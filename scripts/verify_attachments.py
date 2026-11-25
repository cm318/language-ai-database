from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "language_ai_cases.db"
RAW_ROOT = ROOT / "raw_files"
RAW_ZIP = Path(os.environ.get("LANGUAGE_AI_RAW_ZIP", str(ROOT / "所有学校数据.zip")))
SUMMARY_REPORT = ROOT / "quality_reports" / "attachment_verification.json"
MANIFEST_REPORT = ROOT / "quality_reports" / "attachment_manifest.csv"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not RAW_ZIP.is_file():
        raise FileNotFoundError(f"找不到原始学校 ZIP：{RAW_ZIP}；请设置 LANGUAGE_AI_RAW_ZIP 环境变量。")
    db_hash_before = sha256_file(DB)
    zip_hash = sha256_file(RAW_ZIP)
    zip_records: dict[str, dict] = {}
    with ZipFile(RAW_ZIP) as z:
        for info in z.infolist():
            if info.is_dir() or info.filename.endswith(".DS_Store"):
                continue
            rel = PurePosixPath(info.filename)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"unsafe path: {rel}")
            data = z.read(info)
            zip_records[rel.as_posix()] = {
                "size": len(data),
                "sha256": sha256_bytes(data),
                "data": data,
            }

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    attachments = [dict(r) for r in con.execute("SELECT * FROM attachments ORDER BY local_path")]
    con.close()
    db_paths = {r["local_path"] for r in attachments}
    disk_paths = {
        p.relative_to(ROOT).as_posix()
        for p in RAW_ROOT.rglob("*")
        if p.is_file() and not p.name.endswith(".DS_Store")
    }
    zip_db_paths = {f"raw_files/{p}" for p in zip_records}

    rows: list[dict] = []
    all_failures: list[str] = []
    for item in attachments:
        rel = item["local_path"]
        zip_rel = rel.removeprefix("raw_files/")
        path = ROOT / rel
        failures: list[str] = []
        if rel not in zip_db_paths:
            failures.append("数据库路径未出现在上传 ZIP")
            zip_record = None
        else:
            zip_record = zip_records[zip_rel]
        if not path.is_file():
            failures.append("本地副本不存在")
            local_size = None
            local_hash = None
            suffix = ""
            actual_pages = None
            null_targets: list[str] = []
            docx_zip_ok = False
            document_xml_ok = False
        else:
            local_size = path.stat().st_size
            local_hash = sha256_file(path)
            suffix = path.suffix.lower()
            actual_pages = None
            null_targets = []
            docx_zip_ok = False
            document_xml_ok = False
            if local_size != item["file_size_bytes"]:
                failures.append("本地大小与数据库不一致")
            if local_hash != item["file_hash"]:
                failures.append("本地 SHA-256 与数据库不一致")
            if zip_record:
                if local_size != zip_record["size"]:
                    failures.append("本地大小与上传 ZIP 不一致")
                if local_hash != zip_record["sha256"]:
                    failures.append("本地 SHA-256 与上传 ZIP 不一致")
            if item["file_name"] != path.name:
                failures.append("文件名与路径basename不一致")
            if suffix == ".pdf":
                try:
                    actual_pages = len(PdfReader(BytesIO(path.read_bytes()), strict=False).pages)
                    if actual_pages != item["page_count"]:
                        failures.append("PDF 页数与数据库不一致")
                except Exception as exc:
                    failures.append(f"PDF 读取失败：{exc}")
            elif suffix == ".docx":
                if item["page_count"] is not None:
                    failures.append("DOCX 不应登记推算页数")
                try:
                    with ZipFile(path) as docx:
                        bad_member = docx.testzip()
                        docx_zip_ok = bad_member is None
                        if bad_member:
                            failures.append(f"DOCX ZIP 成员 CRC 错误：{bad_member}")
                        if "word/document.xml" not in docx.namelist():
                            failures.append("DOCX 缺少 word/document.xml")
                        else:
                            ET.fromstring(docx.read("word/document.xml"))
                            document_xml_ok = True
                        for member in docx.namelist():
                            if not member.endswith(".rels"):
                                continue
                            root = ET.fromstring(docx.read(member))
                            for relationship in root:
                                target = relationship.attrib.get("Target", "")
                                if target.upper().endswith("/NULL") or target.upper() == "NULL":
                                    null_targets.append(f"{member}:{target}")
                except Exception as exc:
                    failures.append(f"DOCX 结构读取失败：{exc}")
                expected_status = "requires_xml_fallback" if null_targets else "registered_only"
                if item["extraction_status"] != expected_status:
                    failures.append(f"DOCX 解析状态应为 {expected_status}")
            else:
                failures.append(f"未知附件扩展名：{suffix}")
        for field, expected, label in [
            ("storage_status", "local_copy_present", "本地保存状态"),
            ("download_permission", "unknown", "公开下载许可"),
        ]:
            if item[field] != expected:
                failures.append(f"{label}应为 {expected}")
        if item["official_url"] is not None:
            failures.append("附件官方 URL 不应在登记阶段推断")
        if item["access_date"] is not None:
            failures.append("附件实际访问日期不应在登记阶段推断")
        if failures:
            all_failures.extend(f"{item['attachment_id']}：{x}" for x in failures)
        rows.append({
            "attachment_id": item["attachment_id"],
            "university_id": item["university_id"],
            "file_name": item["file_name"],
            "local_path": rel,
            "file_size_bytes": local_size,
            "sha256": local_hash,
            "pdf_pages_actual": actual_pages,
            "pdf_pages_database": item["page_count"],
            "docx_zip_crc_ok": docx_zip_ok if suffix == ".docx" else None,
            "docx_document_xml_ok": document_xml_ok if suffix == ".docx" else None,
            "docx_null_relationship_targets": "；".join(null_targets),
            "extraction_status": item["extraction_status"],
            "download_permission": item["download_permission"],
            "verification_status": "pass" if not failures else "fail",
            "issues": "；".join(failures),
        })

    set_checks = {
        "zip_attachment_count_is_72": len(zip_records) == 72,
        "database_attachment_count_is_72": len(attachments) == 72,
        "disk_attachment_count_is_72": len(disk_paths) == 72,
        "zip_and_database_paths_match": zip_db_paths == db_paths,
        "zip_and_disk_paths_match": zip_db_paths == disk_paths,
        "docx_count_is_56": sum(PurePosixPath(p).suffix.lower() == ".docx" for p in zip_records) == 56,
        "pdf_count_is_16": sum(PurePosixPath(p).suffix.lower() == ".pdf" for p in zip_records) == 16,
    }
    for name, ok in set_checks.items():
        if not ok:
            all_failures.append(f"集合核验失败：{name}")

    with MANIFEST_REPORT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    special_docx = [r for r in rows if r["extraction_status"] == "requires_xml_fallback"]
    report = {
        "verification_time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "raw_zip_path": str(RAW_ZIP),
        "raw_zip_sha256": zip_hash,
        "database_sha256_before": db_hash_before,
        "database_sha256_after": sha256_file(DB),
        "database_unchanged": db_hash_before == sha256_file(DB),
        "zip_attachment_count": len(zip_records),
        "database_attachment_count": len(attachments),
        "disk_attachment_count": len(disk_paths),
        "docx_count": sum(r["local_path"].lower().endswith(".docx") for r in rows),
        "pdf_count": sum(r["local_path"].lower().endswith(".pdf") for r in rows),
        "pdf_total_pages": sum(r["pdf_pages_actual"] or 0 for r in rows),
        "docx_requires_xml_fallback_count": len(special_docx),
        "docx_requires_xml_fallback": [
            {"attachment_id": r["attachment_id"], "local_path": r["local_path"], "null_relationship_targets": r["docx_null_relationship_targets"]}
            for r in special_docx
        ],
        "all_download_permissions_unknown": all(r["download_permission"] == "unknown" for r in rows),
        "set_checks": set_checks,
        "passed_files": sum(r["verification_status"] == "pass" for r in rows),
        "failed_files": sum(r["verification_status"] == "fail" for r in rows),
        "failure_count": len(all_failures),
        "failures": all_failures,
        "manifest_csv": "quality_reports/attachment_manifest.csv",
        "status": "pass" if not all_failures and db_hash_before == sha256_file(DB) else "fail",
    }
    SUMMARY_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
