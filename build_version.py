"""Produce native Windows/Debian version metadata from the *one* app version."""
from pathlib import Path
from datetime import datetime
import re
from aurora_desktop import __version__

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?$")
DATED_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-(\d{6})\.(\d{2})$")


def native_versions(version: str):
    dated=DATED_RE.fullmatch(version)
    if dated:
        a,b,c,ddmmyy,number=dated.groups()
        day,month,year=int(ddmmyy[:2]),int(ddmmyy[2:4]),2000+int(ddmmyy[4:])
        date=datetime(year,month,day)
        iteration=int(number)
        if iteration<1:
            raise ValueError("Sequência diária deve iniciar em 01.")
        # Windows FILEVERSION component is limited to 16 bits. This field
        # is build metadata, not the full release-ordering mechanism.
        revision=date.timetuple().tm_yday*100+iteration
        # DEB must sort monotonically by ISO date, not displayed DDMMYY.
        deb=f"{a}.{b}.{c}~date{date:%Y%m%d}.{number}"
        return (int(a),int(b),int(c),revision),deb
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError("Use X.Y.Z, X.Y.Z-beta.N or X.Y.Z-DDMMAA.NN")
    a,b,c,label,iteration=match.groups()
    revision = 0 if label is None else (1000 if label=="beta" else 2000)+int(iteration)
    deb = f"{a}.{b}.{c}" + (f"~{label}{iteration}" if label else "")
    return (int(a),int(b),int(c),revision), deb


def prepare(folder: Path = Path("build")):
    folder.mkdir(parents=True,exist_ok=True)
    native,deb=native_versions(__version__)
    values=",".join(str(i) for i in native)
    human=".".join(map(str,native))
    # PyInstaller --version-file expects Python-repr version resources.
    content=f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({values}), prodvers=({values}),
    mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,
    date=(0,0)),
  kids=[
    StringFileInfo([StringTable('040904b0',[
      StringStruct('CompanyName','AURORA IPTV'),
      StringStruct('FileDescription','AURORA IPTV Desktop'),
      StringStruct('FileVersion','{__version__}'),
      StringStruct('InternalName','AURORA-IPTV'),
      StringStruct('OriginalFilename','AURORA-IPTV.exe'),
      StringStruct('ProductName','AURORA IPTV Desktop'),
      StringStruct('ProductVersion','{__version__}')
    ])]),
    VarFileInfo([VarStruct('Translation',[1033,1200])])
  ]
)
"""
    (folder/"windows_version.txt").write_text(content,encoding="utf-8")
    (folder/"debian_version.txt").write_text(deb+"\n",encoding="utf-8")
    return human,deb


if __name__=="__main__":
    win,deb=prepare()
    print(f"Build metadata: Aurora {__version__}, Windows {win}, Debian {deb}")
