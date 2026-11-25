from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import fitz
import olefile
from oletools.oleobj import OleNativeStream

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw_files"
OUT = ROOT / "derived" / "embedded"
MANIFEST = ROOT / "quality_reports" / "source_audit" / "embedded_files_manifest.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def school_name(path: Path) -> str:
    return re.sub(r"-2\.0$", "", path.stem)


def recover_name(value: str) -> str:
    for encoding in ("gb18030", "utf-8"):
        try:
            return value.encode("latin1").decode(encoding)
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return value


def safe_name(value: str) -> str:
    value = value.replace("/", "_").replace("\\", "_").replace("\x00", "")
    return re.sub(r"[\x00-\x1f:*?\"<>|]", "_", value).strip() or "embedded.pdf"


def main():
    records = []
    for path in sorted(RAW.rglob("*.docx")):
        with ZipFile(path) as z:
            entries = [n for n in z.namelist() if "embeddings/" in n and n.endswith(".bin")]
            for entry in entries:
                ole_data = z.read(entry)
                ole = olefile.OleFileIO(BytesIO(ole_data))
                streams = [s for s in ole.listdir() if s[-1] == "\x01Ole10Native"]
                for stream in streams:
                    native = OleNativeStream(ole.openstream(stream).read())
                    if native.is_link or not native.data:
                        records.append({"container": str(path.relative_to(ROOT)), "entry": entry,
                                        "status": "linked_not_embedded", "source_path": native.src_path})
                        continue
                    original_name = recover_name(native.filename)
                    suffix = Path(original_name).suffix or ".bin"
                    stem = safe_name(Path(original_name).stem)
                    object_name = Path(entry).stem
                    filename = safe_name(f"{stem}__{object_name}{suffix}")
                    target = OUT / school_name(path) / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() and sha(target.read_bytes()) != sha(native.data):
                        raise RuntimeError(f"拒绝覆盖不同内容：{target}")
                    target.write_bytes(native.data)
                    item = {
                        "school": school_name(path), "container": str(path.relative_to(ROOT)),
                        "container_sha256": sha(path.read_bytes()), "entry": entry,
                        "embedded_original_name": original_name,
                        "embedded_source_path": recover_name(native.src_path or ""),
                        "local_path": str(target.relative_to(ROOT)), "bytes": len(native.data),
                        "sha256": sha(native.data), "status": "extracted",
                        "pdf_pages": len(fitz.open(stream=native.data, filetype="pdf")) if native.data.startswith(b"%PDF") else None,
                    }
                    records.append(item)
                ole.close()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"embedded_objects": len(records),
                      "extracted_files": sum(x["status"] == "extracted" for x in records),
                      "pdf_pages": sum(x.get("pdf_pages") or 0 for x in records),
                      "files": [{k: x.get(k) for k in ("school", "embedded_original_name", "local_path", "sha256", "pdf_pages")}
                                for x in records]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
