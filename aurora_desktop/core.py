"""Core persistence and streaming M3U parser for AURORA IPTV Desktop.

This module has no Qt imports so library operations can be tested independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import urlsplit
import os
import re
import sqlite3
import sys

import requests

from .android_rules import classify_content, series_identity
from .artwork import pick_best_art

ATTR = re.compile(r'([\w-]+)\s*=\s*"([^"]*)"')
ATTR_ANY = re.compile(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")

EPISODE = re.compile(r"(?i)\bS(?:eason)?\s*0*(\d{1,3})\s*[ ._-]*E(?:pisode)?\s*0*(\d{1,4})\b")
ALT_EPISODE = re.compile(r"(?i)\b(\d{1,2})x(\d{1,3})\b")
MOVIE_TAG = re.compile(r"(?i)\b(filmes?|movies?|cinema|vod)\b")
SERIES_TAG = re.compile(r"(?i)\b(s[eé]ries?|series|shows?|novelas?|animes?)\b")


def data_directory() -> Path:
    if sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or Path.home())
        return root / 'AURORA IPTV'
    root = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share')))
    return root / 'aurora-iptv'


def content_id(url: str) -> str:
    return sha256(url.encode('utf-8')).hexdigest()


def kind_of(group: str, title: str, url: str, type_hint: str = "",
            tvg_id: str = "", provider_kind: str = "") -> str:
    return classify_content(title, group, url, type_hint, tvg_id, provider_kind)


def parse_extinf(line: str) -> dict[str, str]:
    """Parse EXTINF with attributes before *or after* the first comma.

    Several IPTV generators emit '#EXTINF:-1, tvg-logo="..." group-title="...",Title'.
    A normal split(',', 1) exposes metadata as the item title; this parser
    finds the delimiter outside quotes and after the final metadata attribute.
    """
    attrs_matches = list(ATTR_ANY.finditer(line))
    attrs = {m.group(1).lower(): (m.group(2) or m.group(3)) for m in attrs_matches}
    last_attr_end = max((m.end() for m in attrs_matches), default=0)
    commas = []
    quoted = None
    for pos, char in enumerate(line):
        if char in ('"', "'") and (quoted is None or quoted == char):
            quoted = char if quoted is None else None
        elif char == "," and quoted is None:
            commas.append(pos)
    delim = next((p for p in commas if p >= last_attr_end), None)
    if delim is None and commas and commas[0] < last_attr_end:
        # Malformed provider line without a final title separator.
        suffix = line[last_attr_end:].strip(" \t,")
        title = suffix if suffix and "=" not in suffix else attrs.get("tvg-name", "")
    else:
        if delim is None and commas:
            delim = commas[0]
        title = line[delim + 1:].strip() if delim is not None else attrs.get("tvg-name", "")
    if not title or title.startswith(("tvg-logo=", "group-title=", "tvg-id=")):
        title = attrs.get("tvg-name", "") or title
    return {
        "title": title or "Sem título",
        "group": attrs.get("group-title", ""),
        "logo": pick_best_art(attrs),
        "artwork_fields": attrs,
        "tvg_id": attrs.get("tvg-id", ""),
        "xui_id": attrs.get("xui-id", "").strip(),
        "type_hint": next((attrs[k] for k in ("media-type","tvg-type","content-type","type") if attrs.get(k)), ""),
        "synopsis": next((attrs[k] for k in ("tvg-description","description","synopsis","plot","summary","tvg-desc","desc")
                         if attrs.get(k)), "")[:12000],
    }


def episode_info(title: str) -> tuple[str, int | None, int | None]:
    identity = series_identity(title)
    return identity.title, identity.season if identity.episode > 0 else None, identity.episode or None


@dataclass(frozen=True)
class Entry:
    key: str
    title: str
    url: str
    group_name: str
    kind: str
    logo: str
    series_name: str
    season: int | None
    episode: int | None
    tvg_id: str = ''
    type_hint: str = ''
    synopsis: str = ''
    xui_id: str = ''


def parse_m3u(lines: Iterable[str]) -> Iterator[Entry]:
    """Yield items lazily: memory usage is independent of playlist size."""
    info: dict[str, str] | None = None
    for raw in lines:
        line = raw.strip().lstrip('\ufeff')
        if not line:
            continue
        if line.startswith('#EXT-X-TARGETDURATION') or line.startswith('#EXT-X-MEDIA-SEQUENCE'):
            raise ValueError('Este arquivo é uma transmissão HLS, não uma lista de canais M3U.')
        if line.startswith('#EXTINF:'):
            info = parse_extinf(line)
            continue
        if line.startswith('#EXTGRP:') and info is not None:
            info['group'] = line[len('#EXTGRP:'):].strip()
            continue
        if line.startswith('#'):
            continue
        if info is None:
            continue
        url = line
        if not urlsplit(url).scheme and not Path(url).is_absolute():
            info = None
            continue
        name = info['title']
        typ = kind_of(info['group'], name, url, info.get('type_hint', ''), info['tvg_id'])
        series, season, episode = episode_info(name) if typ == 'series' else ('', None, None)
        # Give films/series their actual cover priority while channels keep
        # the broadcaster logo. This field is persisted in the existing logo
        # column, so no database migration is required.
        artwork = pick_best_art({**info.get("artwork_fields", {}), "kind":typ}) or info["logo"]
        yield Entry(content_id(url), name, url, info['group'], typ, artwork, series, season, episode,
                    info['tvg_id'], info.get('type_hint', ''), info.get('synopsis', ''),
                    info.get('xui_id',''))
        info = None


def playlist_lines(source: str) -> Iterator[str]:
    parsed = urlsplit(source)
    if parsed.scheme in ('http', 'https'):
        with requests.get(source, stream=True, timeout=(10, 50), headers={"User-Agent": "AURORA-IPTV-Desktop/0.1"}) as response:
            response.raise_for_status()
            for raw in response.iter_lines(chunk_size=65536):
                if raw:
                    yield raw.decode('utf-8-sig', errors='replace')
    elif not parsed.scheme or parsed.scheme == 'file' or Path(source).is_absolute():
        file = Path(source) if parsed.scheme != 'file' else Path(parsed.path)
        with file.open('r', encoding='utf-8-sig', errors='replace') as stream:
            yield from stream
    else:
        raise ValueError('Endereço não suportado. Use HTTPS, HTTP ou arquivo local.')


class Library:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else data_directory() / 'catalog.db'
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != 'nt':
            self.path.parent.chmod(0o700)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=30000')
        return db

    def _initialize(self) -> None:
        with self.connect() as db:
            # Set WAL once, not on every reader connection or worker thread.
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS items (
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    key TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
                    group_name TEXT NOT NULL, kind TEXT NOT NULL, logo TEXT NOT NULL,
                    series_name TEXT NOT NULL, season INTEGER, episode INTEGER,
                    tvg_id TEXT NOT NULL DEFAULT '', type_hint TEXT NOT NULL DEFAULT '',
                    synopsis TEXT NOT NULL DEFAULT '',
                    xui_id TEXT NOT NULL DEFAULT '', PRIMARY KEY(playlist_id,key)
                );
                CREATE INDEX IF NOT EXISTS idx_items_kind ON items(playlist_id,kind,title COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_items_series ON items(playlist_id,series_name,season,episode);
                CREATE TABLE IF NOT EXISTS favorites (
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    key TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                    PRIMARY KEY(playlist_id,key)
                );
                CREATE TABLE IF NOT EXISTS progress (
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    key TEXT NOT NULL, seconds INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(playlist_id,key)
                );
            ''')
        # Schema migrations keep all existing favorites/progress and keys.
        with self.connect() as db:
            existing = {r["name"] for r in db.execute("PRAGMA table_info(items)")}
            if "synopsis" not in existing:
                db.execute("ALTER TABLE items ADD COLUMN synopsis TEXT NOT NULL DEFAULT ''")
            if "xui_id" not in existing:
                db.execute("ALTER TABLE items ADD COLUMN xui_id TEXT NOT NULL DEFAULT ''")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_items_xui_id
                ON items(playlist_id,xui_id) WHERE xui_id<>''""")
        if os.name != 'nt':
            self.path.chmod(0o600)

    def playlists(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM playlists ORDER BY id')]

    def add_playlist(self, name: str, source: str) -> int:
        name, source = name.strip(), source.strip()
        if not name or not source:
            raise ValueError('Informe nome e endereço da lista.')
        scheme = urlsplit(source).scheme.lower()
        if scheme not in ('http', 'https', 'file', '') and not Path(source).is_absolute():
            raise ValueError('Use HTTP, HTTPS ou caminho de arquivo local.')
        with self.connect() as db:
            cur = db.execute('INSERT INTO playlists (name,source) VALUES (?,?)', (name, source))
            return int(cur.lastrowid)

    def update_playlist(self, playlist_id: int, name: str, source: str) -> None:
        if not name.strip() or not source.strip():
            raise ValueError('Nome e endereço não podem ficar vazios.')
        if urlsplit(source).scheme.lower() not in ('http', 'https', 'file', '') and not Path(source).is_absolute():
            raise ValueError('Endereço inválido.')
        with self.connect() as db:
            db.execute('UPDATE playlists SET name=?,source=? WHERE id=?', (name.strip(), source.strip(), playlist_id))

    def delete_playlist(self, playlist_id: int) -> None:
        with self.connect() as db:
            db.execute('DELETE FROM playlists WHERE id=?', (playlist_id,))

    def import_playlist(self, playlist_id: int, source: str | None = None, *, merge: bool = False) -> int:
        """Atomically import a catalog. Merge keeps yesterday's entries on refresh."""
        with self.connect() as db:
            rec = db.execute('SELECT source FROM playlists WHERE id=?', (playlist_id,)).fetchone()
            if not rec:
                raise ValueError('Lista não encontrada.')
        location = source or rec['source']
        total = 0
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TEMP TABLE staging (
                playlist_id INTEGER NOT NULL, key TEXT NOT NULL, title TEXT NOT NULL,
                url TEXT NOT NULL, group_name TEXT NOT NULL, kind TEXT NOT NULL,
                logo TEXT NOT NULL, series_name TEXT NOT NULL, season INTEGER, episode INTEGER,
                tvg_id TEXT NOT NULL DEFAULT '', type_hint TEXT NOT NULL DEFAULT '',
                synopsis TEXT NOT NULL DEFAULT '', xui_id TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(playlist_id,key)
            )''')
            pending = []
            for entry in parse_m3u(playlist_lines(location)):
                pending.append((playlist_id, entry.key, entry.title, entry.url, entry.group_name,
                                entry.kind, entry.logo, entry.series_name, entry.season, entry.episode,
                                entry.tvg_id, entry.type_hint, entry.synopsis, entry.xui_id))
                total += 1
                if len(pending) >= 1000:
                    db.executemany('INSERT OR REPLACE INTO staging VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', pending)
                    pending.clear()
            if pending:
                db.executemany('INSERT OR REPLACE INTO staging VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', pending)
            if total == 0:
                raise ValueError('A lista não contém entradas M3U válidas. Seu catálogo anterior foi preservado.')
            old_count = db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",
                                   (playlist_id,)).fetchone()[0]
            # M3U output protocols (HLS/MPEG-TS) can change stream URLs
            # without changing the provider's item ID. Preserve the previously
            # stored URL key so favorites and playback progress still resolve.
            # Skip IDs that are duplicated in either snapshot.
            if merge:
                db.execute("""UPDATE items SET xui_id=(
                    SELECT s.xui_id FROM staging s
                    WHERE s.playlist_id=items.playlist_id AND s.key=items.key)
                    WHERE playlist_id=? AND xui_id='' AND EXISTS (
                    SELECT 1 FROM staging s WHERE s.key=items.key
                    AND s.playlist_id=items.playlist_id AND s.xui_id<>'')""",(playlist_id,))
                db.execute("""CREATE TEMP TABLE unambiguous_source_ids AS
                    SELECT xui_id FROM staging WHERE xui_id<>''
                    GROUP BY xui_id HAVING COUNT(*)=1""")
                db.execute("""CREATE TEMP TABLE key_remaps AS
                    SELECT s.key AS incoming_key, MIN(i.key) AS stable_key
                    FROM staging s JOIN unambiguous_source_ids u ON u.xui_id=s.xui_id
                    JOIN items i ON i.playlist_id=s.playlist_id AND i.xui_id=s.xui_id
                    WHERE s.playlist_id=? AND i.key<>s.key
                    AND NOT EXISTS (SELECT 1 FROM staging active
                                    WHERE active.key=i.key)
                    GROUP BY s.key HAVING COUNT(*)=1""",(playlist_id,))
                db.execute("""UPDATE staging SET key=(
                    SELECT m.stable_key FROM key_remaps m
                    WHERE m.incoming_key=staging.key)
                    WHERE key IN (SELECT incoming_key FROM key_remaps)""")
            if not merge:
                db.execute('DELETE FROM items WHERE playlist_id=?', (playlist_id,))
            db.execute('''INSERT OR REPLACE INTO items
                    (playlist_id,key,title,url,group_name,kind,logo,series_name,
                     season,episode,tvg_id,type_hint,synopsis,xui_id)
                    SELECT playlist_id,key,title,url,group_name,kind,logo,series_name,
                           season,episode,tvg_id,type_hint,synopsis,xui_id FROM staging''')
            # A nearly complete refresh is safe to reconcile. A truncated
            # remote response must never erase a healthy offline library.
            if merge:
                if old_count and total >= 50 and total * 100 >= old_count * 97:
                    db.execute("""DELETE FROM items WHERE playlist_id=?
                        AND NOT EXISTS (SELECT 1 FROM staging s
                                        WHERE s.playlist_id=items.playlist_id
                                        AND s.key=items.key)""",(playlist_id,))
            db.execute('UPDATE playlists SET updated_at=CURRENT_TIMESTAMP WHERE id=?', (playlist_id,))
            db.commit()
            return total
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def items(self, playlist_id: int, kind: str, search: str = '', limit: int = 100, offset: int = 0) -> list[dict]:
        clause = ' AND title LIKE ?' if search else ''
        params = (playlist_id, kind, f'%{search}%') if search else (playlist_id, kind)
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                f'SELECT * FROM items WHERE playlist_id=? AND kind=?{clause} ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?',
                (*params, limit, offset))]

    def series(self, playlist_id: int, search: str = '', limit: int = 100, offset: int = 0) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('''
                SELECT series_name AS title, COUNT(*) AS episodes
                FROM items WHERE playlist_id=? AND kind='series' AND series_name LIKE ?
                GROUP BY series_name ORDER BY series_name COLLATE NOCASE LIMIT ? OFFSET ?
            ''', (playlist_id, f'%{search}%', limit, offset))]

    def episodes(self, playlist_id: int, series_name: str) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('''
                SELECT * FROM items WHERE playlist_id=? AND kind='series' AND series_name=?
                ORDER BY season,episode,title LIMIT 2000
            ''', (playlist_id, series_name))]

    def item(self, playlist_id: int, key: str) -> dict | None:
        with self.connect() as db:
            rec = db.execute('SELECT * FROM items WHERE playlist_id=? AND key=?', (playlist_id, key)).fetchone()
            return dict(rec) if rec else None

    def set_favorite(self, playlist_id: int, key: str, kind: str, title: str, enabled: bool) -> None:
        with self.connect() as db:
            if enabled:
                db.execute('INSERT OR REPLACE INTO favorites VALUES (?,?,?,?)', (playlist_id,key,kind,title))
            else:
                db.execute('DELETE FROM favorites WHERE playlist_id=? AND key=?', (playlist_id,key))

    def is_favorite(self, playlist_id: int, key: str) -> bool:
        with self.connect() as db:
            return db.execute('SELECT 1 FROM favorites WHERE playlist_id=? AND key=?', (playlist_id,key)).fetchone() is not None

    def favorites(self, playlist_id: int, search: str = '') -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('''
                SELECT * FROM favorites WHERE playlist_id=? AND title LIKE ? ORDER BY title COLLATE NOCASE LIMIT 500
            ''', (playlist_id, f'%{search}%'))]

    def save_progress(self, playlist_id: int, key: str, seconds: int) -> None:
        with self.connect() as db:
            db.execute('''INSERT INTO progress (playlist_id,key,seconds) VALUES (?,?,?)
                ON CONFLICT(playlist_id,key) DO UPDATE SET seconds=excluded.seconds, updated_at=CURRENT_TIMESTAMP''',
                (playlist_id,key,max(0,int(seconds))))

    def get_progress(self, playlist_id: int, key: str) -> int:
        with self.connect() as db:
            row = db.execute('SELECT seconds FROM progress WHERE playlist_id=? AND key=?', (playlist_id,key)).fetchone()
            return int(row['seconds']) if row else 0

    def recent(self, playlist_id: int, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('''
                SELECT i.* ,p.seconds FROM progress p
                JOIN items i ON i.playlist_id=p.playlist_id AND i.key=p.key
                WHERE p.playlist_id=? ORDER BY p.updated_at DESC LIMIT ?
            ''', (playlist_id,limit))]

    def counts(self, playlist_id: int) -> dict[str, int]:
        with self.connect() as db:
            rows = db.execute('SELECT kind,COUNT(*) AS count FROM items WHERE playlist_id=? GROUP BY kind', (playlist_id,))
            return {r['kind']: int(r['count']) for r in rows}
