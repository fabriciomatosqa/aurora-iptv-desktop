"""Desktop support for Android provider categories and existing-data migrations."""
import json

from aurora_desktop.catalog import LibraryV2
from aurora_desktop.provider import get_provider_category_kinds
from aurora_desktop.core import kind_of


def test_android_hint_priority_for_ambiguous_groups():
    assert kind_of("Documentários", "Noticiário", "https://example.net/path/1.ts", "live") == "live"
    assert kind_of("Ao Vivo", "Drama", "https://example.net/path/1.mkv", "movie") == "movie"
    assert kind_of("Filmes e Séries", "A Show", "https://example.net/path/1.ts", "series") == "series"


def test_provider_categories_stay_on_same_host(monkeypatch):
    calls = []
    class Response:
        def __init__(self, url):
            self.url=url
            self.status_code=200
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def raise_for_status(self): pass
        def iter_content(self,_):
            action=self.url.split("action=")[-1]
            categories={"get_live_categories":"Canais de Cinema",
                       "get_vod_categories":"Filmes 2026",
                       "get_series_categories":"Séries: Romance"}
            yield json.dumps([{"category_name":categories[action]}]).encode()
    def get(url, **kwargs):
        calls.append(url)
        return Response(url)
    monkeypatch.setattr("aurora_desktop.provider.requests.get",get)
    result=get_provider_category_kinds(
        "https://provider.example.com/get.php?username=demo&password=dummy&type=m3u_plus")
    assert result == {"canais de cinema":"live","filmes 2026":"movie","series romance":"series"}
    assert len(calls)==3
    assert all(url.startswith("https://provider.example.com/player_api.php?") for url in calls)


def test_provider_categories_override_heuristics(tmp_path,monkeypatch):
    path=tmp_path/"provider.m3u"
    path.write_text("""#EXTM3U
#EXTINF:-1 group-title="Canais de Cinema",TCM HD
http://host.test/example.ts
#EXTINF:-1 group-title="Canais Ao Vivo",Jornal da noite
http://host.test/example2.ts
#EXTINF:-1 group-title="Séries: Romance",Amor S01E01
http://host.test/episode/12.mp4
""")
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_category_kinds",
                        lambda _: {"canais de cinema":"live","canais ao vivo":"live","series romance":"series"})
    lib=LibraryV2(tmp_path/"state.db")
    pid=lib.add_playlist("Test",str(path))
    assert lib.import_playlist(pid)==3
    assert any(i["title"]=="TCM HD" for i in lib.items(pid,"live"))
    assert lib.browse(pid,"series","Romance")[0]["title"]=="Amor"
    lib.ensure_categories(pid)
    assert lib.counts(pid)=={"live":2,"series":1}


def test_old_database_retains_key_identity(tmp_path):
    lib=LibraryV2(tmp_path/"old.db")
    pid=lib.add_playlist("Casa","https://example.test/list.m3u")
    with lib.connect() as db:
        db.execute("""INSERT INTO items
            (playlist_id,key,title,url,group_name,kind,logo,series_name,season,episode,type_hint)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (pid,"the-url-hash","Drama (2024)","https://host.test/v/2.mkv",
             "Ao Vivo","live","","",None,None,"movie"))
    lib.set_favorite(pid,"item:the-url-hash","live","Drama (2024)",True)
    lib.save_progress(pid,"the-url-hash",92)
    lib.ensure_categories(pid)
    assert lib.items(pid,"movie")[0]["key"]=="the-url-hash"
    assert lib.get_progress(pid,"the-url-hash")==92
    assert lib.is_favorite(pid,"item:the-url-hash")
