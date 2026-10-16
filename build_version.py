"""Produce native Windows/Debian version metadata from the *one* app version."""
from pathlib import Path
import re
from aurora_desktop import __version__

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?$")


def native_versions(version: str):
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError("Use X.Y.Z, X.Y.Z-beta.N or X.Y.Z-rc.N")
    a,b,c,label,iteration = match.groups()
    # Windows fixed version uses a numeric 4th component.
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
