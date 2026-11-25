from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "language_ai_cases.db"
ARCHIVE = ROOT / "data" / "language_ai_cases.db.gz"
MANIFEST = ROOT / "data" / "database_manifest.json"
BUILD = Path("/tmp/language_ai_cases.deploy.db.gz")
STAGING = ROOT / "data" / "language_ai_cases.promoting.db.gz"
REPORT = ROOT / "quality_reports" / "deployment_database.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_compressed(path: Path, expected_hash: str, expected_bytes: int) -> None:
    digest = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if size != expected_bytes or digest.hexdigest() != expected_hash:
        raise AssertionError("压缩副本解压后的字节数或 SHA-256 与正式数据库不一致")


def main() -> None:
    database_hash = sha256(DB)
    database_bytes = DB.stat().st_size
    for path in (BUILD, STAGING):
        if path.exists():
            path.unlink()

    # mtime=0 且不写入原文件名，确保同一数据库可重复生成相同 gzip 字节。
    with BUILD.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as output:
            with DB.open("rb") as source:
                for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                    output.write(chunk)
    verify_compressed(BUILD, database_hash, database_bytes)

    # 挂载卷对 sendfile 的支持不稳定，显式流式复制并核对哈希。
    with BUILD.open("rb") as source, STAGING.open("wb") as target:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            target.write(chunk)
    if sha256(STAGING) != sha256(BUILD):
        raise AssertionError("压缩数据库写回项目目录后哈希不一致")
    verify_compressed(STAGING, database_hash, database_bytes)
    os.replace(STAGING, ARCHIVE)

    manifest = {
        "format": "sqlite3",
        "database_file": DB.name,
        "compressed_file": ARCHIVE.name,
        "compression": "gzip",
        "bytes": database_bytes,
        "sha256": database_hash,
        "compressed_bytes": ARCHIVE.stat().st_size,
        "compressed_sha256": sha256(ARCHIVE),
    }
    staging_manifest = MANIFEST.with_suffix(".promoting.json")
    staging_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if json.loads(staging_manifest.read_text(encoding="utf-8")) != manifest:
        raise AssertionError("数据库部署清单写回复核失败")
    os.replace(staging_manifest, MANIFEST)

    report = {
        "verification_time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        **manifest,
        "roundtrip_verified": True,
        "content_reduced": False,
        "note": "压缩副本保留完整 SQLite 字节内容；应用启动时解压并复核 SHA-256。",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
