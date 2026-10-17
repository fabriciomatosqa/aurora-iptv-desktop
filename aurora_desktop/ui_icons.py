"""High-DPI vector icons for AURORA IPTV, drawn with Qt itself.

No emoji, external icon packs or network assets. Shapes are consistent across
Windows/Linux, dark/light themes, and high-resolution/retina displays.
"""
from __future__ import annotations

from functools import lru_cache
from math import cos, pi, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap, QRadialGradient
)


@lru_cache(maxsize=90)
def icon_for(name: str, size: int = 24, light: bool = False) -> QIcon:
    """Return a crisp, accessible, custom AURORA icon with a logical size."""
    if size < 8 or size > 128:
        raise ValueError("Invalid icon size")
    density = 3
    canvas = QPixmap(size * density, size * density)
    canvas.setDevicePixelRatio(density)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.scale(size / 24, size / 24)
    cyan = QColor("#187b82" if light else "#75f1df")
    blue = QColor("#3171bb" if light else "#86bfff")
    violet = QColor("#7960cb" if light else "#b6a3ff")
    gold = QColor("#e6a323" if light else "#ffda62")
    white = QColor("#ffffff")
    ink = QColor("#0a2234")
    p.setPen(Qt.PenStyle.NoPen)

    def outline(path: QPainterPath, color=cyan, width=1.9, fill=None):
        p.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QBrush(fill) if fill is not None else Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def rounded(x, y, w, h, r, color, border=None, line_width=1.8):
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), r, r)
        outline(path, border or color, line_width,
                QColor(color) if isinstance(color, str) else color)

    if name == "home":
        roof = QPainterPath()
        roof.moveTo(2.9, 11.15)
        roof.lineTo(11.1, 3.55)
        roof.quadTo(12, 2.75, 12.9, 3.55)
        roof.lineTo(21.1, 11.15)
        outline(roof, cyan, 2.1)
        base = QPainterPath()
        base.moveTo(5.6, 9.4)
        base.lineTo(5.6, 19.6)
        base.quadTo(5.6, 21.0, 7, 21)
        base.lineTo(17, 21)
        base.quadTo(18.4, 21, 18.4, 19.6)
        base.lineTo(18.4, 9.4)
        outline(base, cyan, 2.0)
        rounded(10.1, 14.0, 3.8, 7, 1.0, blue, blue, 0.4)
    elif name == "live":
        screen = QLinearGradient(4, 4, 19, 19)
        screen.setColorAt(0, QColor("#326bb7" if light else "#234d85"))
        screen.setColorAt(1, QColor("#196d77" if light else "#087c86"))
        rounded(2.0, 3.9, 20, 14.6, 3.0, screen, cyan, 1.9)
        p.setPen(QPen(white, 1.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(7.2, 9), QPointF(13, 9))
        p.drawLine(QPointF(7.2, 12), QPointF(15.6, 12))
        p.setPen(QPen(cyan, 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(9.1, 21), QPointF(14.9, 21))
        p.drawLine(QPointF(12, 18.5), QPointF(12, 21))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gold)
        p.drawEllipse(QRectF(17.3, 6.6, 2.1, 2.1))
    elif name == "movie":
        reel = QRadialGradient(10.9, 10.8, 9.5)
        reel.setColorAt(0, QColor("#5375c4" if light else "#7392ed"))
        reel.setColorAt(1, QColor("#392968" if light else "#3f387f"))
        p.setBrush(reel)
        p.setPen(QPen(violet, 1.6))
        p.drawEllipse(QRectF(2.8, 2.7, 16.2, 16.2))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#102738" if not light else "#edf6fb"))
        for x,y in [(10.9,5.8),(15.3,10.8),(10.9,15.0),(6.5,10.8)]:
            p.drawEllipse(QRectF(x-1.5, y-1.5, 3, 3))
        p.setBrush(cyan)
        p.drawEllipse(QRectF(9.9, 9.8, 2, 2))
        tail = QPainterPath()
        tail.moveTo(15.7, 17.0)
        tail.lineTo(21.4, 21.5)
        tail.lineTo(22.0, 18.3)
        outline(tail, blue, 1.9)
    elif name == "series":
        rounded(2.4, 5.6, 15.1, 15, 2.3, QColor("#21415e") if not light else QColor("#deeef9"), blue, 1.8)
        rounded(6.4, 2.8, 15.3, 15, 2.3, QColor("#245e72") if not light else QColor("#e0f7f6"), cyan, 1.8)
        play = QPainterPath()
        play.moveTo(12.15, 6.9)
        play.lineTo(12.15, 13.45)
        play.lineTo(17.5, 10.15)
        play.closeSubpath()
        outline(play, white, 0.6, white)
        p.setPen(QPen(cyan, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(9.5, 15.7), QPointF(18.6, 15.7))
    elif name == "football":
        p.setPen(QPen(cyan, 1.7))
        p.setBrush(QColor("#174050") if not light else QColor("#d9f4ec"))
        p.drawEllipse(QRectF(2.6, 2.6, 18.8, 18.8))
        middle = QPainterPath()
        for i in range(5):
            t=-pi/2+i*2*pi/5
            x,y=12+4.2*cos(t),12+4.2*sin(t)
            if i==0:
                middle.moveTo(x,y)
            else:
                middle.lineTo(x,y)
        middle.closeSubpath()
        outline(middle, blue, 1.3, QColor("#81dbd6") if not light else QColor("#389fa6"))
        p.setPen(QPen(cyan, 1.25))
        for i in range(5):
            a=-pi/2+i*2*pi/5
            p.drawLine(QPointF(12+4.3*cos(a),12+4.3*sin(a)),
                       QPointF(12+8.8*cos(a),12+8.8*sin(a)))
    elif name in ("favorites", "favorite-outline"):
        gradient = QRadialGradient(10, 7.2, 16)
        gradient.setColorAt(0, QColor("#fff3ae"))
        gradient.setColorAt(.55, gold)
        gradient.setColorAt(1, QColor("#e49c24"))
        star = QPainterPath()
        for i in range(10):
            t=-pi/2 + i*pi/5
            radius = 9.8 if i%2==0 else 4.4
            pt=QPointF(12+radius*cos(t),12+radius*sin(t))
            if i==0:
                star.moveTo(pt)
            else:
                star.lineTo(pt)
        star.closeSubpath()
        fill = gradient if name == "favorites" else None
        outline(star, QColor("#f8c65a") if not light else QColor("#c18b15"), 1.2, fill)
    elif name == "settings":
        p.save()
        p.translate(12, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(blue)
        for i in range(8):
            p.save()
            p.rotate(i*45)
            p.drawRoundedRect(QRectF(-1.75,-10,3.5,5.1),1.15,1.15)
            p.restore()
        p.setBrush(cyan)
        p.drawEllipse(QRectF(-7.25,-7.25,14.5,14.5))
        p.setBrush(QColor("#132b43") if not light else QColor("#eaf6fa"))
        p.drawEllipse(QRectF(-3.45,-3.45,6.9,6.9))
        p.restore()
    elif name == "sparkle":
        for cx,cy,r in [(12,12,9.7),(19,5.4,2.2)]:
            shape=QPainterPath()
            shape.moveTo(cx,cy-r)
            shape.quadTo(cx+r*.15,cy-r*.15,cx+r,cy)
            shape.quadTo(cx+r*.15,cy+r*.15,cx,cy+r)
            shape.quadTo(cx-r*.15,cy+r*.15,cx-r,cy)
            shape.quadTo(cx-r*.15,cy-r*.15,cx,cy-r)
            shape.closeSubpath()
            outline(shape,cyan,.55,cyan)
    elif name == "play":
        shape=QPainterPath()
        shape.moveTo(7,4.6)
        shape.quadTo(6.1,4.4,6.1,6)
        shape.lineTo(6.1,18)
        shape.quadTo(6.1,19.6,7.5,19.1)
        shape.lineTo(18.1,13)
        shape.quadTo(19.5,12,18.1,11)
        shape.closeSubpath()
        outline(shape,cyan,1.4,cyan)
    elif name == "pause":
        rounded(5.5,4.4,4.7,15.2,1.4,cyan,cyan,1)
        rounded(13.8,4.4,4.7,15.2,1.4,cyan,cyan,1)
    elif name in ("volume", "mute"):
        shape=QPainterPath()
        shape.moveTo(3,9)
        shape.lineTo(7.5,9)
        shape.lineTo(13,4.8)
        shape.lineTo(13,19.2)
        shape.lineTo(7.5,15)
        shape.lineTo(3,15)
        shape.closeSubpath()
        outline(shape,cyan,1.7, QColor("#1e4358") if not light else QColor("#d7f0f0"))
        if name == "volume":
            for rad in [6,10]:
                curve=QPainterPath()
                curve.arcMoveTo(QRectF(9.0,12-rad,rad*2,rad*2),-52)
                curve.arcTo(QRectF(9.0,12-rad,rad*2,rad*2),-52,104)
                outline(curve,blue,1.6)
        else:
            p.setPen(QPen(gold,2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(17,9),QPointF(22,15))
            p.drawLine(QPointF(22,9),QPointF(17,15))
    elif name in ("fullscreen","exit-fullscreen"):
        p.setPen(QPen(cyan,2.1,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        if name == "fullscreen":
            for x,y,dx,dy in [(4,4,5,5),(20,4,-5,5),(4,20,5,-5),(20,20,-5,-5)]:
                p.drawLine(QPointF(x+dx,y),QPointF(x,y))
                p.drawLine(QPointF(x,y),QPointF(x,y+dy))
        else:
            for x,y,dx,dy in [(4,4,5,5),(20,4,-5,5),(4,20,5,-5),(20,20,-5,-5)]:
                p.drawLine(QPointF(x+dx,y),QPointF(x+dx,y+dy))
                p.drawLine(QPointF(x,y+dy),QPointF(x+dx,y+dy))
    elif name == "refresh":
        circle = QPainterPath()
        circle.arcMoveTo(QRectF(3.5,3.5,17,17),45)
        circle.arcTo(QRectF(3.5,3.5,17,17),45,285)
        outline(circle, cyan, 2)
        arrow=QPainterPath()
        arrow.moveTo(17.3,4.0)
        arrow.lineTo(20.2,4.1)
        arrow.lineTo(20.1,7.1)
        outline(arrow,cyan,1.9)
    else:
        p.end()
        raise ValueError(f"Unknown AURORA icon: {name}")
    p.end()
    return QIcon(canvas)
