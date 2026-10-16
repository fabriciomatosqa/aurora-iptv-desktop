"""Desktop catalog extensions: non-destructive migrations, 3-column categories and XMLTV."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import gzip
import io
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
from urllib.parse import urlparse
from xml.etree.ElementTree import iterparse

import requests

from .core import ATTR, Library, playlist_lines

GENRES = (
    ("Ação", r"\ba[cç][aã]o\b|\baction\b"),
    ("Terror", r"\bterror\b|\bhorror\b"),
    ("Comédia", r"\bcom[eé]dia\b|\bcomedy\b"),
    ("Drama", r"\bdrama\b"),
    ("Suspense", r"\bsuspense\b|\bthriller\b"),
    ("Aventura", r"\baventura\b|\badventure\b"),
    ("Ficção científica", r"\bfic[cç][aã]o\b|\bsci.?fi\b"),
    ("Romance", r"\bromance\b"),
    ("Animação", r"\banima[cç][aã]o\b|\banima(?:tion|ted)\b"),
    ("Documentário", r"\bdocument[aá]ri[oa]s?\b|\bdocumentary\b"),
    ("Infantil", r"\binfantil\b|\bkids\b"),
    ("Faroeste", r"\bfaroeste\b|\bwestern\b"),
)
PLATFORMS = (
    ("Netflix", r"\bnetflix\b"), ("Prime Video", r"\bprime\s*video\b|\bamazon\s*prime\b"),
    ("Disney+", r"\bdisney\b"), ("Max / HBO", r"\bhbo\b|\bmax\b"),
    ("Apple TV+", r"\bapple\s*tv\b"), ("Paramount+", r"\bparamount\b"),
    ("Globoplay", r"\bgloboplay\b"), ("Hulu", r"\bhulu\b"),
    ("Crunchyroll", r"\bcrunchyroll\b"), ("Star+", r"\bstar\+?\b"),
)
CHANNELS = (
    ("Globo", r"^(?:rede\s+|tv\s+)?globo\b"),
    ("SBT", r"^(?:tv\s+)?sbt\b"),
    ("Record", r"^(?:rede\s+|tv\s+)?record\b"),
    ("Band", r"^(?:tv\s+|rede\s+)?band\b"),
    ("RedeTV!", r"^rede\s*tv\b"),
    ("CNN Brasil", r"^cnn\s*brasil\b"),
    ("SporTV", r"^sportv\b"),
    ("Premiere", r"^premiere\b"),
    ("ESPN", r"^espn\b"),
    ("TNT Sports", r"^tnt\s*sports?\b"),
    ("Cultura", r"^(?:tv\s+)?cultura\b"),
    ("Gazeta", r"^(?:tv\s+)?gazeta\b"),
    ("Canção Nova", r"^can[cç][aã]o\s+nova\b"),
)
QUALITY = re.compile(r"(?i)(?:[\[(]?\s*(?:4k|uhd|fhd|full\s*hd|hd|sd|h265|hevc|backup|alt(?:ernativo)?|vip|60\s*fps)\s*[\])]?\s*)+$")
REGION = re.compile(r"(?i)(?:\s+[-|]?\s*(?:br|rj|sp|mg|rs|pr|ba|df|es|sc|pe|ce|go|pa|am|pb|rn|se|al|mt|ms|pi|ma|to|ac|ap|ro|rr))+$")
MATCH = re.compile(r"(?i)\b[\wÀ-ÿ][\wÀ-ÿ .'-]{1,45}\s+(?:x|vs\.?|versus|×)\s+[\wÀ-ÿ][\wÀ-ÿ .'-]{1,45}")
FOOTBALL = re.compile(r"(?i)\bfutebol\b|\bfootball\b|\bsoccer\b|\bbrasileir[aã]o\b|\bchampions\b|\blibertadores\b|\bcopa\s+do\s+brasil\b|\bmundial\s+de\s+clubes\b")


def channel_base(title: str) -> str:
    clean = re.sub(r'^\s*(?:BR\s*[:|]\s*)', '', title, flags=re.IGNORECASE).strip()
    for label, pattern in CHANNELS:
        if re.search(pattern, clean, re.IGNORECASE):
            return label
    clean = re.sub(r"\s*[\[(](?:HD|FHD|UHD|4K|SD|BR)[\])]", "", clean, flags=re.IGNORECASE)
    clean = QUALITY.sub("", clean).strip()
    clean = REGION.sub("", clean).strip(" -|:")
    return clean or "Sem nome"


def category_of(kind: str, title: str, group_name: str) -> str:
    group = group_name.strip()
    if kind == "live":
        return channel_base(title)
    if kind == "movie":
        for genre, pattern in GENRES:
            if re.search(pattern, group, re.IGNORECASE):
                return genre
        return group or "Outros filmes"
    if kind == "series":
        for provider, pattern in PLATFORMS:
            if re.search(pattern, group, re.IGNORECASE):
                return provider
        # Do not invent a streaming company when none is identified.
        cleaned = re.sub(r"(?i)^\s*(s[eé]ries?|series|shows?)\s*(?:[|:\/-]\s*)?", "", group).strip()
        return cleaned or "Sem plataforma identificada"
    return "Outros"


def xmltv_time(value: str) -> datetime | None:
    value = (value or "").strip()
    match = re.match(r"^(\d{12,14})(?:\s*([+-]\d{4}))?", value)
    if not match:
        return None
    date, offset = match.groups()
    if len(date) == 12:
        date += "00"
    try:
        stamp = datetime.strptime(date + (" " + offset if offset else ""), "%Y%m%d%H%M%S %z" if offset else "%Y%m%d%H%M%S")
        return stamp.astimezone() if offset else stamp.astimezone()
    except ValueError:
        return None


def epg_from_header(source: str) -> str:
    """Read just the beginning of the M3U for the URL advertised by its owner."""
    try:
        iterator = playlist_lines(source)
        try:
            first = next(iterator, "")
        finally:
            iterator.close()
        if first.lstrip("\ufeff").startswith("#EXTM3U"):
            attrs = {k.lower(): v for k, v in ATTR.findall(first)}
            url = attrs.get("x-tvg-url", attrs.get("url-tvg", "")).split(",")[0].strip()
            if urlparse(url).scheme in ("http", "https"):
                return url
    except (OSError, requests.RequestException, ValueError):
        pass
    return ""


def _read_xmltv(source: str):
    """Spool XMLTV to disk rather than reading large provider guides into RAM."""
    parsed = urlparse(source)
    with tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024) as file:
        if parsed.scheme in ("http", "https"):
            with requests.get(source, stream=True, timeout=(10, 90)) as response:
                response.raise_for_status()
                count = 0
                for chunk in response.iter_content(65536):
                    count += len(chunk)
                    if count > 160 * 1024 * 1024:
                        raise ValueError("EPG muito grande (limite de 160 MB comprimidos).")
                    file.write(chunk)
        else:
            path = Path(source)
            if path.stat().st_size > 160 * 1024 * 1024:
                raise ValueError("EPG muito grande (limite de 160 MB).")
            with path.open("rb") as origin:
                while chunk := origin.read(65536):
                    file.write(chunk)
        file.seek(0)
        magic = file.read(2)
        file.seek(0)
        reader = gzip.GzipFile(fileobj=file) if magic == b"\x1f\x8b" else file
        context = iterparse(reader, events=("start", "end"))
        try:
            _, root = next(context)
        except StopIteration:
            return
        for event, element in context:
            if event == "end" and element.tag == "programme":
                yield element
                root.clear()


class LibraryV2(Library):
    def __init__(self, path=None):
        super().__init__(path)
        with self.connect() as db:
            cols = {r["name"] for r in db.execute("PRAGMA table_info(items)")}
            if "category" not in cols:
                db.execute("ALTER TABLE items ADD COLUMN category TEXT NOT NULL DEFAULT ''")
            if "tvg_id" not in cols:
                db.execute("ALTER TABLE items ADD COLUMN tvg_id TEXT NOT NULL DEFAULT ''")
            pcols = {r["name"] for r in db.execute("PRAGMA table_info(playlists)")}
            if "epg_url" not in pcols:
                db.execute("ALTER TABLE playlists ADD COLUMN epg_url TEXT NOT NULL DEFAULT ''")
            db.executescript("""
                CREATE INDEX IF NOT EXISTS idx_items_category ON items(playlist_id,kind,category,title COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_items_tvg ON items(playlist_id,tvg_id);
                CREATE TABLE IF NOT EXISTS football_events (
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    channel_id TEXT NOT NULL, start TEXT NOT NULL, end TEXT,
                    title TEXT NOT NULL, competition TEXT NOT NULL,
                    PRIMARY KEY (playlist_id,channel_id,start,title)
                );
                CREATE INDEX IF NOT EXISTS idx_football_start ON football_events(playlist_id,start);
            """)

    def import_playlist(self, playlist_id: int, source: str | None = None) -> int:
        count = super().import_playlist(playlist_id, source)
        self.ensure_categories(playlist_id)
        with self.connect() as db:
            r = db.execute("SELECT source,epg_url FROM playlists WHERE id=?", (playlist_id,)).fetchone()
        if r and not r["epg_url"]:
            epg = epg_from_header(source or r["source"])
            if epg:
                self.set_epg_url(playlist_id, epg)
        return count

    def ensure_categories(self, playlist_id: int) -> None:
        """Migrate older v0.1 catalogs in bounded batches; never erase user data."""
        with self.connect() as db:
            while True:
                batch = db.execute("""SELECT key,title,group_name,kind FROM items
                    WHERE playlist_id=? AND category='' LIMIT 1000""", (playlist_id,)).fetchall()
                if not batch:
                    break
                db.executemany("UPDATE items SET category=? WHERE playlist_id=? AND key=?",
                    [(category_of(r["kind"],r["title"],r["group_name"]),playlist_id,r["key"]) for r in batch])
            db.commit()

    def categories(self, playlist_id: int, kind: str) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("""
                SELECT category AS title, COUNT(*) AS total
                FROM items WHERE playlist_id=? AND kind=?
                GROUP BY category ORDER BY title COLLATE NOCASE
            """, (playlist_id,kind))]

    def browse(self, playlist_id: int, kind: str, category: str | None,
               search: str = "", limit: int = 70, offset: int = 0) -> list[dict]:
        where = ["playlist_id=?", "kind=?"]
        args: list = [playlist_id,kind]
        if category:
            where.append("category=?")
            args.append(category)
        if search:
            where.append("(title LIKE ? OR series_name LIKE ?)")
            args.extend([f"%{search}%",f"%{search}%"])
        condition = " AND ".join(where)
        with self.connect() as db:
            if kind == "series":
                sql = f"""SELECT series_name AS title,series_name, 'series' AS kind,
                    MAX(logo) AS logo, MIN(key) AS key,COUNT(*) AS episodes,MIN(category) AS category
                    FROM items WHERE {condition}
                    GROUP BY series_name ORDER BY series_name COLLATE NOCASE LIMIT ? OFFSET ?"""
            else:
                sql = f"SELECT * FROM items WHERE {condition} ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?"
            return [dict(r) for r in db.execute(sql,(*args,limit,offset))]

    def favorite_entries(self, playlist_id: int, search: str = "") -> list[dict]:
        with self.connect() as db:
            rows = [dict(r) for r in db.execute(
                "SELECT * FROM favorites WHERE playlist_id=? AND title LIKE ? ORDER BY title COLLATE NOCASE LIMIT 500",
                (playlist_id,f"%{search}%"))]
            for r in rows:
                if r["kind"] == "series":
                    item = db.execute("""SELECT MAX(logo) AS logo,series_name,COUNT(*) AS episodes FROM items
                        WHERE playlist_id=? AND series_name=?""",(playlist_id,r["title"])).fetchone()
                else:
                    item = db.execute("SELECT logo FROM items WHERE playlist_id=? AND key=?",
                        (playlist_id,r["key"][5:])).fetchone()
                r["logo"] = item["logo"] if item else ""
            return rows

    def set_epg_url(self, playlist_id: int, url: str) -> None:
        url = url.strip()
        if url and urlparse(url).scheme not in ("http","https","file") and not Path(url).exists():
            raise ValueError("Use uma URL HTTP/HTTPS ou um caminho de arquivo XMLTV.")
        with self.connect() as db:
            db.execute("UPDATE playlists SET epg_url=? WHERE id=?",(url,playlist_id))

    def get_epg_url(self, playlist_id: int) -> str:
        with self.connect() as db:
            r = db.execute("SELECT epg_url FROM playlists WHERE id=?",(playlist_id,)).fetchone()
            return r["epg_url"] if r else ""

    def import_football(self, playlist_id: int) -> int:
        """Guide dates come exclusively from XMLTV. Never synthesize kickoff times."""
        epg_url = self.get_epg_url(playlist_id)
        if not epg_url:
            raise ValueError("Configure uma URL XMLTV nas Configurações para carregar o Futebol.")
        now = datetime.now().astimezone()
        start_cutoff = now - timedelta(hours=3)
        end_cutoff = now + timedelta(days=7)
        events = []
        for elem in _read_xmltv(epg_url):
            time = xmltv_time(elem.get("start", ""))
            if time and start_cutoff <= time <= end_cutoff:
                title = next((c.text or "" for c in elem if c.tag == "title"), "").strip()
                desc = next((c.text or "" for c in elem if c.tag == "desc"), "").strip()
                if title and (MATCH.search(title) or (FOOTBALL.search(title) and MATCH.search(desc))):
                    name = title if MATCH.search(title) else desc[:140]
                    comp = title if name != title else "Jogos"
                    events.append((playlist_id,elem.get("channel",""),time.isoformat(),
                                   (xmltv_time(elem.get("stop","")) or time).isoformat(),name,comp))
            elem.clear()
            if len(events) > 15000:
                raise ValueError("EPG retornou jogos demais. Verifique a origem XMLTV.")
        with self.connect() as db:
            db.execute("DELETE FROM football_events WHERE playlist_id=?", (playlist_id,))
            db.executemany("INSERT OR REPLACE INTO football_events VALUES (?,?,?,?,?,?)", events)
        return len(events)

    def football(self, playlist_id: int, category: str | None = None, search: str = "",
                 limit: int = 70, offset: int = 0) -> list[dict]:
        with self.connect() as db:
            where = ["f.playlist_id=?"]
            args: list = [playlist_id]
            if category:
                where.append("f.competition=?")
                args.append(category)
            if search:
                where.append("f.title LIKE ?")
                args.append(f"%{search}%")
            sql = f"""SELECT f.*, i.title AS channel_title, i.url, i.key, i.logo, 'football' AS kind
                FROM football_events f LEFT JOIN items i ON i.rowid=(
                  SELECT rowid FROM items WHERE playlist_id=f.playlist_id
                    AND kind='live' AND (tvg_id=f.channel_id OR title=f.channel_id)
                    ORDER BY CASE WHEN tvg_id=f.channel_id THEN 0 ELSE 1 END LIMIT 1
                )
                WHERE {' AND '.join(where)} ORDER BY f.start ASC LIMIT ? OFFSET ?"""
            return [dict(r) for r in db.execute(sql,(*args,limit,offset))]

    def football_categories(self, playlist_id: int) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT competition AS title,COUNT(*) AS total FROM football_events WHERE playlist_id=? GROUP BY competition ORDER BY title",
                (playlist_id,))]
