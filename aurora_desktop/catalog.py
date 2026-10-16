"""Desktop catalog extensions: non-destructive migrations, 3-column categories and XMLTV."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import io
from collections import defaultdict
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from xml.etree.ElementTree import iterparse

import requests

from .core import ATTR, Library, playlist_lines, kind_of, episode_info, parse_extinf
from .android_rules import normalized, movie_category, football_details
from .provider import get_provider_category_kinds

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


def clean_label(text: str) -> str:
    """Remove formatting markers, not content names."""
    text = text.strip().strip("✦●•|: ")
    return re.sub(r"\s+", " ", text) or "Outros"


def channel_base(title: str) -> str:
    clean = clean_label(title)
    clean = re.sub(r"(?i)^(?:(?:BR|BRA|PT|US)\s*[:|\-]\s*)+", "", clean)
    for label, pattern in CHANNELS:
        if re.search(pattern, clean, re.IGNORECASE):
            return label
    clean = re.sub(r"(?i)\s*[\[(](?:HD|FHD|UHD|4K|SD|BR|H265|HEVC)[\])]", "", clean)
    clean = QUALITY.sub("", clean).strip()
    clean = REGION.sub("", clean).strip(" -|:")
    return clean or "Outros canais"


def category_of(kind: str, title: str, group_name: str) -> str:
    group = clean_label(group_name) if group_name.strip() else ""
    if kind == "live":
        return channel_base(title)
    if kind in ("movie", "series"):
        # Genre comes first for both movies AND series.
        for genre, pattern in GENRES:
            if re.search(pattern, group, re.IGNORECASE):
                return genre
        if kind == "series":
            for provider, pattern in PLATFORMS:
                if re.search(pattern, group, re.IGNORECASE):
                    return provider
            stripped = re.sub(r"(?i)^\s*(s[eé]ries?|series|shows?)\s*(?:[|:/-]\s*)?", "", group).strip()
            return stripped or "Sem plataforma identificada"
        android_category = movie_category(group)
        labels = {
            "__aurora_recent__": "Recentes",
            "__aurora_releases_2026__": "Lançamentos",
            "__aurora_4k__": "4K / UHD",
            "__aurora_adult__": "Adultos",
        }
        return labels.get(android_category, android_category or "Outros filmes")
    return "Outros"


def repair_legacy_title(title: str, group: str, logo: str) -> tuple[str, str, str]:
    """Recover corrupted titles from the 0.1/0.2 EXTINF comma bug."""
    if "tvg-logo=" in title or "group-title=" in title or "tvg-id=" in title:
        parsed = parse_extinf("#EXTINF:-1," + title)
        repaired_title = parsed["title"]
        if repaired_title != title and not repaired_title.startswith("tvg-"):
            return repaired_title, parsed["group"] or group, parsed["logo"] or logo
    return title, group, logo


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
        return stamp.astimezone() if offset else stamp.replace(tzinfo=timezone.utc).astimezone()
    except ValueError:
        return None


def guess_xtream_epg(source: str) -> str:
    """Suggest the standard Xtream XMLTV endpoint without any network call."""
    parsed = urlparse(source)
    args = parse_qs(parsed.query)
    if (parsed.scheme in ("http", "https")
            and parsed.path.lower().endswith("/get.php")
            and args.get("username") and args.get("password")):
        query = urlencode({"username":args["username"][0],"password":args["password"][0]})
        base_path = parsed.path[:-len("/get.php")]
        return urlunparse((parsed.scheme,parsed.netloc,base_path+"/xmltv.php","",query,""))
    return ""


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
    # Xtream-compatible providers can expose XMLTV separately from get.php.
    return guess_xtream_epg(source)


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
            if event == "end" and element.tag in ("programme", "channel"):
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
            if "type_hint" not in cols:
                db.execute("ALTER TABLE items ADD COLUMN type_hint TEXT NOT NULL DEFAULT ''")
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
                CREATE TABLE IF NOT EXISTS classification_version (
                    playlist_id INTEGER PRIMARY KEY REFERENCES playlists(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS provider_category_kinds (
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    normalized_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    PRIMARY KEY (playlist_id,normalized_name)
                );
            """)
            fcols = {r["name"] for r in db.execute("PRAGMA table_info(football_events)")}
            if "broadcast" not in fcols:
                db.execute("ALTER TABLE football_events ADD COLUMN broadcast TEXT NOT NULL DEFAULT 'unknown'")

    def import_playlist(self, playlist_id: int, source: str | None = None) -> int:
        count = super().import_playlist(playlist_id, source)
        with self.connect() as db:
            r = db.execute("SELECT source,epg_url FROM playlists WHERE id=?", (playlist_id,)).fetchone()
        location = source or r["source"] if r else ""
        # Xtream providers can reliably tell us which groups are TV, VOD or series.
        # Metadata is optional and cannot make an otherwise playable M3U fail.
        kinds = get_provider_category_kinds(location)
        if kinds:
            with self.connect() as db:
                db.execute("DELETE FROM provider_category_kinds WHERE playlist_id=?", (playlist_id,))
                db.executemany("INSERT INTO provider_category_kinds VALUES (?,?,?)",
                               [(playlist_id,name,kind) for name,kind in kinds.items()])
        self.ensure_categories(playlist_id, force=True)
        if r and not r["epg_url"]:
            epg = epg_from_header(location)
            if epg:
                self.set_epg_url(playlist_id, epg)
        return count

    def ensure_categories(self, playlist_id: int, force: bool = False) -> None:
        """Reclassify a 0.1/0.2 catalog once, preserving URL-keyed favorites and progress."""
        with self.connect() as db:
            row = db.execute("SELECT version FROM classification_version WHERE playlist_id=?", (playlist_id,)).fetchone()
            if row and row["version"] >= 4 and not force:
                return
            provider_kinds = {r["normalized_name"]:r["kind"] for r in db.execute(
                "SELECT normalized_name,kind FROM provider_category_kinds WHERE playlist_id=?", (playlist_id,))}
            cursor = 0
            while True:
                batch = db.execute("""SELECT rowid,key,title,url,group_name,kind,logo,type_hint
                    FROM items WHERE playlist_id=? AND rowid>? ORDER BY rowid LIMIT 1200""",
                    (playlist_id, cursor)).fetchall()
                if not batch:
                    break
                updated = []
                for item in batch:
                    title, group, logo = repair_legacy_title(item["title"], item["group_name"], item["logo"])
                    kind = provider_kinds.get(normalized(group)) or kind_of(group, title, item["url"], item["type_hint"])
                    series, season, episode = episode_info(title) if kind == "series" else ("", None, None)
                    category = category_of(kind, title, group)
                    updated.append((title,group,logo,kind,category,series,season,episode,item["rowid"]))
                db.executemany("""UPDATE items SET title=?,group_name=?,logo=?,kind=?,
                    category=?,series_name=?,season=?,episode=? WHERE rowid=?""",updated)
                cursor = batch[-1]["rowid"]
            db.execute("""INSERT INTO classification_version VALUES (?,4)
                ON CONFLICT(playlist_id) DO UPDATE SET version=4""", (playlist_id,))

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
        """Android guide parity: match real broadcasts, detect replay, prefer tvg-id."""
        epg_url = self.get_epg_url(playlist_id)
        if not epg_url:
            raise ValueError("Sua playlist não informou XMLTV. Configure o EPG ou consulte os canais esportivos.")
        now = datetime.now().astimezone()
        last_hour = now - timedelta(hours=1)
        end_cutoff = now + timedelta(days=7)
        # Match channel display names only when they map unambiguously to M3U.
        with self.connect() as db:
            records = db.execute("""SELECT title,tvg_id FROM items
                WHERE playlist_id=? AND kind='live'""",(playlist_id,)).fetchall()
        aliases = defaultdict(set)
        valid_ids = set()
        for row in records:
            if row["tvg_id"]:
                valid_ids.add(row["tvg_id"])
            name = re.sub(r"(?i)\b(?:fhd|uhd|hd|sd|4k|h265|h264|alt)\b|[\[\]]"," ",row["title"])
            aliases[normalized(name)].add((row["tvg_id"] or row["title"]))
        channel_map: dict[str,str] = {}
        events = []
        for elem in _read_xmltv(epg_url):
            if elem.tag == "channel":
                xml_id = elem.get("id","")
                if xml_id and xml_id not in valid_ids:
                    matches = set()
                    for display in elem.findall("display-name"):
                        name = re.sub(r"(?i)\b(?:fhd|uhd|hd|sd|4k|h265|h264|alt)\b|[\[\]]"," ",display.text or "")
                        matches.update(aliases.get(normalized(name),set()))
                    if len(matches) == 1:
                        channel_map[xml_id] = next(iter(matches))
                elem.clear()
                continue
            if elem.tag != "programme":
                elem.clear()
                continue
            begin = xmltv_time(elem.get("start",""))
            stop = xmltv_time(elem.get("stop",""))
            if not begin or not (begin <= end_cutoff and (stop or begin+timedelta(hours=2)) > last_hour):
                elem.clear()
                continue
            title = next(((c.text or "") for c in elem if c.tag == "title"), "").strip()
            subtitle = next(((c.text or "") for c in elem if c.tag == "sub-title"), "").strip()
            category = " ".join((c.text or "") for c in elem if c.tag == "category").strip()
            desc = next(((c.text or "") for c in elem if c.tag == "desc"), "").strip()
            name = title if MATCH.search(title) else (subtitle if MATCH.search(subtitle) else desc[:160])
            details = football_details(name,category or title)
            # Keep supporting existing XMLTV feeds with minimal titles and no category.
            if details is None and not category and not FOOTBALL.search(title) and not MATCH.search(title):
                elem.clear()
                continue
            if details is None and not MATCH.search(name):
                elem.clear()
                continue
            if not name:
                elem.clear()
                continue
            if details is None and re.search(
                r"(?i)\b(?:nfl|nba|basquete|rugby|ufc|futsal|volei|t[eê]nis)\b", title+" "+desc
            ):
                elem.clear()
                continue
            competition = (details.competition if details else "") or category or "Jogos"
            replay = any(k in normalized(title+" "+category) for k in
                         ("reprise", "replay", "repeticao", "reexibicao"))
            live = "ao vivo" in normalized(title+" "+category) or elem.find("live") is not None
            if elem.find("previously-shown") is not None:
                replay=True
            broadcast = "replay" if replay else "live" if live else "unknown"
            external_id = elem.get("channel","")
            channel = channel_map.get(external_id,external_id)
            events.append((playlist_id,channel,begin.isoformat(),
                           (stop or begin+timedelta(hours=2)).isoformat(),
                           name,competition,broadcast))
            elem.clear()
            if len(events) > 15_000:
                raise ValueError("O guia contém partidas demais; verifique a fonte XMLTV.")
        with self.connect() as db:
            db.execute("DELETE FROM football_events WHERE playlist_id=?", (playlist_id,))
            db.executemany("""INSERT OR REPLACE INTO football_events
                (playlist_id,channel_id,start,end,title,competition,broadcast)
                VALUES (?,?,?,?,?,?,?)""", events)
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
                    AND kind='live' AND f.channel_id<>'' AND (tvg_id=f.channel_id OR title=f.channel_id)
                    ORDER BY CASE WHEN tvg_id<>'' THEN 0 ELSE 1 END LIMIT 1
                )
                WHERE {' AND '.join(where)} ORDER BY f.start ASC LIMIT ? OFFSET ?"""
            return [dict(r) for r in db.execute(sql,(*args,limit,offset))]

    def football_categories(self, playlist_id: int) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT competition AS title,COUNT(*) AS total FROM football_events WHERE playlist_id=? GROUP BY competition ORDER BY title",
                (playlist_id,))]


    def sport_channels(self, playlist_id: int, search: str = "", limit: int = 160) -> list[dict]:
        """When an EPG is missing, show genuine sports channels, not imaginary games."""
        pattern = r"(?i)(sportv|premiere|espn|fox\s*sports|tnt\s*sports|futebol|sport|esport|canal\s*goat|caz[eé]\s*tv|bandsports)"
        with self.connect() as db:
            rows = db.execute("""SELECT * FROM items WHERE playlist_id=? AND kind='live'
                ORDER BY title COLLATE NOCASE LIMIT 15000""", (playlist_id,))
            result = []
            for r in rows:
                if re.search(pattern, r["title"] + " " + r["group_name"]) and (
                    not search or search.casefold() in r["title"].casefold()):
                    item = dict(r)
                    item["kind"] = "football_channel"
                    result.append(item)
                    if len(result) >= limit:
                        break
            return result
