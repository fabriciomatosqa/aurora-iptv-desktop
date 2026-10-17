"""Deterministic sports integration tests without network or IPTV credentials."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aurora_desktop.sports_data import (
    FIFA_BADGE, country_key, fetch_score_updates, fixture_key, league_slug,
    match_score, national_artwork, parse_scoreboard, parse_team_roster, roster_badge,
    safe_artwork, safe_epg_artwork, team_key,
)


def event_json(dt, *, state="in", completed=False, home="Fluminense",
               away="Santos", home_goals="2", away_goals="1", home_logo=True):
    def competitor(side, name, value):
        return {"homeAway": side, "type": "team", "score": value,
                "team": {"displayName": name, "shortDisplayName": name,
                         "logo": f"https://a.espncdn.com/i/teamlogos/soccer/500/{1 if side=='home' else 2}.png"
                           if home_logo else "https://bad.example/evil.png"}}
    return {
        "leagues": [{"logos": [{"href": "https://a.espncdn.com/i/leaguelogos/soccer/500/1.png"}]}],
        "events": [{"date": dt.isoformat(),
                    "competitions": [{
                        "competitors": [competitor("home", home, home_goals),
                                        competitor("away", away, away_goals)],
                        "status": {"displayClock": "65'", "type":
                                   {"state": state, "name": "STATUS_IN_PROGRESS",
                                    "completed": completed}},
                    }]}],
    }


def fixture(dt, **overrides):
    row = {"playlist_id": 7, "channel_id": "sports-01",
           "competition": "Campeonato Brasileiro", "home_team": "Fluminense",
           "away_team": "Santos", "start": dt.isoformat(),
           "broadcast": "unknown",
           "url": "https://iptv.example/get.php?username=secret&password=secret"}
    row.update(overrides)
    return row


def test_football_sources_are_strictly_mapped():
    assert league_slug("CONMEBOL Libertadores") == "conmebol.libertadores"
    assert league_slug("Brasileirão Série B") == "bra.2"
    assert league_slug("Campeonato Brasileiro") == "bra.1"
    assert league_slug("Premier League") == "eng.1"
    assert league_slug("Campeonato inexistente") is None
    assert country_key("Brasil") == "brazil"
    assert country_key("Argentina") == "argentina"
    assert team_key("Fluminense FC") == team_key("Fluminense")
    assert not safe_artwork("http://a.espncdn.com/insecure.png")
    assert not safe_artwork("https://evil.tld/espn.png")
    assert not safe_artwork("https://a.espncdn.com.evil.tld/logo.png")


def test_match_requires_two_exact_teams_and_compatible_date():
    date = datetime.now(timezone.utc) + timedelta(minutes=20)
    feed = parse_scoreboard(event_json(date), "bra.1", checked=12345)
    found = match_score(fixture(date), feed)
    assert found is not None
    assert found["home_score"] == 2 and found["away_score"] == 1
    assert found["score_clock"] == "65'"
    assert found["home_badge"].startswith("https://a.espncdn.com/")
    assert match_score(fixture(date, away_team="Corinthians"), feed) is None
    assert match_score(fixture(date + timedelta(hours=7)), feed) is None
    assert match_score(fixture(date), feed + feed) is None  # ambiguous
    assert match_score(fixture(date, competition="Libertadores"), feed) is None
    assert match_score(fixture(date, broadcast="replay"), feed) is None


def test_score_state_stale_and_no_fabricated_goals():
    date = datetime.now(timezone.utc) + timedelta(hours=2)
    future = parse_scoreboard(event_json(date, state="pre", home_goals="0",
                                          away_goals="0"), "bra.1")
    score = match_score(fixture(date), future)
    assert score["home_score"] is None and score["away_score"] is None
    finished = parse_scoreboard(event_json(date, state="post", completed=True), "bra.1")
    replay = match_score(fixture(date, broadcast="replay"), finished)
    assert replay["score_state"] == "finished"
    assert replay["home_score"] == 2
    assert safe_artwork(parse_scoreboard(event_json(date,home_logo=False),"bra.1")[0]["home"]["badge"]) == ""


def test_approved_country_urls_ported_from_android_without_guesses():
    date = datetime.now(timezone.utc)
    row = fixture(date, home_team="Brasil", away_team="Argentina",
                  competition="Copa do Mundo FIFA")
    art = national_artwork(row)
    assert art["competition_badge"] == FIFA_BADGE
    assert "/team/badge/" in art["home_badge"]
    assert "/team/badge/" in art["away_badge"]
    assert national_artwork(fixture(date)) == {}


def test_bounded_requests_do_not_expose_playlist_credentials():
    date = datetime.now(timezone.utc)
    row = fixture(date)
    addresses = []
    def fetch(url):
        addresses.append(url)
        return event_json(date)
    data = fetch_score_updates([row], fetch_json=fetch, request_limit=3)
    assert fixture_key(row) in data
    assert data[fixture_key(row)]["home_score"] == 2
    assert addresses and all("site.api.espn.com/apis/site/v2/sports/soccer/" in u for u in addresses)
    assert all("username" not in u and "password" not in u and "secret" not in u for u in addresses)
    empty = fetch_score_updates([row], fetch_json=lambda url: (_ for _ in ()).throw(OSError("offline")))
    assert empty == {}


def test_national_images_fallback_when_provider_unreachable():
    date = datetime.now(timezone.utc)
    row = fixture(date, home_team="Brasil", away_team="Argentina",
                  competition="Copa do Mundo FIFA")
    found = fetch_score_updates([row], fetch_json=lambda url: (_ for _ in ()).throw(OSError("offline")))
    assert found[fixture_key(row)]["home_badge"].startswith("https://r2.thesportsdb.com/")


def test_espn_team_roster_fills_logos_even_without_score():
    now = datetime.now(timezone.utc)
    fixture_row = fixture(now)
    payload = {"sports":[{"leagues":[{"teams":[
        {"team":{"displayName":"Fluminense FC","name":"Fluminense",
                 "logos":[{"href":"https://a.espncdn.com/i/teamlogos/soccer/500/123.png"}]}},
        {"team":{"displayName":"Santos FC","name":"Santos",
                 "logos":[{"href":"https://a.espncdn.com/i/teamlogos/soccer/500/456.png"}]}}
    ]}]}]}
    roster = parse_team_roster(payload)
    assert len(roster) == 2
    assert roster_badge("Fluminense", roster).endswith("/123.png")
    assert roster_badge("Santos", roster).endswith("/456.png")
    assert roster_badge("Flamengo", roster) == ""

    urls = []
    def mock_request(url):
        urls.append(url)
        return payload if url.endswith("/teams?limit=100") else {"events":[]}
    result = fetch_score_updates([fixture_row],fetch_json=mock_request)
    assert result[fixture_key(fixture_row)]["home_badge"].endswith("/123.png")
    assert result[fixture_key(fixture_row)]["away_badge"].endswith("/456.png")
    assert any("/teams?limit=100" in u for u in urls)
    assert len(urls) <= 12


def test_epg_logo_preserved_only_for_public_https_hosts():
    assert safe_epg_artwork("https://example.org/football/league.png").endswith("league.png")
    assert safe_epg_artwork("https://a.espncdn.com/logo.png").startswith("https://")
    assert safe_epg_artwork("https://127.0.0.1/private.png") == ""
    assert safe_epg_artwork("https://192.168.1.10/internal.png") == ""
    assert safe_epg_artwork("http://example.org/logo.png") == "http://example.org/logo.png"
    assert safe_epg_artwork("https://localhost/logo.png") == ""
    assert safe_epg_artwork("https://user:password@example.org/logo.png") == ""
