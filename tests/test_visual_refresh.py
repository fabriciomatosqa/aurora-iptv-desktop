"""Visual identity regression checks: vector icons, theme isolation and nav layout."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from aurora_desktop.modern import MainWindow
from aurora_desktop.ui_icons import icon_for


def test_seven_navigation_icons_are_unique_high_dpi():
    app=QApplication.instance() or QApplication([])
    modes=("home","live","movie","series","football","favorites","settings")
    icons=[icon_for(m, 32).pixmap(QSize(32,32)) for m in modes]
    assert all(not p.isNull() for p in icons)
    assert all(p.devicePixelRatio() >= 1 for p in icons)
    signatures=[]
    for p in icons:
        image=p.toImage()
        sig=bytes(image.bits())
        assert any(sig)
        signatures.append(hash(sig))
    assert len(set(signatures)) == len(modes)
    assert icon_for("favorites").cacheKey() != icon_for("movie").cacheKey()


def test_theme_does_not_accumulate_styles_or_black_heading_bars(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    try:
        first=app.styleSheet()
        assert "QLabel {" in first
        assert "background:transparent" in first
        assert "QFrame#playerSplash" in first
        assert "QPushButton#navButton" in first
        win._theme_apply()
        assert app.styleSheet()==first
        win.settings.setValue("theme","light")
        win._theme_apply()
        light=app.styleSheet()
        assert light != first
        assert len(light) < len(first) * 1.3
        win.settings.setValue("theme","dark")
        win._theme_apply()
        assert app.styleSheet() == first
    finally:
        win.close()


def test_menu_uses_vector_icons_and_human_readable_labels(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    try:
        assert set(win.nav)=={"home","live","movie","series","football","favorites","settings"}
        assert [(k,btn.text()) for k,btn in win.nav.items()] == [
            ("home","Início"),("live","Ao vivo"),("movie","Filmes"),
            ("series","Séries"),("football","Futebol"),
            ("favorites","Favoritos"),("settings","Configurações")
        ]
        assert all(btn.objectName()=="navButton" for btn in win.nav.values())
        assert all(not btn.icon().isNull() for btn in win.nav.values())
        assert win.results.objectName()=="results"
        assert win.now.objectName()=="playerEyebrow"
        assert win.status.objectName()=="statusInfo"
        assert win.covers.placeholder("movie").cacheKey() != win.covers.placeholder("live").cacheKey()
    finally:
        win.close()
