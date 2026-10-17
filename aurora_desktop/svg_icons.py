"""Scalable SVG icon library for the AURORA desktop navigation and actions.

Actual SVG path data, rasterized at 3x device pixel ratio for consistent,
antialiased rendering across the supported Qt/Windows/Linux backends.
"""
from __future__ import annotations
from functools import lru_cache
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# SVG path definitions are original, authored for the AURORA IPTV UI.
# The surrounding markup, stroke weight, palette and proportions are uniform.
PATHS = {
    "home": '<path d="M3 10.5 12 3l9 7.5v9.2a1.3 1.3 0 0 1-1.3 1.3H4.3A1.3 1.3 0 0 1 3 19.7z"/><path d="M9.5 21v-7.5h5V21"/><path d="m2 11 10-8 10 8"/>',
    "live": '<rect x="2" y="4" width="20" height="14" rx="3"/><path d="M8 21h8m-4-3v3"/><path d="m10 8 5 3-5 3z" fill="{aqua}" stroke="{aqua}" stroke-width=".75"/>',
    "movie": '<circle cx="11" cy="11" r="8"/><circle cx="11" cy="11" r="1.3" fill="{aqua}"/><circle cx="11" cy="6.2" r="1.65"/><circle cx="15.8" cy="11" r="1.65"/><circle cx="11" cy="15.8" r="1.65"/><circle cx="6.2" cy="11" r="1.65"/><path d="m16.5 16.5 5 4"/>',
    "series": '<rect x="2.5" y="6" width="15.5" height="15" rx="2.3"/><rect x="6.2" y="2.5" width="15.2" height="15.2" rx="2.3" fill="{panel}"/><path d="m12 7.5 5.4 3.1-5.4 3.1z" fill="{aqua}" stroke="{aqua}" stroke-width=".6"/>',
    "football": '<circle cx="12" cy="12" r="9.5"/><path d="m12 7-4.5 3.4 1.7 5.2h5.6l1.7-5.2z" fill="{aqua}" fill-opacity=".35"/><path d="m12 7-1.4-4.2m5.9 7.6 4.1-1.6m-5.8 6.8 2.2 4.1m-7.8-4.1-2.2 4.1m.5-9.3-4.1-1.6"/>',
    "favorites": '<path d="m12 2.4 3 6.2 6.8 1-4.9 4.8 1.1 6.8-6-3.2-6 3.2 1.1-6.8L2.2 9.6l6.8-1z" fill="{gold}" stroke="{gold}" stroke-width="1.4"/>',
    "settings": '<path d="M10 2h4l.65 2.3 1.9.8 2.1-1.2 2.65 2.65-1.2 2.1.8 1.9L22.2 11v3l-2.3.65-.8 1.9 1.2 2.1-2.65 2.65-2.1-1.2-1.9.8L14 22.2h-4l-.65-2.3-1.9-.8-2.1 1.2-2.65-2.65 1.2-2.1-.8-1.9L.8 14v-3l2.3-.65.8-1.9-1.2-2.1 2.65-2.65 2.1 1.2 1.9-.8z" transform="translate(.5 .5) scale(.96)"/><circle cx="12" cy="12" r="3.2"/>',
    "back": '<path d="m14.5 5-7 7 7 7"/><path d="M8 12h13"/>',
    "refresh": '<path d="M20.5 7.8A9 9 0 0 0 5.2 5.4L3 8"/><path d="M3 3.4V8h4.7"/><path d="M3.5 16.2A9 9 0 0 0 18.8 18.6L21 16"/><path d="M21 20.6V16h-4.7"/>',
    "add": '<path d="M12 4v16M4 12h16"/><circle cx="12" cy="12" r="9"/>',
    "upload": '<rect x="3" y="15" width="18" height="6" rx="2"/><path d="M12 15V3m-5 5 5-5 5 5"/>',
    "manage": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    "guide": '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4m8-4v4M8 13h2m4 0h2m-8 4h2"/>',
    # Video controls use the exact same packaged, HiDPI-safe SVG renderer
    # as navigation and EPG. This avoids a mixture of Qt-painted and SVG icons.
    "play": '<path d="M5 3.5 21 12 5 20.5z" fill="{aqua}" stroke="{aqua}"/>',
    "pause": '<rect x="4" y="3" width="6" height="18" rx="1.5" fill="{aqua}" stroke="{aqua}"/><rect x="14" y="3" width="6" height="18" rx="1.5" fill="{aqua}" stroke="{aqua}"/>',
    "volume": '<path d="M2.5 9h4L13 4v16l-6.5-5h-4z" fill="{panel}"/><path d="M16 8a6 6 0 0 1 0 8M19 5a10 10 0 0 1 0 14"/>',
    "mute": '<path d="M2.5 9h4L13 4v16l-6.5-5h-4z" fill="{panel}"/><path d="m16 9 6 6m0-6-6 6" stroke="{gold}"/>',
    "fullscreen": '<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6"/>',
    "exit-fullscreen": '<path d="M3 9h6V3m6 0v6h6M9 21v-6H3m18 0h-6v6"/>',
    "sparkle": '<path d="m12 2 2.7 7.3L22 12l-7.3 2.7L12 22l-2.7-7.3L2 12l7.3-2.7z" fill="{aqua}" stroke="{aqua}"/><path d="m19 1 .6 1.5L21 3l-1.4.5L19 5l-.6-1.5L17 3l1.4-.5z" fill="{gold}"/>',
    "update": '<path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
}

@lru_cache(maxsize=96)
def svg_icon_for(name: str, size: int = 26, light: bool = False) -> QIcon:
    if name not in PATHS or not 8 <= size <= 128:
        raise ValueError("Unsupported AURORA SVG icon")
    aqua = "#087a87" if light else "#74f2df"
    gold = "#efae21" if light else "#ffd45d"
    stroke = gold if name == "favorites" else ("#27628b" if light else "#bdd7ff")
    panel = "#e9f4fa" if light else "#153148"
    contents = PATHS[name].format(aqua=aqua, gold=gold, panel=panel)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
           f'viewBox="0 0 24 24"><g fill="none" stroke="{stroke}" '
           f'stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">'
           f'{contents}</g></svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"Invalid SVG for {name}")
    scale = 3
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    # CRITICAL: explicit *logical-size* viewport. Without it, on HiDPI
    # renderers QtSvg draws just a physical 24x24 fragment into a 90x90
    # pixmap, causing chopped symbols (the beta.12 regression).
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)
