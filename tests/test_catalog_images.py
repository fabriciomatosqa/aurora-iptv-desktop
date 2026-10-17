"""Image regression tests: channels, movies, grouped series, Qt disk cache."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path

from aurora_desktop.artwork import (
    image_cache_file, pick_best_art, xtream_stream_id,
)
from aurora_desktop.core import parse_m3u
from aurora_desktop.catalog import LibraryV2
from aurora_desktop.provider import get_provider_stream_artwork


def test_m3u_picks_kind_specific_real_images():
    rows=list(parse_m3u([
        '#EXTINF:-1 group-title="Ao Vivo" tvg-logo="https://img.example/tv.png" poster="https://img.example/wrong.jpg",Canal TV',
        'https://provider.example/live/user/pass/101.ts',
        '#EXTINF:-1 group-title="Filmes" tvg-logo="https://img.example/thumb.png" poster="https://img.example/film.jpg",Um Filme',
        'https://provider.example/movie/user/pass/102.mp4',
        '#EXTINF:-1 group-title="Séries" tvg-logo="https://img.example/episode.png" cover="https://img.example/series.jpg",Uma Série S01E01',
        'https://provider.example/series/user/pass/103.mp4',
        '#EXTINF:-1 group-title="Ao Vivo" stream_icon="https://img.example/stream.png",Outro Canal',
        'https://provider.example/live/user/pass/104.ts',
    ]))
    assert [r.kind for r in rows]==["live","movie","series","live"]
    assert [r.logo for r in rows]==[
        "https://img.example/tv.png",
        "https://img.example/film.jpg",
        "https://img.example/series.jpg",
        "https://img.example/stream.png",
    ]


def test_picker_reuses_series_poster_and_does_not_guess():
    assert pick_best_art({
        "kind":"series","logo":"https://cdn.test/ep.jpg",
        "series_poster":"https://cdn.test/show.jpg"})=="https://cdn.test/show.jpg"
    assert pick_best_art({"kind":"movie","cover":"https://cdn.test/movie.jpg"})=="https://cdn.test/movie.jpg"
    assert pick_best_art({"kind":"live","logo":"https://cdn.test/channel.png"})=="https://cdn.test/channel.png"
    assert pick_best_art({"kind":"movie","poster":"not-an-image-url"})==""
    key=image_cache_file(Path("/tmp"),"https://server.example/logo.png?token=private")
    assert key.suffix==".img" and "private" not in str(key)


def test_stream_id_matches_only_explicit_xtream_paths():
    assert xtream_stream_id("https://provider.test/live/user/pass/123.ts","live")=="123"
    assert xtream_stream_id("https://provider.test/movie/user/pass/900.mp4","movie")=="900"
    assert xtream_stream_id("https://provider.test/live/user/pass/123.ts","movie")==""
    assert xtream_stream_id("https://provider.test/series/user/pass/123.mp4","series")==""


def test_provider_images_use_exact_ids_and_same_configured_host(monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    calls=[]
    class Response:
        def __init__(self, content): self.content=content
        def __enter__(self): return self
        def __exit__(self,*exc): return False
        def raise_for_status(self): pass
        def iter_content(self,size): yield self.content
    def get(url, **kw):
        import json
        calls.append(url)
        query=parse_qs(urlsplit(url).query)
        action=query.get("action",[""])[0]
        if action=="get_live_streams":
            rows=[{"stream_id":101,"stream_icon":"https://cdn.example/live.png"}]
        elif action=="get_vod_streams":
            rows=[{"stream_id":102,"stream_icon":"https://cdn.example/film.jpg"}]
        else:
            rows=[]
        return Response(json.dumps(rows).encode())
    monkeypatch.setattr("aurora_desktop.provider.requests.get",get)
    source="https://provider.example/get.php?username=user&password=pass&type=m3u_plus"
    assert get_provider_stream_artwork(source,"live")=={"101":"https://cdn.example/live.png"}
    assert get_provider_stream_artwork(source,"movie")=={"102":"https://cdn.example/film.jpg"}
    assert len(calls)==2 and all("provider.example" in url for url in calls)


def test_catalog_adds_real_posters_without_resetting_user_data(tmp_path,monkeypatch):
    source="https://provider.example/get.php?username=user&password=pass&type=m3u_plus"
    playlist=tmp_path/"sample.m3u"
    playlist.write_text(
        '#EXTM3U\n'
        '#EXTINF:-1 group-title="Ao Vivo",Canal\n'
        'https://provider.example/live/user/pass/101.ts\n'
        '#EXTINF:-1 group-title="Filmes",Um Filme\n'
        'https://provider.example/movie/user/pass/102.mp4\n'
        '#EXTINF:-1 group-title="Séries | Drama" tvg-logo="https://cdn.example/episode.jpg",A Teia S01E01\n'
        'https://provider.example/series/user/pass/103.mp4\n'
        '#EXTINF:-1 group-title="Séries | Drama",A Teia S01E02\n'
        'https://provider.example/series/user/pass/104.mp4\n',encoding="utf-8")
    # Only movie/channel artwork API is stubbed; no internet necessary.
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_category_kinds",lambda _: {})
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_series_posters",
                        lambda _: {"a teia":"https://cdn.example/show.jpg"})
    monkeypatch.setattr("aurora_desktop.catalog.get_provider_stream_artwork",
                        lambda _,kind: {"101":"https://cdn.example/live.png"} if kind=="live"
                                      else {"102":"https://cdn.example/film.jpg"})
    lib=LibraryV2(tmp_path/"catalog.db")
    pid=lib.add_playlist("Minha playlist",str(playlist))
    assert lib.import_playlist(pid)==4
    # Local M3U import is not Xtream; explicit post-enrichment emulates
    # the same provider source while proving strict ID mapping.
    lib._enrich_missing_artwork(pid,source)
    live=lib.browse(pid,"live",None)[0]
    movie=lib.browse(pid,"movie",None)[0]
    shows=lib.browse(pid,"series",None)
    assert live["logo"]=="https://cdn.example/live.png"
    assert movie["logo"]=="https://cdn.example/film.jpg"
    assert shows[0]["logo"]=="https://cdn.example/show.jpg"
    assert len(shows)==1 and shows[0]["episodes"]==2
    lib.save_progress(pid,movie["key"],90)
    lib.set_favorite(pid,"item:"+movie["key"],"movie",movie["title"],True)
    lib.set_favorite(pid,"series:A Teia","series","A Teia",True)
    faves=lib.favorite_entries(pid)
    assert next(r for r in faves if r["kind"]=="series")["logo"]=="https://cdn.example/show.jpg"
    lib._enrich_missing_artwork(pid,source)
    assert lib.get_progress(pid,movie["key"])==90
    assert lib.is_favorite(pid,"item:"+movie["key"])
    with lib.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]==4


def test_qt_cards_load_local_artwork_and_persisted_cache(tmp_path,monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap,QColor
    from PySide6.QtWidgets import QApplication,QListWidget,QListWidgetItem,QLabel
    from aurora_desktop.modern import Covers
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    widget=QListWidget()
    loader=Covers(widget)
    image=QPixmap(300,500)
    image.fill(QColor("#00ccaa"))
    local=tmp_path/"poster.png"
    assert image.save(str(local))
    item=QListWidgetItem("Filme",widget)
    loader.enqueue(item,str(local),"movie")
    assert item.icon().cacheKey()!=loader.blanks["movie"].cacheKey()
    image_url="https://cdn.example/poster.png"
    location=image_cache_file(loader.disk_dir,image_url)
    assert image.save(str(location),"PNG")
    disk_item=QListWidgetItem("Série",widget)
    loader.enqueue(disk_item,image_url,"series")
    assert disk_item.icon().cacheKey()!=loader.blanks["series"].cacheKey()
    logo=QListWidgetItem("TV",widget)
    loader.enqueue(logo,image_url,"live")
    assert logo.icon().cacheKey()!=loader.blanks["live"].cacheKey()
    preview=QLabel()
    preview.setFixedSize(132,190)
    loader.enqueue_preview(preview,str(local),"movie")
    assert preview.pixmap() is not None and not preview.pixmap().isNull()
    loader.enqueue_preview(preview,image_url,"series")
    assert preview.pixmap() is not None and not preview.pixmap().isNull()
    # A stale request for the previous item may not overwrite selection.
    preview.setProperty("artworkUrl","https://cdn.example/other.png")
    before=preview.pixmap().cacheKey()
    loader._show_preview(preview,image_url,image)
    assert preview.pixmap().cacheKey()==before
    widget.close()
