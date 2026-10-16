"""Regression tests against the provider layouts seen in real M3U lists."""
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import sqlite3

from aurora_desktop.core import parse_m3u, kind_of, parse_extinf
from aurora_desktop.catalog import LibraryV2, category_of, epg_from_header


def test_extinf_attributes_after_initial_comma():
    line = '#EXTINF:-1, tvg-id="globo.rj" tvg-logo="https://img.example/globo.png" group-title="Canais | Brasil",Globo RJ HD'
    meta = parse_extinf(line)
    assert meta["title"] == "Globo RJ HD"
    assert meta["group"] == "Canais | Brasil"
    assert meta["logo"].endswith("globo.png")
    assert meta["tvg_id"] == "globo.rj"


def test_extinf_preserves_comma_inside_name_and_quoted_attribute():
    line = '#EXTINF:-1 tvg-logo="https://images.example/?tag=ação,aventura" group-title="Filmes | Ação",Lado A, Lado B (2026)'
    meta = parse_extinf(line)
    assert meta["title"] == "Lado A, Lado B (2026)"
    assert meta["logo"].endswith("aventura")


def test_realistic_mixed_playlist_classification():
    fixture = """#EXTM3U
#EXTINF:-1 tvg-id="globo.rj" group-title="Ao Vivo" tvg-logo="https://img.example/g.png",Globo Rio HD
http://provider.example/live/user/pass/11.ts
#EXTINF:-1, tvg-logo="https://img.example/horror.png" group-title="● Terror",Um Filme de Terror (2025)
http://provider.example/movie/user/pass/22.mp4
#EXTINF:-1 tvg-logo="https://img.example/drama.png" group-title="Drama",Uma Vida (2025)
http://provider.example/user/pass/33.mkv
#EXTINF:-1 tvg-logo="https://img.example/serie.png" group-title="Séries | Ação",A Teia S01E10
http://provider.example/series/user/pass/44.mp4
#EXTINF:-1, group-title="Séries | Romance",Amores S02E01
http://provider.example/user/pass/55.mp4
"""
    parsed = list(parse_m3u(fixture.splitlines()))
    assert [(e.kind, e.title) for e in parsed] == [
        ("live", "Globo Rio HD"),
        ("movie", "Um Filme de Terror (2025)"),
        ("movie", "Uma Vida (2025)"),
        ("series", "A Teia S01E10"),
        ("series", "Amores S02E01"),
    ]
    assert [category_of(e.kind, e.title, e.group_name) for e in parsed] == [
        "Globo", "Terror", "Drama", "Ação", "Romance"
    ]


def test_reclassification_of_installed_beta_catalog_preserves_favorites(tmp_path):
    db = tmp_path / "catalog.db"
    lib = LibraryV2(db)
    pid = lib.add_playlist("Origem",str(tmp_path / "old.m3u"))
    with lib.connect() as conn:
        conn.execute("""INSERT INTO items
            (playlist_id,key,title,url,group_name,kind,logo,series_name,season,episode,category)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",(
            pid, "movie-id", "tvg-logo=\"https://img.example/a.jpg\" group-title=\"● Terror\",Susto (2025)",
            "https://example.com/movie/u/p/54.mp4", "", "live", "", "",None,None,
            'tvg-logo="https://img.example/a.jpg" group-title="● Terror",Susto (2025)'
        ))
        conn.execute("INSERT INTO classification_version VALUES (?,2)",(pid,))
    lib.set_favorite(pid,"item:movie-id","live","Susto (2025)",True)
    lib.save_progress(pid,"movie-id",333)
    lib.ensure_categories(pid)
    found=lib.browse(pid,"movie","Terror")
    assert len(found)==1
    assert found[0]["title"]=="Susto (2025)"
    assert found[0]["logo"]=="https://img.example/a.jpg"
    assert lib.is_favorite(pid,"item:movie-id")
    assert lib.get_progress(pid,"movie-id")==333


def test_series_genre_takes_precedence_over_platform():
    assert category_of("series","Um Seriado","Séries | Netflix | Romance") == "Romance"
    assert category_of("series","Um Seriado","Séries | HBO") == "Max / HBO"


def test_xtream_guide_url_discovery_no_remote_access(tmp_path):
    # No private credentials are stored in the source code; synthetic fixture.
    path = tmp_path / "iptv.m3u"
    path.write_text("#EXTM3U\n",encoding="utf-8")
    assert epg_from_header(str(path)) == ""
    url = epg_from_header("https://example.org/get.php?username=demo&password=not-real&type=m3u_plus")
    parsed=urlparse(url)
    assert parsed.path == "/xmltv.php"
    assert parse_qs(parsed.query) == {"username":["demo"], "password":["not-real"]}


def test_football_fallback_only_real_live_sports_channels(tmp_path):
    lib=LibraryV2(tmp_path / "football.db")
    pid=lib.add_playlist("Teste",str(tmp_path / "x.m3u"))
    m3u=tmp_path / "x.m3u"
    m3u.write_text("""#EXTM3U
#EXTINF:-1 group-title="Esportes",SporTV FHD
https://example.org/live/u/p/1.ts
#EXTINF:-1 group-title="Filmes | Ação",Racing (2025)
https://example.org/movie/u/p/2.mp4
#EXTINF:-1 group-title="Canais",Globo RJ
https://example.org/live/u/p/3.ts
""",encoding="utf-8")
    lib.import_playlist(pid)
    channels=lib.sport_channels(pid)
    assert [r["title"] for r in channels] == ["SporTV FHD"]
    assert all(r["kind"]=="football_channel" for r in channels)
