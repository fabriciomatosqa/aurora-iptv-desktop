"""Focused UI, football and synopsis regressions for the next AURORA beta."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
from datetime import datetime,timedelta,timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem

from aurora_desktop.core import parse_extinf,parse_m3u
from aurora_desktop.catalog import LibraryV2,competition_group
from aurora_desktop.modern import MainWindow


def test_description_is_preserved_in_m3u_and_database(tmp_path):
    item='#EXTINF:-1 group-title="Filmes | Terror" description="Sinopse detalhada de teste.",Um Filme'
    info=parse_extinf(item)
    assert info["synopsis"]=="Sinopse detalhada de teste."
    rows=list(parse_m3u([item,"https://example.com/movie/2.mp4"]))
    assert rows[0].synopsis=="Sinopse detalhada de teste."
    source=tmp_path/"films.m3u"
    source.write_text("#EXTM3U\n"+item+"\nhttps://example.com/movie/2.mp4\n")
    lib=LibraryV2(tmp_path/"db.sqlite")
    pid=lib.add_playlist("Minha lista",str(source))
    assert lib.import_playlist(pid)==1
    movie=lib.browse(pid,"movie",None)[0]
    assert movie["synopsis"]=="Sinopse detalhada de teste."
    lib.set_favorite(pid,"item:"+movie["key"],"movie",movie["title"],True)
    lib.save_progress(pid,movie["key"],41)
    lib.import_playlist(pid)
    assert lib.is_favorite(pid,"item:"+movie["key"])
    assert lib.get_progress(pid,movie["key"])==41


def test_football_event_requires_two_teams_and_uses_provided_artwork(tmp_path):
    path=tmp_path/"source.m3u"
    path.write_text('#EXTM3U\n#EXTINF:-1 tvg-id="glo" group-title="Ao vivo",Globo\nhttps://example.com/live/1.ts\n')
    lib=LibraryV2(tmp_path/"f.db")
    pid=lib.add_playlist("Local",str(path))
    lib.import_playlist(pid)
    t=datetime.now(timezone.utc)+timedelta(hours=1)
    stamp=lambda x:x.strftime("%Y%m%d%H%M%S +0000")
    xml=tmp_path/"guide.xml"
    xml.write_text(
        f'<tv><programme channel="glo" start="{stamp(t)}" stop="{stamp(t+timedelta(hours=2))}">'
        '<title>Jornal esportivo</title><category>Brasileirão</category></programme>'
        f'<programme channel="glo" start="{stamp(t)}" stop="{stamp(t+timedelta(hours=2))}">'
        '<title>Fluminense x Santos</title><category>Campeonato Brasileiro</category>'
        '<icon src="https://example.com/official/event.png" /></programme></tv>',encoding="utf-8")
    lib.set_epg_url(pid,str(xml))
    assert lib.import_football(pid)==1
    entries=lib.football(pid,"Brasileirão","Santos")
    assert len(entries)==1
    assert entries[0]["home_team"]=="Fluminense"
    assert entries[0]["away_team"]=="Santos"
    assert entries[0]["event_logo"]=="https://example.com/official/event.png"
    assert lib.football(pid,"Brasileirão","Flamengo")==[]
    assert lib.football_categories(pid)==[{"title":"Brasileirão","total":1}]
    assert competition_group("CONMEBOL Libertadores")=="Libertadores"
    assert competition_group("Copa do Mundo FIFA")=="FIFA"


def test_football_page_without_guide_does_not_list_channels_as_matches(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    source=tmp_path/"sports.m3u"
    source.write_text('#EXTM3U\n#EXTINF:-1 group-title="Esportes",SporTV\nhttps://example.com/live/one.ts\n')
    pid=win.library.add_playlist("Esportes",str(source))
    win.library.import_playlist(pid)
    win._reload_playlists(pid)
    win.show()
    app.processEvents()
    try:
        win.navigate("football")
        app.processEvents()
        assert win.results.count()==0
        assert "Nenhuma partida" in win.page.text()
        assert win.football_refresh.isVisible()
        assert win.football_refresh.height()<=40
        assert not win.action.isVisible()
        assert not win.second_action.isVisible()
        win.navigate("settings")
        win.groups.setCurrentRow(3)
        app.processEvents()
        assert win.epg_settings.isVisible()
    finally:
        win.close()


def test_back_from_episodes_returns_to_search_genre_and_scroll(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    source=tmp_path/"shows.m3u"
    source.write_text('#EXTM3U\n#EXTINF:-1 group-title="Séries | Animação",Série Legal S01E01\nhttps://example.com/series/1.mp4\n',encoding="utf-8")
    pid=win.library.add_playlist("Programas",str(source))
    win.library.import_playlist(pid)
    win._indexed.add(pid)
    win._reload_playlists(pid)
    win.show()
    app.processEvents()
    try:
        win.navigate("series")
        app.processEvents()
        genre=next(i for i in range(win.groups.count())
                   if win.groups.item(i).data(Qt.ItemDataRole.UserRole)=="Animação")
        win.groups.setCurrentRow(genre)
        win.search.setText("Série")
        record=win.library.browse(pid,"series","Animação")[0]
        item=QListWidgetItem(record["title"])
        item.setData(Qt.ItemDataRole.UserRole,record)
        win._open(item)
        assert win.mode=="episodes"
        win._go_back()
        app.processEvents()
        assert win.mode=="series"
        assert win.selected_category=="Animação"
        assert win.search.text()=="Série"
        assert win.previous.isHidden()
    finally:
        win.close()


def test_synopsis_fallback_and_date_format_are_grounded():
    label=MainWindow._football_label({
        "competition":"Brasileirão","home_team":"Fluminense",
        "away_team":"Santos","start":"2026-10-18T16:00:00-03:00",
        "channel_title":"Canal do jogo","broadcast":"unknown"})
    assert "Fluminense  X  Santos" in label
    assert "Outubro" in label
    expected=datetime.fromisoformat("2026-10-18T16:00:00-03:00").astimezone().strftime("%H:%M")
    assert expected in label
    assert "Canal do jogo" in label
    assert "0 X 0" not in label
    assert "AO VIVO" not in label


def test_ui_search_preserves_current_football_and_film_category(tmp_path, monkeypatch):
    """Typing a query must not silently change the selected championship/genre."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    source=tmp_path/"browse.m3u"
    source.write_text(
        '#EXTM3U\n'
        '#EXTINF:-1 group-title="Ao vivo",Canal Esportivo\n'
        'https://example.com/live/channel.ts\n'
        '#EXTINF:-1 group-title="Filmes | Terror",Um Filme\n'
        'https://example.com/vod/film.mp4\n',encoding="utf-8")
    pid=win.library.add_playlist("Teste de filtros",str(source))
    win.library.import_playlist(pid)
    win._indexed.add(pid)
    win._auto_guide_attempted.add(pid)
    win._reload_playlists(pid)
    win.show()
    app.processEvents()
    try:
        win.navigate("football")
        football_calls=[]
        def track_football(pid, category, search="", **kwargs):
            football_calls.append((category,search))
            return []
        monkeypatch.setattr(win.library, "football", track_football)
        win.selected_category="Brasileirão"
        win.search.blockSignals(True)
        win.search.setText("Fluminense")
        win.search.blockSignals(False)
        win._load_items(reset=True)
        assert football_calls[-1]==("Brasileirão","Fluminense")

        win.navigate("movie")
        movie_calls=[]
        def track_movie(pid, kind, category, search="", **kwargs):
            movie_calls.append((kind,category,search))
            return []
        monkeypatch.setattr(win.library, "browse", track_movie)
        win.selected_category="Terror"
        win.search.blockSignals(True)
        win.search.setText("Vampiro")
        win.search.blockSignals(False)
        win._load_items(reset=True)
        assert movie_calls[-1]==("movie","Terror","Vampiro")
    finally:
        win.close()


def test_all_player_and_epg_icons_are_svg_and_settings_have_correct_gear(tmp_path,monkeypatch):
    """Menu, player and EPG use the same SVG path registry on both themes."""
    from aurora_desktop.svg_icons import PATHS, svg_icon_for
    expected={"play","pause","volume","mute","fullscreen","exit-fullscreen",
              "favorites","settings","refresh","sparkle"}
    assert expected.issubset(PATHS)
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    win=MainWindow()
    win.show()
    app.processEvents()
    try:
        for button in (win.play,win.favorite,win.fs_favorite,win.fs_play,
                       win.volume_button,win.fullscreen_button,
                       win.config_epg_button,win.update_epg_button):
            assert not button.icon().isNull()
        for theme in (False,True):
            for name in expected:
                assert not svg_icon_for(name,24,light=theme).isNull()
        win.navigate("settings")
        win.groups.setCurrentRow(3)
        app.processEvents()
        assert win.config_epg_button.isVisible()
        assert win.update_epg_button.isVisible()
    finally:
        win.close()
