"""HiDPI SVG coverage regression: incomplete icons from beta.12 never return."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"

from PySide6.QtWidgets import QApplication
from aurora_desktop.svg_icons import PATHS, svg_icon_for


def test_svg_icons_occupy_full_logical_square_not_tiny_corner():
    app=QApplication.instance() or QApplication([])
    for name in PATHS:
        for light in (True,False):
            ico=svg_icon_for(name,30,light=light)
            img=ico.pixmap(90,90).toImage()
            assert not img.isNull(),name
            # Test the *actual pixels* rather than QSvgRenderer.isValid().
            # The beta.12 bug produced a small fragment in the corner.
            xs,ys=[],[]
            for y in range(img.height()):
                for x in range(img.width()):
                    if img.pixelColor(x,y).alpha()>40:
                        xs.append(x)
                        ys.append(y)
            assert xs and ys, f"{name}: empty"
            width=max(xs)-min(xs)+1
            height=max(ys)-min(ys)+1
            assert width >= int(img.width()*.61), (name,width,img.width())
            assert height >= int(img.height()*.57), (name,height,img.height())
            assert max(xs) >= img.width()//2, name
            assert max(ys) >= img.height()//2, name
