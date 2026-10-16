"""Fetch approved Aurora AutoFill branding into the native installers.

Assets are from the official Aurora AutoFill repository and pinned to a commit.
Local development can run without these assets; the CI build includes them.
"""
from pathlib import Path
from urllib.request import urlopen

COMMIT = "439bd7d869c2f00ac938b015ea378517d28922f5"
BASE = f"https://raw.githubusercontent.com/fabriciomatosqa/AURORA-AutoFill/{COMMIT}/assets/"
DEST = Path(__file__).resolve().parent / "assets"
DEST.mkdir(exist_ok=True)
for name in ("aurora_icon.png", "aurora_icon.ico", "aurora_banner.jpg"):
    with urlopen(BASE + name, timeout=25) as response:
        data = response.read(2_000_001)
        if len(data) > 2_000_000 or len(data) < 1000:
            raise ValueError(f"Invalid branding asset: {name}")
        (DEST / name).write_bytes(data)
    print(f"Branding bundled: {name}")
