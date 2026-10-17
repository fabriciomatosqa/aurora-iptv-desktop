"""Classification regression suite based on structural patterns of a large
M3U provided for authorized analysis. All streams, IDs and accounts below are
synthetic: never copy private playlist URLs into the repository.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aurora_desktop.core import kind_of
from aurora_desktop.catalog import LibraryV2
from aurora_desktop.provider import get_provider_category_kinds


def _line(title: str, group: str, url: str, item_id: str,
          tvg_id: str = "") -> str:
    return (f'#EXTINF:-1 xui-id="{item_id}" tvg-id="{tvg_id}" '
            f'group-title="{group}",{title}\n{url}\n')


def _write(path: Path, rows) -> None:
    path.write_text("#EXTM3U\n"+"".join(rows),encoding="utf-8")


def test_classification_respects_stream_evidence_before_group_labels():
    assert kind_of("Canais 24H | Séries", "TV HD",
                   "https://example.invalid/play/opaque/ts")=="live"
    assert kind_of("Filmes e Séries", "Noticiário",
                   "https://example.invalid/play/opaque",tvg_id="channel.epg")=="live"
    assert kind_of("Legendadas", "História S01E02",
                   "https://example.invalid/play/opaque",provider_kind="movie")=="series"
    assert kind_of("Outras produtoras", "História S02E01",
                   "https://example.invalid/play/opaque")=="series"
    assert kind_of("Legendados ✔", "História (2025)",
                   "https://example.invalid/play/opaque")=="movie"
    assert kind_of("Canais 24H | Cinema", "Canal contínuo",
                   "https://example.invalid/play/opaque/ts")=="live"
    assert kind_of("Grupo indefinido", "Conteúdo indefinido",
                   "https://example.invalid/play/opaque")=="uncategorized"


def test_reclassify_existing_bad_categories_and_preserve_progress(tmp_path,monkeypatch):
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_category_kinds",
                        lambda _: {"legendadas":"movie","canais 24h series":"series"})
    m3u=tmp_path/"data.m3u"
    _write(m3u,[
        _line("Uma série S01E01","Legendadas",
              "https://example.invalid/play/episode-a","101"),
        _line("Uma série S01E02","Legendadas",
              "https://example.invalid/play/episode-b","102"),
        _line("Uma série S02E01","Legendadas",
              "https://example.invalid/play/episode-c","103"),
        _line("Canal infantil","Canais 24H | Series",
              "https://example.invalid/play/channel/ts","201"),
        _line("Longa-metragem (2025)","Legendados ✔",
              "https://example.invalid/play/movie","301"),
        _line("Sem pistas","Variados",
              "https://example.invalid/play/unknown","401"),
    ])
    lib=LibraryV2(tmp_path/"database.db")
    pid=lib.add_playlist("Teste",str(m3u))
    assert lib.import_playlist(pid)==6
    shows=lib.browse(pid,"series",None)
    assert len(shows)==1 and shows[0]["title"]=="Uma série"
    assert shows[0]["episodes"]==3
    assert len(lib.browse(pid,"live",None))==1
    assert len(lib.browse(pid,"movie",None))==1
    unknown=lib.browse(pid,"uncategorized",None)
    assert len(unknown)==1
    episode=lib.episodes(pid,"Uma série")[0]
    lib.save_progress(pid,episode["key"],147)
    lib.set_favorite(pid,"item:"+episode["key"],"series",episode["title"],True)
    lib.set_kind_override(pid,unknown[0]["key"],"movie")
    lib.ensure_categories(pid,force=True)
    assert lib.get_progress(pid,episode["key"])==147
    assert lib.is_favorite(pid,"item:"+episode["key"])
    assert any(r["key"]==unknown[0]["key"] for r in lib.browse(pid,"movie",None))
    lib.ensure_categories(pid,force=True)
    with lib.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]==6
        assert db.execute("SELECT version FROM classification_version WHERE playlist_id=?",(pid,)).fetchone()[0]==7


def test_changed_hls_mpegts_urls_keep_favorites_progress_and_no_duplicates(tmp_path):
    source=tmp_path/"data.m3u"
    lib=LibraryV2(tmp_path/"catalog.db")
    pid=lib.add_playlist("Minha lista",str(source))
    first=[
        _line(f"Filme de teste {index}","Filmes",
              f"https://cdn.invalid/play/film-{index}",str(index))
        for index in range(1,61)
    ]
    _write(source,first)
    assert lib.import_playlist(pid)==60
    target=lib.browse(pid,"movie",None)[0]
    target_key=target["key"]
    target_title=target["title"]
    lib.save_progress(pid,target_key,357)
    lib.set_favorite(pid,"item:"+target_key,"movie",target_title,True)
    # The provider changes stream URLs but maintains unique xui-id values.
    second=[
        _line(f"Filme de teste {index}","Filmes",
              f"https://cdn.invalid/play/new-film-{index}",str(index))
        for index in range(1,61)
    ]
    _write(source,second)
    assert lib.import_playlist(pid)==60
    lib.ensure_categories(pid)
    with lib.connect() as db:
        items=db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]
        changed=db.execute("SELECT url FROM items WHERE playlist_id=? AND key=?",
                          (pid,target_key)).fetchone()
    assert items==60
    assert "new-film-" in changed["url"]
    assert lib.get_progress(pid,target_key)==357
    assert lib.is_favorite(pid,"item:"+target_key)
    assert lib.import_playlist(pid)==60
    with lib.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]==60


def test_duplicate_provider_ids_are_not_force_matched(tmp_path):
    source=tmp_path/"dup.m3u"
    lib=LibraryV2(tmp_path/"dup.db")
    pid=lib.add_playlist("Teste",str(source))
    _write(source,[
        _line("A","Filmes","https://cdn.invalid/play/a","same-id"),
        _line("B","Filmes","https://cdn.invalid/play/b","same-id"),
    ])
    lib.import_playlist(pid)
    _write(source,[
        _line("A","Filmes","https://cdn.invalid/play/new-a","same-id"),
        _line("B","Filmes","https://cdn.invalid/play/new-b","same-id"),
    ])
    lib.import_playlist(pid)
    with lib.connect() as db:
        # Without a unique provider ID, keep both distinct URLs and don't
        # arbitrarily move one favorite to the wrong entry.
        assert db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]==4


def test_healthy_refresh_prunes_stale_entries_but_short_response_does_not(tmp_path):
    source=tmp_path/"refresh.m3u"
    lib=LibraryV2(tmp_path/"refresh.db")
    pid=lib.add_playlist("Teste",str(source))
    _write(source,[
        _line(f"Filme {i}","Filmes",f"https://cdn.invalid/play/{i}",str(i))
        for i in range(1,101)
    ])
    lib.import_playlist(pid)
    # Near-complete refresh: stale entry removed safely.
    _write(source,[
        _line(f"Filme {i}","Filmes",f"https://cdn.invalid/play/{i}",str(i))
        for i in range(1,100)
    ])
    lib.import_playlist(pid)
    with lib.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]==99
    # A partial response is not allowed to destroy the current catalog.
    _write(source,[_line("Filme 1","Filmes","https://cdn.invalid/play/1","1")])
    lib.import_playlist(pid)
    with lib.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]==99


def test_same_account_variants_cannot_duplicate_playlists(tmp_path):
    lib=LibraryV2(tmp_path/"dedupe.db")
    src="https://sample.invalid/get.php?username=demo&password=fictional&type=m3u_plus&output=mpegts"
    pid=lib.add_playlist("Home",src)
    with pytest.raises(ValueError,match="biblioteca"):
        lib.add_playlist("Again","https://sample.invalid/get.php?username=demo&password=fictional&type=m3u_plus&output=hls")
    assert len(lib.playlists())==1 and lib.playlists()[0]["id"]==pid


def test_colliding_provider_group_name_is_not_forced_to_one_kind(monkeypatch):
    import json
    class Response:
        def __init__(self,url): self.url=url
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def raise_for_status(self): pass
        def iter_content(self,chunk):
            yield json.dumps([{"category_name":"Legendadas"}]).encode()
    monkeypatch.setattr("aurora_desktop.provider.requests.get",
                        lambda url,**kwargs: Response(url))
    result=get_provider_category_kinds(
        "https://provider.invalid/get.php?username=demo&password=fictional")
    assert "legendadas" not in result
