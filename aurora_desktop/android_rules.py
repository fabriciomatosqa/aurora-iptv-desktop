"""Portable domain rules adapted from AURORA IPTV Android business logic.

Reference files in github.com/fabriciomatosqa/iptv-player:
Playlist.kt, Series.kt, MovieCategories.kt, ContentRules.kt, ProviderApi.kt.

No GUI imports and no network traffic. Keep stable URL identifiers so that
catalog upgrades never invalidate favorite URLs or watch progress.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode
import re
import unicodedata


def normalized(value: str) -> str:
    words = unicodedata.normalize("NFD", value.casefold())
    words = "".join(c for c in words if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", words).strip()


EPISODE_PATTERNS = (
    re.compile(r"\bS\s*(\d{1,3})\s*[.\- ]*E\s*(\d{1,4})\b", re.I),
    re.compile(r"\b(\d{1,3})\s*x\s*(\d{1,4})\b", re.I),
    re.compile(r"\b(?:temporada|season|temp\.?|t)\s*(\d{1,3})\s*[.\-: ]*(?:epis[oó]dio|episode|ep\.?|cap[ií]tulo|cap\.?|e)\s*(\d{1,4})\b", re.I),
)
EPISODE_ONLY = re.compile(r"\b(?:epis[oó]dio|episode|ep\.?|cap[ií]tulo|cap\.?)\s*(\d{1,4})\b", re.I)
QUALITY = re.compile(r"[\[(]\s*(?:br|pt|hd|fhd|sd|uhd|4k|720p|1080p|2160p|dublado|dub|legendado|leg|dual audio)\s*[\])]", re.I)
TRAILING_QUALITY = re.compile(r"\s*[-|]?\s*(?:hd|fhd|sd|uhd|4k|720p|1080p|2160p|dublado|dub|legendado|leg|dual audio)\s*$", re.I)
VOD_FILE = re.compile(r"\.(?:mp4|mkv|avi|mov|m4v|wmv|webm)(?:[?#]|$)", re.I)
SERIES_WORDS = re.compile(r"\b(?:series?|seriados|tv shows?|temporadas?|episodios?|animes?|novelas?)\b")
MOVIE_WORDS = re.compile(r"\b(?:filmes?|movies?|cinema|lancamentos|film|acao|animacao|aventura|comedia|crime|documentarios?|drama|familia|faroeste|ficcao|guerra|fantasia|romance|suspense|terror|legendados|nacionais|dublagem|adultos|reelsshorts)\b")
ADULT_WORDS = re.compile(r"\b(?:adultos?|adults?|xxx|porn[oô]?|pornografia|hentais?|erotico|erotica)\b")
NON_FOOTBALL = re.compile(r"\b(?:americano|american|nfl|rugby|basquete|basketball|nba|baseball|beisebol|ufc|bjj|volei|voleibol|tenis|handebol|futsal)\b")
NON_MATCH_PROGRAMMES = re.compile(r"\b(?:resenha|debate|mesa redonda|central do|noticias|jornal|sportcenter|sportscenter|gols da rodada|melhores momentos|documentario|40 minutos)\b")
COMPETITIONS = re.compile(r"\b(?:brasileirao|libertadores|sul americana|sulamericana|champions league|liga dos campeoes|premier league|la liga|laliga|bundesliga|ligue 1|liga europa|europa league|conference league|copa do brasil|copa do mundo|copa do nordeste|serie [ab] italiana|campeonato (?:brasileiro|paulista|carioca|ingles|espanhol|portugues|italiano|alemao)|futebol|soccer|football)\b")
VERSUS = re.compile(r"\s+(?:x|vs\.?|v\.?|versus|×)\s+", re.I)


def has_episode_marker(name: str) -> bool:
    return any(p.search(name) for p in EPISODE_PATTERNS) or bool(EPISODE_ONLY.search(name))


def classify_content(name: str, group: str, url: str,
                     type_hint: str = "", tvg_id: str = "") -> str:
    """Conservative, ordered M3U/Xtream classification.

    Never infer 'live' solely because an item is ambiguous. High-confidence
    fields win over generic genre words, e.g. 'canais de filmes' means TV.
    """
    hint = normalized(type_hint)
    if hint in ("live", "tv", "ao vivo", "channel", "linear"):
        return "live"
    if hint in ("movie", "movies", "filme", "filmes", "film"):
        return "movie"
    if hint in ("series", "serie", "episode", "episodio", "tv show", "show"):
        return "series"
    path = urlsplit(url).path.lower()
    if "/series/" in path or "/episode/" in path:
        return "series"
    if "/live/" in path or path.startswith("/play/") and (
            path.endswith("/ts") or path.endswith("/m3u8")):
        return "live"
    if "/movie/" in path or "/movies/" in path or "/vod/" in path:
        return "movie"
    if has_episode_marker(name):
        return "series"

    category = normalized(group)
    # Provider group labels often contain words for multiple content types.
    if (category.startswith(("canais ", "canal ", "tv ", "ao vivo", "live "))
            or category in ("tv", "canais", "live", "televisao")):
        return "live"
    if SERIES_WORDS.search(category):
        if "filmes e series" not in category and "movies and series" not in category:
            return "series"
    if hint == "vod":
        return "movie" if VOD_FILE.search(url) else "other"
    if "filmes e series" in category or "movies and series" in category:
        return "movie" if VOD_FILE.search(url) else "other"
    if MOVIE_WORDS.search(category):
        return "movie"
    if VOD_FILE.search(url):
        return "movie"
    # An actual XMLTV channel ID is more reliable than a generic group.
    if tvg_id.strip():
        return "live"
    if path.endswith((".ts", ".m3u8")):
        return "live"
    return "other"


@dataclass(frozen=True)
class SeriesIdentity:
    identifier: str
    title: str
    season: int
    episode: int
    episode_title: str


def series_identity(name: str, series_id: str = "", series_title: str = "",
                    season_number: int = 0, episode_number: int = 0) -> SeriesIdentity:
    match = next((m for p in EPISODE_PATTERNS if (m := p.search(name))), None)
    lone = EPISODE_ONLY.search(name) if match is None else None
    marker = match or lone
    base = name[:marker.start()] if marker else name
    title = series_title.strip() or base
    title = QUALITY.sub(" ", title).strip(" -|.:")
    title = title.rstrip("([").strip()
    while TRAILING_QUALITY.search(title):
        title = TRAILING_QUALITY.sub("", title).strip(" -|")
    title = re.sub(r"\s+", " ", title).strip() or (f"Série {series_id}" if series_id else name)
    ident = "id:" + series_id if series_id else "title:" + normalized(title)
    season = season_number if season_number > 0 else (int(match.group(1)) if match else 1)
    number = episode_number if episode_number > 0 else (
        int(match.group(2)) if match else int(lone.group(1)) if lone else 0)
    suffix = name[marker.end():].strip(" -|.:)]") if marker else ""
    return SeriesIdentity(ident, title, season, number, suffix or name)


RECENT_GROUP = "__aurora_recent__"
RELEASES_GROUP = "__aurora_releases_2026__"
UHD_GROUP = "__aurora_4k__"
ADULT_GROUP = "__aurora_adult__"


def is_adult_group(group: str) -> bool:
    return bool(ADULT_WORDS.search(normalized(group)) or
                re.search(r"(?:\+\s*18|18\s*\+|\bnsfw\b)", group, re.I) or "🔞" in group)


def movie_category(group: str) -> str:
    if group in (RECENT_GROUP, RELEASES_GROUP, UHD_GROUP, ADULT_GROUP):
        return group
    if is_adult_group(group):
        return ADULT_GROUP
    clean = re.sub(r"[^\w +]", " ", group, flags=re.UNICODE)
    clean = re.sub(r"\s+", " ", clean).strip()
    key = re.sub(r"^(?:filmes?|movies?)\s+", "", normalized(clean))
    if key in ("update","updates","recentes","adicionado recentemente",
               "adicionados recentemente","recently added"):
        return RECENT_GROUP
    if "2026" in key and "lancamento" in key:
        return RELEASES_GROUP
    if re.search(r"\b(?:4k|uhd)\b",key):
        return UHD_GROUP
    names = {
        "documentario":"Documentários", "documentarios":"Documentários",
        "documentary":"Documentários", "documentaries":"Documentários",
        "ficcao":"Ficção científica","ficcao cientifica":"Ficção científica",
        "sci fi":"Ficção científica","science fiction":"Ficção científica",
        "drama":"Drama","acao":"Ação","comedia":"Comédia","animacao":"Animação",
        "terror":"Terror","romance":"Romance","suspense":"Suspense",
        "aventura":"Aventura",
    }
    return names.get(key, re.sub(r"(?i)^(?:filmes?|movies?)\s+", "", clean).strip() or group)


@dataclass(frozen=True)
class FootballDetails:
    competition: str
    home: str
    away: str


def football_details(title: str, category: str = "") -> FootballDetails | None:
    clean = normalized(title + " " + category)
    if NON_FOOTBALL.search(clean) or NON_MATCH_PROGRAMMES.search(clean):
        return None
    if not COMPETITIONS.search(clean):
        return None
    without_replay = re.sub(r"(?i)\s*[\[(](?:reprise|replay|ao vivo|live)[\])]\s*", " ", title)
    without_replay = re.sub(r"(?i)^(?:reprise|replay)\s*(?::|-)?\s+|\s+-\s+(?:reprise|replay)$","",without_replay)
    chunks = [x.strip() for x in re.split(r"[║|]+|\s+·\s+",without_replay) if x.strip()]
    main = next((x for x in chunks if VERSUS.search(x)), None)
    if main is None:
        return None
    m = VERSUS.search(main)
    home,away = main[:m.start()].strip(),main[m.end():].strip()
    competition = ""
    if ":" in home:
        prefix = home.rsplit(":",1)[0].strip()
        if COMPETITIONS.search(normalized(prefix)):
            competition = prefix
        home = home.rsplit(":",1)[-1].strip()
    if " - " in away:
        competition = away.split(" - ",1)[1].strip()
        away = away.split(" - ",1)[0].strip()
    if not competition:
        competition = next((s for s in chunks if not VERSUS.search(s) and COMPETITIONS.search(normalized(s))),"")
    if not competition and COMPETITIONS.search(normalized(category)):
        competition = category.strip()
    if not (2 <= len(home) <= 80 and 2 <= len(away) <= 80):
        return None
    if normalized(home) == normalized(away):
        return None
    return FootballDetails(competition,home,away)


def provider_api_endpoint(source: str, action: str) -> str | None:
    """Call *only* the URL's own provider, never forward playlist credentials elsewhere."""
    uri = urlsplit(source)
    if (uri.scheme not in ("http","https") or not uri.path.endswith("/get.php")
            or not uri.hostname):
        return None
    args = parse_qs(uri.query,keep_blank_values=True)
    username, password = args.get("username",[""])[0],args.get("password",[""])[0]
    if not username or not password:
        return None
    query = urlencode((("username",username),("password",password),("action",action)))
    return urlunsplit((uri.scheme,uri.netloc,uri.path[:-len("/get.php")]+"/player_api.php",query,""))
