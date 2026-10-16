import json
from pathlib import Path

from aurora_desktop.catalog import LibraryV2
from aurora_desktop.provider import get_provider_series_posters


def test_provider_series_posters_are_exact_and_host_local(monkeypatch):
    seen=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*exc): return False
        def raise_for_status(self): pass
        def iter_content(self,size):
            yield json.dumps([
                {"name":"A Teia","cover":"https://cdn.example/ateia.jpg"},
                {"name":"A Teia 2","cover":"https://cdn.example/ateia2.jpg"},
                {"name":"No cover","cover":""},
            ]).encode("utf-8")
    def request(url,**kwargs):
        seen.append(url)
        return Response()
    monkeypatch.setattr("aurora_desktop.provider.requests.get",request)
    posters=get_provider_series_posters(
        "https://provider.example.com/get.php?username=demo&password=dummy")
    assert posters=={
        "a teia":"https://cdn.example/ateia.jpg",
        "a teia 2":"https://cdn.example/ateia2.jpg",
    }
    assert len(seen)==1 and "provider.example.com/player_api.php" in seen[0]


def test_series_browse_prefers_official_cover(tmp_path, monkeypatch):
    playlist=tmp_path/"demo.m3u"
    playlist.write_text("""#EXTM3U
#EXTINF:-1 group-title="Séries | Romance" tvg-logo="https://cdn.example/episode.jpg",A Teia S01E01
https://provider.example.com/series/demo/1.mp4
#EXTINF:-1 group-title="Séries | Romance",A Teia S01E02
https://provider.example.com/series/demo/2.mp4
""",encoding="utf-8")
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_category_kinds",lambda _: {})
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_series_posters",
                        lambda _: {"a teia":"https://cdn.example/series.jpg"})
    db=LibraryV2(tmp_path/"db.sqlite")
    pid=db.add_playlist("Casa",str(playlist))
    assert db.import_playlist(pid)==2
    series=db.browse(pid,"series","Romance")
    assert len(series)==1
    assert series[0]["title"]=="A Teia"
    assert series[0]["logo"]=="https://cdn.example/series.jpg"
