"""Beta.15: defensive catalog migration and deterministic playlist classification."""
import pytest

from aurora_desktop.android_rules import classify_content
from aurora_desktop.catalog import LibraryV2
from aurora_desktop.core import parse_m3u


def test_content_priority_prevents_channels_and_episodes_becoming_movies():
    assert classify_content("Rede Globo","Canais de Filmes",
                            "https://provider.test/live/u/p/7.ts") == "live"
    assert classify_content("Série Legal S03E06","Filmes",
                            "https://provider.test/opaque") == "series"
    assert classify_content("Filme HD","Ao vivo",
                            "https://provider.test/m3u","movie") == "movie"
    assert classify_content("Episódio S01E02","Tudo",
                            "https://provider.test/series/u/p/1.mp4") == "series"
    assert classify_content("Sem identificação","Diversos",
                            "https://provider.test/unknown/5") == "other"
    assert classify_content("Televisão","Outro",
                            "https://provider.test/opaque", tvg_id="Globo.br") == "live"
    assert classify_content("Documentário","Canais",
                            "https://provider.test/live/44.ts") == "live"


def test_non_classified_content_is_visible_and_manually_reclassifiable(tmp_path,monkeypatch):
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_category_kinds",lambda _: {})
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_series_posters",lambda _: {})
    source = tmp_path/"playlist.m3u"
    source.write_text(
        '#EXTM3U\n'
        '#EXTINF:-1,Conteúdo sem metadados\n'
        'https://provider.test/opaque/1\n'
        '#EXTINF:-1 group-title="Canais de Filmes",Rede TV\n'
        'https://provider.test/live/u/p/2.ts\n'
        '#EXTINF:-1 group-title="Filmes | Terror",Filme Noir\n'
        'https://provider.test/movie/u/p/3.mp4\n'
        '#EXTINF:-1 group-title="Séries",Uma Série S01E01\n'
        'https://provider.test/series/u/p/4.mp4\n'
        '#EXTINF:-1 group-title="Séries",Uma Série S01E02\n'
        'https://provider.test/series/u/p/5.mp4\n',
        encoding="utf-8")
    lib=LibraryV2(tmp_path/"database.db")
    pid=lib.add_playlist("Teste",str(source))
    assert lib.import_playlist(pid)==5
    assert len(lib.browse(pid,"other",None))==1
    assert len(lib.browse(pid,"live",None))==1
    assert len(lib.browse(pid,"movie",None))==1
    series=lib.browse(pid,"series",None)
    assert len(series)==1 and series[0]["episodes"]==2
    key=lib.browse(pid,"other",None)[0]["key"]
    lib.save_progress(pid,key,77)
    lib.set_favorite(pid,"item:"+key,"other","Conteúdo sem metadados",True)
    lib.set_content_kind(pid,key,"movie")
    assert lib.browse(pid,"other",None)==[]
    assert lib.browse(pid,"movie",None)[1]["kind"]=="movie"
    assert lib.is_favorite(pid,"item:"+key)
    assert lib.get_progress(pid,key)==77
    # Idempotent imports do not duplicate items or forget user overrides.
    for _ in range(2):
        assert lib.import_playlist(pid)==5
    assert len(lib.browse(pid,"movie",None))==2
    assert lib.get_progress(pid,key)==77
    assert lib.is_favorite(pid,"item:"+key)
    assert len(lib.browse(pid,"series",None))==1
    with pytest.raises(ValueError):
        lib.set_content_kind(pid,key,"unknown")
    with lib.connect() as db:
        assert db.execute("SELECT count(*) FROM items WHERE playlist_id=?", (pid,)).fetchone()[0]==5


def test_unknown_entries_have_stable_url_identity():
    first=list(parse_m3u(["#EXTM3U","#EXTINF:-1,Sem tipo",
                         "https://provider.test/content/123"]))
    second=list(parse_m3u(["#EXTM3U","#EXTINF:-1 group-title='Filmes',Sem tipo",
                          "https://provider.test/content/123"]))
    assert first[0].kind=="other"
    assert second[0].kind=="movie"
    assert first[0].key==second[0].key
