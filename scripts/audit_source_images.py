from __future__ import annotations

import concurrent.futures
import json
import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw_files"
OUT = ROOT / "quality_reports" / "source_audit" / "docx_image_ocr.json"
TESS = ROOT / ".ocr" / "tessdata"


def jobs():
    result = []
    for path in sorted(RAW.rglob("*.docx")):
        with ZipFile(path) as z:
            for name in z.namelist():
                if not name.startswith("word/media/") or name.endswith("/"):
                    continue
                data = z.read(name)
                try:
                    with Image.open(BytesIO(data)) as im:
                        width, height = im.size
                except Exception:
                    width = height = None
                result.append({"docx": str(path.relative_to(ROOT)), "media": name,
                               "data": data, "width": width, "height": height})
    return result


def run(job):
    base = {k: v for k, v in job.items() if k != "data"}
    try:
        im = Image.open(BytesIO(job["data"])).convert("RGB")
        if max(im.size) > 2400:
            scale = 2400 / max(im.size)
            im = im.resize((int(im.width * scale), int(im.height * scale)))
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            im.save(f.name)
            cmd = ["tesseract", f.name, "stdout", "--tessdata-dir", str(TESS),
                   "-l", "chi_sim+eng", "--psm", "11"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        text = re.sub(r"[ \t]+", " ", proc.stdout).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return base | {"ocr_text": text, "ocr_chars": len(text),
                       "ocr_status": "ok" if proc.returncode == 0 else "failed",
                       "ocr_error": proc.stderr[-500:] if proc.returncode else None}
    except Exception as exc:
        return base | {"ocr_text": "", "ocr_chars": 0,
                       "ocr_status": "unsupported_or_failed", "ocr_error": str(exc)}


def main():
    items = jobs()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, items))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"images": len(results),
                      "nonempty_20_chars": sum(x["ocr_chars"] >= 20 for x in results),
                      "failed": sum(x["ocr_status"] != "ok" for x in results),
                      "ocr_characters": sum(x["ocr_chars"] for x in results),
                      "failures": [{k: x[k] for k in ("docx", "media", "ocr_error")}
                                   for x in results if x["ocr_status"] != "ok"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
