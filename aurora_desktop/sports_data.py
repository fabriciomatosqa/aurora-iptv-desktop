"""Football scores and team artwork adapted from AURORA IPTV Android.

Only public fixture metadata (league and date) is sent to data providers.
Never send M3U URLs, user credentials or IPTV playback addresses.
Artwork rights and provider access must be cleared before commercial distribution.
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import re
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .android_rules import normalized

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"
FIFA_BADGE = "https://a.espncdn.com/i/leaguelogos/soccer/500/4.png"

# Explicitly verified in the Android source. These are reference URLs, not
# a blanket grant of rights for redistribution or publication.
NATIONAL_BADGES = {
    "brazil": "https://r2.thesportsdb.com/images/media/team/badge/jl6dip1726167280.png",
    "argentina": "https://r2.thesportsdb.com/images/media/team/badge/3zplhu1726167477.png",
    "usa": "https://r2.thesportsdb.com/images/media/team/badge/21f0oi1597948195.png",
    "spain": "https://r2.thesportsdb.com/images/media/team/badge/ncgqyr1726166942.png",
}
COUNTRY_ALIASES = {
    "brazil": {"brasil", "brazil", "bra"},
    "argentina": {"argentina", "arg"},
    "usa": {"usa", "eua", "estados unidos", "united states", "us", "united states of america"},
    "spain": {"espanha", "espana", "spain", "esp"},
}
ALLOWED_IMAGE_HOSTS = frozenset({"a.espncdn.com", "r2.thesportsdb.com"})

# Matches the competition families used in the Android application.
LEAGUES = (
    (("brasileirao serie b", "campeonato brasileiro serie b", "brasileiro serie b"), "bra.2"),
    (("brasileirao", "brasileiro", "campeonato brasileiro"), "bra.1"),
    (("libertadores",), "conmebol.libertadores"),
    (("sul americana", "sulamericana", "sudamericana"), "conmebol.sudamericana"),
    (("copa do brasil",), "bra.copa_do_brazil"),
    (("copa do nordeste",), "bra.copa_do_nordeste"),
    (("premier league", "campeonato ingles"), "eng.1"),
    (("la liga", "laliga", "campeonato espanhol"), "esp.1"),
    (("bundesliga", "campeonato alemao"), "ger.1"),
    (("serie a italiana", "campeonato italiano", "italian serie a"), "ita.1"),
    (("ligue 1", "campeonato frances"), "fra.1"),
    (("primeira liga", "campeonato portugues"), "por.1"),
    (("champions league", "liga dos campeoes"), "uefa.champions"),
    (("europa league", "liga europa"), "uefa.europa"),
    (("conference league",), "uefa.europa.conf"),
    (("copa do mundo feminina", "women s world cup"), "fifa.wwc"),
    (("copa do mundo", "world cup", "fifa world"), "fifa.world"),
    (("copa america feminina",), "conmebol.america.femenina"),
    (("copa america",), "conmebol.america"),
    (("eurocopa feminina",), "uefa.weuro"),
    (("eurocopa", "european championship"), "uefa.euro"),
    (("amistoso internacional feminino",), "fifa.friendly.w"),
    (("amistoso internacional", "international friendly", "amistosos de selecoes"), "fifa.friendly"),
    (("eliminatorias conmebol", "eliminatorias sul americanas"), "fifa.worldq.conmebol"),
    (("eliminatorias uefa",), "fifa.worldq.uefa"),
)
COMPONENT_PREFIXES = ("clube de regatas ", "clube atletico ", "clube ", "club ", "cr ", "ca ", "ec ", "sc ", "fc ", "cf ", "ac ")
COMPONENT_SUFFIXES = (" fc", " cf", " sc", " ec", " ac")


def league_slug(competition: str) -> str | None:
    name = normalized(competition)
    for parts, slug in LEAGUES:
        if any(part in name for part in parts):
            return slug
    return None


def country_key(name: str) -> str | None:
    n = normalized(name)
    for key, labels in COUNTRY_ALIASES.items():
        if n in labels:
            return key
    return None


def team_key(name: str) -> str:
    key = country_key(name)
    if key:
        return "country:" + key
    n = normalized(name)
    for prefix in COMPONENT_PREFIXES:
        if n.startswith(prefix):
            n = n[len(prefix):]
            break
    for suffix in COMPONENT_SUFFIXES:
        if n.endswith(suffix):
            n = n[:-len(suffix)]
            break
    aliases = {"flamengo rj": "flamengo", "cr flamengo": "flamengo",
               "do flamengo": "flamengo",
               "fluminense rj": "fluminense", "fluminense football club": "fluminense",
               "real madrid cf": "real madrid",
               "sport club corinthians paulista": "corinthians",
               "sport club internacional": "internacional",
               "gremio foot ball porto alegrense": "gremio",
               "manchester utd": "manchester united"}
    return re.sub(r"[^a-z0-9]", "", aliases.get(n, n))


def safe_artwork(url: str) -> str:
    try:
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname in ALLOWED_IMAGE_HOSTS and not parsed.username:
            return url
    except (ValueError, TypeError):
        pass
    return ""


def fixture_key(row: dict) -> str:
    return "|".join(str(row.get(k, "")) for k in
                    ("playlist_id", "channel_id", "start", "home_team", "away_team", "competition"))


def _date(value: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (TypeError, ValueError, AttributeError):
        return None


def _read_json(url: str) -> dict:
    if not url.startswith(ESPN + "/"):
        raise ValueError("Unexpected score data host")
    request = Request(url, headers={"User-Agent": "AuroraIPTVDesktop/0.6", "Accept": "application/json"})
    with urlopen(request, timeout=7) as response:
        if response.status != 200:
            raise ValueError("Sports API unavailable")
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Oversized sports response")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Invalid sports response")
    return result


def _state(status: dict) -> str:
    state = status.get("type") or {}
    name = str(state.get("name", "")).lower()
    value = state.get("state")
    if "cancel" in name:
        return "cancelled"
    if any(word in name for word in ("postpon", "suspend", "abandon")):
        return "postponed"
    if "half" in name:
        return "halftime"
    if state.get("completed") and value == "post":
        return "finished"
    if value == "in":
        return "live"
    if value == "pre":
        return "scheduled"
    return "unknown"


def _team(row: dict) -> dict:
    t = row.get("team") or {}
    names = [t.get(k) for k in ("displayName", "shortDisplayName", "name", "location", "abbreviation")]
    names = [n for n in names if isinstance(n, str) and n.strip()]
    logos = t.get("logos") or []
    logo = safe_artwork(t.get("logo", "") or (logos[0].get("href", "") if logos else ""))
    try:
        score = int(row.get("score", {}).get("displayValue", row.get("score", {}).get("value"))) if isinstance(row.get("score"), dict) else int(row.get("score"))
        if not 0 <= score <= 99:
            score = None
    except (ValueError, TypeError):
        score = None
    return {"names": names, "badge": logo, "score": score}


def parse_scoreboard(payload: dict, slug: str, checked: float | None = None) -> list[dict]:
    checked = time.time() if checked is None else checked
    logos = ((payload.get("leagues") or [{}])[0].get("logos") or [{}])
    competition_badge = safe_artwork(logos[0].get("href", ""))
    events = []
    for item in payload.get("events", []):
        try:
            contest = item["competitions"][0]
            competitors = contest["competitors"]
            home = next(row for row in competitors if row.get("homeAway") == "home")
            away = next(row for row in competitors if row.get("homeAway") == "away")
            d = _date(item.get("date", ""))
            if not d:
                continue
            state = _state(contest.get("status") or item.get("status") or {})
            h, a = _team(home), _team(away)
            if not h["names"] or not a["names"]:
                continue
            clock = (contest.get("status") or item.get("status") or {}).get("displayClock", "")
            events.append({"league": slug, "kickoff": d, "home": h, "away": a,
                           "state": state, "clock": str(clock), "checked": checked,
                           "competition_badge": competition_badge})
        except (KeyError, ValueError, TypeError, StopIteration, IndexError):
            continue
    return events


def match_score(row: dict, events: list[dict]) -> dict | None:
    slug = league_slug(row.get("competition", ""))
    kickoff = _date(row.get("start", ""))
    h = team_key(row.get("home_team", ""))
    a = team_key(row.get("away_team", ""))
    if not slug or not kickoff or not h or not a or h == a:
        return None
    matches = []
    for e in events:
        if e["league"] != slug or abs((e["kickoff"] - kickoff).total_seconds()) > 6 * 3600:
            continue
        home_keys = {team_key(n) for n in e["home"]["names"]}
        away_keys = {team_key(n) for n in e["away"]["names"]}
        if h in home_keys and a in away_keys:
            matches.append((e, e["home"], e["away"]))
        elif h in away_keys and a in home_keys:
            matches.append((e, e["away"], e["home"]))
    # Never attach a potentially wrong score or crest to ambiguous fixtures.
    if len(matches) != 1:
        return None
    e, home, away = matches[0]
    live = e["state"] in ("live", "halftime")
    if row.get("broadcast") == "replay" and e["state"] != "finished":
        return None
    home_badge = home["badge"]
    away_badge = away["badge"]
    national = country_key(row.get("home_team", "")) and country_key(row.get("away_team", ""))
    if national:
        home_badge = NATIONAL_BADGES.get(country_key(row["home_team"]), home_badge)
        away_badge = NATIONAL_BADGES.get(country_key(row["away_team"]), away_badge)
    return {
        "home_badge": safe_artwork(home_badge),
        "away_badge": safe_artwork(away_badge),
        "competition_badge": FIFA_BADGE if national else e["competition_badge"],
        "home_score": home["score"] if e["state"] in ("live", "halftime", "finished") else None,
        "away_score": away["score"] if e["state"] in ("live", "halftime", "finished") else None,
        "score_state": e["state"], "score_clock": e["clock"] if live else "",
        "score_checked": e["checked"],
    }


def national_artwork(row: dict) -> dict:
    h, a = country_key(row.get("home_team", "")), country_key(row.get("away_team", ""))
    if h and a:
        return {"home_badge": NATIONAL_BADGES.get(h, ""),
                "away_badge": NATIONAL_BADGES.get(a, ""),
                "competition_badge": FIFA_BADGE}
    return {}


def parse_team_roster(payload: dict) -> list[dict]:
    """Read ESPN team roster without guessing club identities."""
    sports = payload.get("sports") or []
    leagues = (sports[0].get("leagues") or []) if sports else []
    roster = (leagues[0].get("teams") or []) if leagues else []
    result = []
    for item in roster:
        team = item.get("team") or {}
        names = [team.get(k) for k in ("displayName", "shortDisplayName", "name", "nickname", "abbreviation")]
        names = [n for n in names if isinstance(n, str) and n.strip()]
        logos = team.get("logos") or []
        logo = safe_artwork((logos[0].get("href") or "") if logos else team.get("logo", ""))
        if names and logo:
            result.append({"names": names, "badge": logo})
    return result


def roster_badge(name: str, roster: list[dict]) -> str:
    key = team_key(name)
    if not key:
        return ""
    matches = {row["badge"] for row in roster
               if key in {team_key(alias) for alias in row["names"]} and row["badge"]}
    return next(iter(matches)) if len(matches) == 1 else ""


def fetch_score_updates(rows: list[dict], fetch_json=None, *, request_limit: int = 12) -> dict[str, dict]:
    """Bounded lookup for visible fixtures; failure never breaks the catalogue.

    Missing data is *not* filled with guesses. Call in a worker, not in Qt GUI.
    """
    getter = fetch_json or _read_json
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    now = datetime.now(timezone.utc)
    for row in rows[:70]:
        slug, when = league_slug(row.get("competition", "")), _date(row.get("start", ""))
        if not slug or not when:
            continue
        if not now - timedelta(days=7) <= when <= now + timedelta(days=14):
            continue
        # UTC scoreboard date avoids most Brazilian timezone mismatch.
        days = {when.strftime("%Y%m%d")}
        if abs((when - now).total_seconds()) <= 86400:
            days.add(now.strftime("%Y%m%d"))
        for day in days:
            groups[(slug, day)].append(row)
    if not groups:
        return {fixture_key(row): national_artwork(row) for row in rows if national_artwork(row)}
    results: list[dict] = []
    schedule = sorted(groups, key=lambda key: (key[1] != now.strftime("%Y%m%d"), key[1]))[:max(0, request_limit)]

    def download(slug: str, day: str) -> list[dict]:
        url = f"{ESPN}/{slug}/scoreboard?dates={day}&limit=100"
        return parse_scoreboard(getter(url), slug)

    if schedule:
        # At most three simultaneous requests. A slow ESPN endpoint never
        # freezes the GUI or keeps a 12-league refresh running for 84 seconds.
        with ThreadPoolExecutor(max_workers=min(3, len(schedule))) as pool:
            tasks = [pool.submit(download, slug, day) for slug, day in schedule]
            for task in as_completed(tasks):
                try:
                    results.extend(task.result())
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                    continue
    # Team logos are often available even when a specific fixture is absent
    # from the scoreboard. Use the same ESPN teams endpoint as Android.
    # Keep the combined request ceiling at 12 URLs per refresh.
    remaining = max(0, 12 - len(schedule))
    leagues = list(dict.fromkeys(league_slug(row.get("competition", ""))
                                 for row in rows if league_slug(row.get("competition", ""))))
    rosters = {}
    if remaining and leagues:
        def download_roster(slug):
            return parse_team_roster(getter(f"{ESPN}/{slug}/teams?limit=100"))
        with ThreadPoolExecutor(max_workers=min(3, remaining, len(leagues))) as pool:
            tasks = {pool.submit(download_roster, slug): slug for slug in leagues[:remaining]}
            for task in as_completed(tasks):
                try:
                    rosters[tasks[task]] = task.result()
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                    continue
    updates = {}
    for row in rows:
        artwork = national_artwork(row)
        score = match_score(row, results)
        if score:
            artwork.update(score)
        roster = rosters.get(league_slug(row.get("competition", "")), [])
        if roster:
            if not artwork.get("home_badge"):
                artwork["home_badge"] = roster_badge(row.get("home_team", ""), roster)
            if not artwork.get("away_badge"):
                artwork["away_badge"] = roster_badge(row.get("away_team", ""), roster)
        if artwork:
            updates[fixture_key(row)] = artwork
    return updates
