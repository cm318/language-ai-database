from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent
DEST = OUTPUT / "语言AI数据库_V2全量结构化版_最终成果.zip"
MANIFEST = ROOT / "交付文件清单.json"
ARCHIVE_ROOT = "language_ai_v2"
REPORTS = ROOT / "quality_reports"

ROOT_FILES = [
    ".gitignore", ".streamlit/config.toml", "README.md", "部署说明.md",
    "app.py", "requirements.txt",
    "data/language_ai_cases.db", "data/language_ai_cases.db.gz",
    "data/database_manifest.json", "data/language_ai_cases.xlsx",
]
QUALITY_FILES = [
    "80份附件完整性核验报告.md", "全量结构化验收报告.md", "阶段总体验收报告.md",
    "browser_regression.json", "constraint_tests.json", "database_bootstrap_test.json",
    "deployment_database.json", "deployment_status.json", "repository_sync.json",
    "excel_recalc_result.json", "excel_sqlite_consistency.json", "excel_verify.json",
    "excel_verify_tool_raw.json", "final_acceptance_checks.json", "final_legacy_comparison.json",
    "full_attachment_verification.json", "full_import_summary.json", "full_quality_summary.json",
    "repository_bootstrap_test.json", "online_precheck.json",
]
TEST_FILES = [
    "tests/run_v2_browser.py", "tests/v2_browser_results.json",
    "tests/final_browser_console.log", "tests/final_compare_snapshot.yml",
    "tests/final_detail_snapshot.yml", "tests/final_home_snapshot.yml",
    "tests/final_sources_snapshot.yml", "tests/streamlit_final.log",
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not value or "\\" in value:
        raise ValueError(f"不安全路径：{value!r}")
    return path.as_posix()


def add_file(files: dict[str, Path], value: str) -> None:
    rel = safe_relative(value)
    source = ROOT / rel
    if not source.is_file():
        raise FileNotFoundError(f"缺少必要交付文件：{rel}")
    if rel in files:
        raise RuntimeError(f"交付路径重复：{rel}")
    files[rel] = source


def collect_files() -> tuple[dict[str, Path], list[sqlite3.Row]]:
    acceptance = json.loads((REPORTS / "final_acceptance_checks.json").read_text(encoding="utf-8"))
    quality = json.loads((REPORTS / "full_quality_summary.json").read_text(encoding="utf-8"))
    if acceptance.get("status") != "pass" or quality.get("status") != "pass":
        raise RuntimeError("全量最终验收未通过，停止打包")
    if quality.get("school_reports") != 56:
        raise RuntimeError("56 校逐校质量报告不完整，停止打包")

    files: dict[str, Path] = {}
    for rel in ROOT_FILES + TEST_FILES:
        add_file(files, rel)
    for folder in ("schema", "scripts"):
        for source in sorted((ROOT / folder).glob("*")):
            if source.is_file() and source.suffix in {".py", ".sql", ".md"}:
                add_file(files, source.relative_to(ROOT).as_posix())
    for name in QUALITY_FILES:
        add_file(files, f"quality_reports/{name}")
    for source in sorted((REPORTS / "schools").glob("U*_质量报告.md")):
        add_file(files, source.relative_to(ROOT).as_posix())
    for source in sorted((ROOT / "backups").rglob("*")):
        if source.is_file():
            add_file(files, source.relative_to(ROOT).as_posix())
    for source in sorted((ROOT / "tests/v2_screens").glob("*.png")):
        add_file(files, source.relative_to(ROOT).as_posix())

    con = sqlite3.connect(f"file:{ROOT / 'data/language_ai_cases.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    attachments = list(con.execute(
        """SELECT attachment_id,local_path,file_size_bytes,file_hash,
                  extraction_status,download_permission
           FROM attachments ORDER BY attachment_id"""
    ))
    con.close()
    if len(attachments) != 80:
        raise RuntimeError(f"登记附件应为 80 份，实际 {len(attachments)}")
    for row in attachments:
        if row["download_permission"] != "allowed" or row["extraction_status"] != "parsed":
            raise RuntimeError(f"附件状态不合格：{row['attachment_id']}")
        add_file(files, row["local_path"])
        source = files[row["local_path"]]
        if source.stat().st_size != row["file_size_bytes"] or sha_file(source) != row["file_hash"]:
            raise RuntimeError(f"附件哈希不一致：{row['local_path']}")

    school_ids = {p.name[:4] for p in (REPORTS / "schools").glob("U*_质量报告.md")}
    if school_ids != {f"U{i:03d}" for i in range(1, 57)}:
        raise RuntimeError("逐校报告不是完整的 U001—U056")
    return files, attachments


def main() -> None:
    files, attachments = collect_files()
    entries = []
    for rel, path in sorted(files.items()):
        entries.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha_file(path)})

    raw_count = sum(rel.startswith("raw_files/") for rel in files)
    embedded_count = sum(rel.startswith("derived/embedded/") for rel in files)
    if raw_count != 72 or embedded_count != 8:
        raise RuntimeError(f"附件数量错误：顶层 {raw_count}，嵌入 {embedded_count}")
    database_manifest = json.loads((ROOT / "data/database_manifest.json").read_text(encoding="utf-8"))
    db = ROOT / "data/language_ai_cases.db"
    archive = ROOT / "data/language_ai_cases.db.gz"
    if sha_file(db) != database_manifest["sha256"] or sha_file(archive) != database_manifest["compressed_sha256"]:
        raise RuntimeError("数据库或压缩副本与部署清单不一致")
    deployment_status = json.loads((REPORTS / "deployment_status.json").read_text(encoding="utf-8"))

    manifest = {
        "project": "世界一流大学‘语言＋人工智能’复合型人才培养模式案例数据库",
        "stage": "V2 全量结构化最终版",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "acceptance_status": "pass",
        "archive_root": ARCHIVE_ROOT,
        "payload_file_count": len(entries),
        "manifest_file": MANIFEST.name,
        "archive_file_count_including_manifest": len(entries) + 1,
        "payload_total_bytes": sum(x["bytes"] for x in entries),
        "university_count": 56,
        "school_quality_report_count": 56,
        "raw_attachment_count": raw_count,
        "embedded_attachment_count": embedded_count,
        "attachment_count": len(attachments),
        "database_bytes": db.stat().st_size,
        "database_sha256": database_manifest["sha256"],
        "compressed_database_bytes": archive.stat().st_size,
        "compressed_database_sha256": database_manifest["compressed_sha256"],
        "github_push_status_at_packaging": deployment_status.get("github", {}).get("push_status"),
        "streamlit_status_at_packaging": deployment_status.get("streamlit", {}).get("deployment_status"),
        "excluded_from_final_zip": [
            ".deps/", ".ocr/", "__pycache__/", "*.pyc", "*.pyo", "*.pid",
            "quality_reports/musepool*/", "quality_reports/source_audit/",
            "quality_reports/*失败试验日志与过程日志", "tests/history/",
            "tests/constraint_*/", "derived/embedded/根目录早期乱码OLE重复文件",
            "未登记的候选库、隔离构建库和临时数据库",
        ],
        "notes": [
            "本清单哈希对应 ZIP 内文件；清单自身不自哈希。",
            "完整 SQLite、gzip 部署副本、同步 Excel 与 80 份已授权附件均保留；未删减任何业务数据。",
            "原始 DOCX／PDF 与历史备份保留；早期乱码 OLE 重复文件和隔离临时库不属于正式交付。",
            "GitHub 与 Streamlit 的实际状态以包内 quality_reports/deployment_status.json 为准；本地打包不代表已推送或上线。",
        ],
        "files": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 在本机临时目录构建，随后显式流式写回挂载卷并原子替换，避免 sendfile 兼容问题。
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(prefix="language_ai_final_", suffix=".zip", delete=False) as handle:
            temporary_name = handle.name
        with ZipFile(temporary_name, "w", compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zipped:
            for rel, path in sorted(files.items()):
                zipped.write(path, f"{ARCHIVE_ROOT}/{rel}")
            zipped.write(MANIFEST, f"{ARCHIVE_ROOT}/{MANIFEST.name}")

        staging = DEST.with_name(DEST.stem + ".building.zip")
        with open(temporary_name, "rb") as source, staging.open("wb") as target:
            for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                target.write(chunk)
        if sha_file(staging) != sha_file(Path(temporary_name)):
            raise IOError("最终 ZIP 写回挂载卷后哈希不一致")
        os.replace(staging, DEST)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)

    with ZipFile(DEST) as zipped:
        bad_member = zipped.testzip()
        zipped_names = set(zipped.namelist())
        expected_names = {f"{ARCHIVE_ROOT}/{rel}" for rel in files} | {f"{ARCHIVE_ROOT}/{MANIFEST.name}"}
        hash_mismatches = []
        for item in entries:
            data = zipped.read(f"{ARCHIVE_ROOT}/{item['path']}")
            if len(data) != item["bytes"] or sha_bytes(data) != item["sha256"]:
                hash_mismatches.append(item["path"])
        zipped_manifest = json.loads(zipped.read(f"{ARCHIVE_ROOT}/{MANIFEST.name}").decode("utf-8"))
        zipped_db_hash = hashlib.sha256()
        with zipped.open(f"{ARCHIVE_ROOT}/data/language_ai_cases.db") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                zipped_db_hash.update(chunk)

    result = {
        "status": "pass" if (
            bad_member is None and zipped_names == expected_names and not hash_mismatches
            and zipped_manifest == manifest and zipped_db_hash.hexdigest() == database_manifest["sha256"]
        ) else "fail",
        "zip_path": str(DEST),
        "zip_bytes": DEST.stat().st_size,
        "zip_sha256": sha_file(DEST),
        "zip_crc_error_member": bad_member,
        "zip_entry_count": len(zipped_names),
        "zip_entry_set_matches": zipped_names == expected_names,
        "zip_payload_hash_mismatches": hash_mismatches,
        "zipped_manifest_matches": zipped_manifest == manifest,
        "zipped_database_sha256": zipped_db_hash.hexdigest(),
        "attachment_count": len(attachments),
        "school_quality_report_count": 56,
    }
    verification = REPORTS / "final_package_verification.json"
    verification.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
