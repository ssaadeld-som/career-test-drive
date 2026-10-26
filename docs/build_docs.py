"""Build self-contained report.html and slides.html (screenshots embedded as base64 JPEG).

    python docs/build_docs.py
"""
import base64, re, subprocess, tempfile
from pathlib import Path

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parent
SHOTS = DOCS / "shots"


def data_uri(name: str, width: int = 1600) -> str:
    src = SHOTS / f"{name}.png"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"{name}.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "--resampleWidth", str(width),
                        str(src), "--out", str(out)], check=True, capture_output=True)
        return "data:image/jpeg;base64," + base64.b64encode(out.read_bytes()).decode()


def build(src: str, dst: str) -> None:
    html = (DOCS / src).read_text(encoding="utf-8")
    cache: dict[str, str] = {}
    html = re.sub(r"\{\{img:([a-z0-9_]+)\}\}", lambda m: cache.setdefault(m.group(1), data_uri(m.group(1))), html)
    (ROOT / dst).write_text(html, encoding="utf-8")
    print(dst, f"{len(html) / 1e6:.1f} MB, {len(cache)} images")


build("report_src.html", "report.html")
if (DOCS / "slides_src.html").exists():
    build("slides_src.html", "slides.html")
