"""Regressions that old compile-only tests did not cover.

Keep playlist secrets and personal file paths out of these fixtures.
"""
from datetime import datetime, timedelta, timezone

from aurora_desktop.catalog import LibraryV2


def test_refresh_merges_new_catalog_without_losing_existing_items(tmp_path, monkeypatch):
    path = tmp_path / "demo.m3u"
    path.write_text(
        '#EXTM3U\n#EXTINF:-1 group-title="Filmes | Ação",Primeiro\n'
        'https://example.org/movie/1.mp4\n', encoding="utf8"
    )
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_category_kinds", lambda _: {})
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_series_posters", lambda _: {})
    lib = LibraryV2(tmp_path / "library.db")
    pid = lib.add_playlist("Minha lista",str(path))
    assert lib.import_playlist(pid) == 1
    original = lib.items(pid,"movie")[0]
    lib.set_favorite(pid,"item:"+original["key"],"movie",original["title"],True)
    lib.save_progress(pid,original["key"],344)
    path.write_text(
        '#EXTM3U\n#EXTINF:-1 group-title="Filmes | Terror",Segundo\n'
        'https://example.org/movie/2.mp4\n', encoding="utf8"
    )
    assert lib.import_playlist(pid) == 1
    rows=lib.items(pid,"movie")
    assert {r["title"] for r in rows} == {"Primeiro","Segundo"}
    assert lib.is_favorite(pid,"item:"+original["key"])
    assert lib.get_progress(pid,original["key"]) == 344


def test_football_shows_only_playable_matches_and_expires_old_events(tmp_path):
    lib=LibraryV2(tmp_path / "local.db")
    path=tmp_path / "ch.m3u"
    path.write_text(
        '#EXTM3U\n#EXTINF:-1 tvg-id="globo.test" group-title="Ao Vivo",Globo HD\n'
        'https://example.org/live/1.ts\n',encoding="utf-8"
    )
    pid=lib.add_playlist("Casa",str(path))
    lib.import_playlist(pid)
    now=datetime.now(timezone.utc)
    recent=(now+timedelta(hours=1)).isoformat()
    finished=(now-timedelta(hours=4)).isoformat()
    with lib.connect() as db:
        db.executemany("""INSERT INTO football_events
            (playlist_id,channel_id,start,end,title,competition,broadcast)
            VALUES (?,?,?,?,?,?,?)""",[
            (pid,"globo.test",recent,(now+timedelta(hours=3)).isoformat(),
             "Flamengo x Vasco","Brasileirão","unknown"),
            (pid,"not-found",recent,(now+timedelta(hours=3)).isoformat(),
             "Botafogo x Fluminense","Brasileirão","unknown"),
            (pid,"globo.test",finished,(now-timedelta(hours=2)).isoformat(),
             "Fora do prazo x Outro","Brasileirão","unknown")
        ])
    rows=lib.football(pid)
    assert len(rows)==1 and rows[0]["title"]=="Flamengo x Vasco"
    assert rows[0]["channel_title"]=="Globo HD"
    assert lib.football_categories(pid)==[{"title":"Brasileirão","total":1}]


def test_import_guide_rejects_american_football_even_with_match_title(tmp_path):
    playlist=tmp_path/"playlist.m3u"
    playlist.write_text(
        '#EXTM3U\n#EXTINF:-1 tvg-id="sports" group-title="Ao Vivo",Canal esporte\n'
        'https://example.org/live/sports.ts\n',encoding="utf8"
    )
    lib=LibraryV2(tmp_path/"db.sqlite")
    pid=lib.add_playlist("Teste",str(playlist))
    lib.import_playlist(pid)
    kickoff=(datetime.now(timezone.utc)+timedelta(hours=2)).strftime("%Y%m%d%H%M%S +0000")
    end=(datetime.now(timezone.utc)+timedelta(hours=4)).strftime("%Y%m%d%H%M%S +0000")
    xml=tmp_path/"guide.xml"
    xml.write_text(
        '<tv>'
        f'<programme channel="sports" start="{kickoff}" stop="{end}">'
        '<title>Alabama x East Carolina</title>'
        '<category>Futebol americano universitário</category>'
        '</programme>'
        f'<programme channel="sports" start="{kickoff}" stop="{end}">'
        '<title>Flamengo x Vasco</title><category>Brasileirão</category>'
        '</programme>'
        '</tv>',encoding="utf8"
    )
    lib.set_epg_url(pid,str(xml))
    assert lib.import_football(pid)==1
    assert lib.football(pid)[0]["title"]=="Flamengo x Vasco"
