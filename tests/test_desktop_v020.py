from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from aurora_desktop.catalog import (
    LibraryV2, category_of, channel_base, epg_from_header, xmltv_time
)


def test_live_channel_families():
    assert channel_base("Globo RJ HD") == "Globo"
    assert channel_base("REDE GLOBO SP 4K") == "Globo"
    assert channel_base("SBT HD") == "SBT"
    assert channel_base("ESPN 2 FHD") == "ESPN"
    assert channel_base("Canal Especial MG FHD") == "Canal Especial"


def test_movie_genres_and_series_provider():
    assert category_of("movie", "Filme", "Filmes | Ação") == "Ação"
    assert category_of("movie", "Filme", "Comédia Romântica") == "Comédia"
    assert category_of("movie", "Filme", "TERROR") == "Terror"
    assert category_of("series", "Série", "Series | Netflix") == "Netflix"
    assert category_of("series", "Série", "Séries | Prime Video") == "Prime Video"
    assert category_of("series", "Série", "") == "Sem plataforma identificada"


def test_upgrade_keeps_old_playlist_and_favorites(tmp_path):
    path = tmp_path / "legacy.db"
    # Simulate a database written by the previous 0.1.0 app.
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE playlists (id INTEGER PRIMARY KEY,name TEXT NOT NULL,
            source TEXT NOT NULL,updated_at TEXT);
        CREATE TABLE items (playlist_id INTEGER NOT NULL,key TEXT NOT NULL,
            title TEXT NOT NULL,url TEXT NOT NULL,group_name TEXT NOT NULL,
            kind TEXT NOT NULL,logo TEXT NOT NULL,series_name TEXT NOT NULL,
            season INTEGER,episode INTEGER,PRIMARY KEY(playlist_id,key));
        CREATE TABLE favorites (playlist_id INTEGER NOT NULL,key TEXT NOT NULL,
            kind TEXT NOT NULL,title TEXT NOT NULL,PRIMARY KEY(playlist_id,key));
        CREATE TABLE progress (playlist_id INTEGER NOT NULL,key TEXT NOT NULL,
            seconds INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(playlist_id,key));
        INSERT INTO playlists VALUES(1,'Minha Lista','https://example.com/get.php?token=private',NULL);
        INSERT INTO items VALUES(1,'key-1','Globo RJ HD','https://example.com/live/1',
            'Ao Vivo','live','','',NULL,NULL);
        INSERT INTO favorites VALUES(1,'item:key-1','live','Globo RJ HD');
        INSERT INTO progress (playlist_id,key,seconds) VALUES (1,'key-1',125);
    """)
    db.commit()
    db.close()
    lib = LibraryV2(path)
    lib.ensure_categories(1)
    assert lib.playlists()[0]["name"] == "Minha Lista"
    assert lib.is_favorite(1, "item:key-1")
    assert lib.get_progress(1,"key-1") == 125
    assert lib.categories(1,"live") == [{"title":"Globo","total":1}]
    assert lib.items(1,"live")[0]["tvg_id"] == ""


def test_scroll_categories_and_series(tmp_path):
    lib = LibraryV2(tmp_path / "new.sqlite")
    f = tmp_path / "test.m3u"
    content = ['#EXTM3U url-tvg="https://example.org/epg.xml"']
    for i in range(180):
        content += [
            f'#EXTINF:-1 group-title="Filmes | Ação",Filme {i:03}',
            f'https://example.org/movie/{i}',
        ]
    content += [
        '#EXTINF:-1 group-title="Séries | Netflix" tvg-logo="https://example.org/a.png",Minha Série S01E01',
        'https://example.org/series/a/1',
        '#EXTINF:-1 group-title="Séries | Netflix",Minha Série S01E02',
        'https://example.org/series/a/2',
    ]
    f.write_text("\n".join(content), encoding="utf-8")
    pid = lib.add_playlist("Casa",str(f))
    assert lib.import_playlist(pid) == 182
    assert lib.get_epg_url(pid) == "https://example.org/epg.xml"
    assert len(lib.browse(pid,"movie","Ação",limit=60)) == 60
    assert len(lib.browse(pid,"movie","Ação",limit=60,offset=120)) == 60
    assert len(lib.browse(pid,"series","Netflix")) == 1
    assert lib.browse(pid,"series","Netflix")[0]["episodes"] == 2


def test_xmltv_parsing_links_playable_channel(tmp_path):
    lib = LibraryV2(tmp_path / "player.db")
    m3u = tmp_path / "live.m3u"
    m3u.write_text(
        '#EXTM3U\n#EXTINF:-1 tvg-id="globo.rj" group-title="Canais",Globo RJ HD\n'
        'https://example.org/live/rj\n', encoding="utf-8"
    )
    pid = lib.add_playlist("Casa",str(m3u))
    lib.import_playlist(pid)
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    end = start + timedelta(hours=2)
    to_xml = lambda dt: dt.strftime("%Y%m%d%H%M%S +0000")
    epg = tmp_path / "guide.xml"
    epg.write_text(
        f'<tv><programme start="{to_xml(start)}" stop="{to_xml(end)}" channel="globo.rj">'
        '<title>Flamengo x Vasco</title><desc>Futebol ao vivo</desc>'
        '</programme></tv>', encoding="utf-8"
    )
    lib.set_epg_url(pid,str(epg))
    assert lib.import_football(pid) == 1
    games = lib.football(pid)
    assert len(games) == 1
    assert games[0]["channel_title"] == "Globo RJ HD"
    assert games[0]["url"] == "https://example.org/live/rj"
    assert ":" in datetime.fromisoformat(games[0]["start"]).strftime("%H:%M")


def test_no_invented_match_from_nonfootball_guide(tmp_path):
    lib = LibraryV2(tmp_path / "player.db")
    pid = lib.add_playlist("Guide",str(tmp_path / "list.m3u"))
    epg = tmp_path / "guide.xml"
    start = (datetime.now(timezone.utc)+timedelta(hours=1)).strftime("%Y%m%d%H%M%S +0000")
    epg.write_text(
        f'<tv><programme start="{start}" channel="news"><title>Jornal da Noite</title>'
        '<desc>Notícias</desc></programme></tv>', encoding="utf-8"
    )
    lib.set_epg_url(pid,str(epg))
    assert lib.import_football(pid) == 0
    assert lib.football(pid) == []
