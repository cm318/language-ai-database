from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "language_ai_cases.db"
XLSX = ROOT / "data" / "language_ai_cases.xlsx"
V1_DIR = ROOT / "backups" / "v1_original"
V1_DB = V1_DIR / "data" / "language_ai_cases.db"
REPORTS = ROOT / "quality_reports"
TABLES = [
    "universities", "programs", "objectives", "courses", "faculty", "practice",
    "evaluation", "organizations", "sources", "program_course", "faculty_organization",
    "research_projects", "research_project_links", "research_outputs", "research_output_links",
    "student_development", "attachments", "raw_fragments", "source_links", "review_issues", "import_batches",
]
OLD_TABLES = ["universities", "programs", "objectives", "courses", "faculty", "practice", "evaluation", "organizations", "sources"]
PK = {
    "universities": "university_id", "programs": "program_id", "objectives": "objective_id",
    "courses": "course_id", "faculty": "faculty_id", "practice": "practice_id",
    "evaluation": "evaluation_id", "organizations": "organization_id", "sources": "source_id",
    "program_course": "program_course_id", "faculty_organization": "faculty_organization_id",
    "research_projects": "project_id", "research_project_links": "project_link_id",
    "research_outputs": "output_id", "research_output_links": "output_link_id",
    "student_development": "development_id", "attachments": "attachment_id",
    "raw_fragments": "fragment_id", "source_links": "link_id", "review_issues": "issue_id",
    "import_batches": "batch_id",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(value):
    # Excel 保存后，空字符串单元格与真正空白单元格均回读为 None；按同一空值语义核对。
    return None if value == "" else value


def verify_v1() -> dict:
    manifest = json.loads((V1_DIR / "backup_manifest.json").read_text(encoding="utf-8"))
    backup_files = []
    for item in manifest["files"]:
        path = V1_DIR / item["path"]
        actual_hash = sha(path)
        backup_files.append({
            "path": item["path"], "expected_sha256": item["sha256"], "actual_sha256": actual_hash,
            "bytes_match": path.stat().st_size == item["bytes"], "hash_match": actual_hash == item["sha256"],
        })
    old = sqlite3.connect(f"file:{V1_DB}?mode=ro", uri=True)
    new = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    old.row_factory = sqlite3.Row
    new.row_factory = sqlite3.Row
    program_uid = {r["program_id"]: r["university_id"] for r in old.execute("SELECT program_id,university_id FROM programs")}

    def row_uid(row):
        return row.get("university_id") or program_uid[row["program_id"]]

    per_table = []
    raw_mismatches = []
    legacy_differences = []
    per_university = {uid: {"raw_row_mismatches": 0, "legacy_field_differences": 0, "v1_rows": 0} for uid in ["U001", "U002", "U003", "U004"]}
    for table in OLD_TABLES:
        pk = PK[table]
        old_rows = sorted([dict(r) for r in old.execute(f"SELECT * FROM {table}")], key=lambda r: r[pk])
        view_rows = sorted([dict(r) for r in new.execute(f"SELECT * FROM v_legacy_{table}")], key=lambda r: r[pk])
        table_raw = 0
        table_legacy = 0
        for row in old_rows:
            uid = row_uid(row)
            per_university[uid]["v1_rows"] += 1
            stored = new.execute(f"SELECT raw_text FROM {table} WHERE {pk}=?", (row[pk],)).fetchone()
            if stored is None or json.loads(stored[0]) != row:
                mismatch = {"table": table, "id": row[pk], "university_id": uid}
                raw_mismatches.append(mismatch)
                per_university[uid]["raw_row_mismatches"] += 1
                table_raw += 1
        old_by_id = {r[pk]: r for r in old_rows}
        view_by_id = {r[pk]: r for r in view_rows}
        # 全量导入后兼容视图包含所有已提取高校；V1 无损核对只逐条检查旧记录 ID。
        # 新增高校和新增业务记录单独计数，不作为 V1 差异，也不能掩盖旧记录缺失或字段变化。
        for record_id in sorted(old_by_id):
            a = old_by_id.get(record_id)
            b = view_by_id.get(record_id)
            uid = row_uid(a or b)
            if a is None or b is None:
                legacy_differences.append({"table": table, "id": record_id, "university_id": uid, "field": "__record__", "v1_present": a is not None, "v2_present": b is not None})
                per_university[uid]["legacy_field_differences"] += 1
                table_legacy += 1
                continue
            for field in a:
                if a[field] != b.get(field):
                    legacy_differences.append({"table": table, "id": record_id, "university_id": uid, "field": field, "v1": a[field], "v2": b.get(field)})
                    per_university[uid]["legacy_field_differences"] += 1
                    table_legacy += 1
        per_table.append({
            "table": table, "v1_records": len(old_rows), "v2_legacy_records": len(view_rows),
            "v2_additional_records_not_in_v1": len(set(view_by_id) - set(old_by_id)),
            "raw_row_mismatches": table_raw, "legacy_field_differences": table_legacy,
        })
    integrity = new.execute("PRAGMA integrity_check").fetchone()[0]
    fk_errors = len(new.execute("PRAGMA foreign_key_check").fetchall())
    old.close()
    new.close()
    result = {
        "verification_time": now(), "v1_db_sha256": sha(V1_DB), "v2_db_sha256": sha(DB),
        "comparison_scope": "逐条核对 V1 原记录 ID、raw_text 完整原行及兼容视图旧字段；V2 新增记录只计数，不作为差异。",
        "backup_file_count": len(backup_files), "backup_files": backup_files,
        "v1_total_rows": sum(x["v1_records"] for x in per_table),
        "raw_row_mismatches": len(raw_mismatches), "legacy_field_differences": len(legacy_differences),
        "integrity_check": integrity, "foreign_key_errors": fk_errors,
        "per_table": per_table, "per_university": per_university,
        "raw_mismatch_details": raw_mismatches, "legacy_difference_details": legacy_differences,
        "status": "pass" if all(x["hash_match"] and x["bytes_match"] for x in backup_files) and not raw_mismatches and not legacy_differences and integrity == "ok" and fk_errors == 0 else "fail",
    }
    (REPORTS / "final_legacy_comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def compare_sheet(con, wb, table, sheet_name=None) -> dict:
    from itertools import zip_longest

    sheet_name = sheet_name or table
    ws = wb[sheet_name]
    if table == "quality_view":
        db_cursor = con.execute("SELECT * FROM v_university_quality ORDER BY university_id")
        headers = [r[1] for r in con.execute("PRAGMA table_info(v_university_quality)")]
    else:
        headers = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        db_cursor = con.execute(f"SELECT * FROM {table} ORDER BY {PK[table]}")
    excel_cursor = ws.iter_rows(values_only=True)
    excel_headers = list(next(excel_cursor, ()))
    differences = []
    if headers != excel_headers:
        differences.append({"cell": "header", "expected": headers, "actual": excel_headers})
    compared_cells = 0
    records = 0
    missing = object()
    for row_index, (record, excel_row) in enumerate(zip_longest(db_cursor, excel_cursor, fillvalue=missing), 2):
        if record is missing or excel_row is missing:
            differences.append({"cell": f"row:{row_index}", "reason": "SQLite 与 Excel 行数不一致"})
            continue
        records += 1
        for col_index, field in enumerate(headers):
            expected = normalize(record[field])
            actual = normalize(excel_row[col_index] if col_index < len(excel_row) else None)
            compared_cells += 1
            if expected != actual and len(differences) < 200:
                differences.append({"cell": f"{get_column_letter(col_index + 1)}{row_index}", "field": field, "sqlite": expected, "excel": actual})
            elif expected != actual:
                differences.append({"cell": "more", "reason": "差异超过200条，后续仅计数"})
    return {"sheet": sheet_name, "records": records, "compared_cells": compared_cells, "difference_count": len(differences), "differences": differences[:200]}


def verify_excel() -> dict:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    wb = load_workbook(XLSX, data_only=False, read_only=True)
    cached = load_workbook(XLSX, data_only=True, read_only=True)
    expected_sheets = ["说明", "表清单"] + TABLES + ["质量概览", "数据字典"]
    sheet_results = [compare_sheet(con, wb, table) for table in TABLES]
    sheet_results.append(compare_sheet(con, wb, "quality_view", "质量概览"))
    formulas = []
    missing_cache = []
    formula_errors = []
    for sheet_name in ("说明", "表清单"):
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
                    formulas.append(f"{ws.title}!{cell.coordinate}")
                    value = cached[ws.title][cell.coordinate].value
                    if value is None:
                        missing_cache.append(f"{ws.title}!{cell.coordinate}")
                    if isinstance(value, str) and value.startswith("#"):
                        formula_errors.append({"cell": f"{ws.title}!{cell.coordinate}", "value": value})
    table_count_differences = []
    for row_index, row in enumerate(wb["表清单"].iter_rows(min_row=2, values_only=True), 2):
        table = row[0]
        actual = cached["表清单"].cell(row=row_index, column=3).value
        expected = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        if actual != expected:
            table_count_differences.append({"table": table, "sqlite": expected, "excel_cached": actual})
    metric_labels = (
        "已登记高校", "已结构化高校", "培养项目／路径", "课程／研究主题", "项目—课程关系",
        "科研项目", "科研成果", "学生发展", "原始附件", "原文片段", "证据关系",
        "待核验事项", "V1 原行差异", "V1 兼容字段差异",
    )
    intro_metrics = {}
    for row in range(4, cached["说明"].max_row + 1):
        label = cached["说明"].cell(row, 1).value
        if label in metric_labels:
            intro_metrics[label] = cached["说明"].cell(row, 2).value
    def db_count(table):
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    expected_metrics = {
        "已登记高校": db_count("universities"),
        "已结构化高校": con.execute("SELECT count(*) FROM universities WHERE data_status<>'not_started'").fetchone()[0],
        "培养项目／路径": db_count("programs"), "课程／研究主题": db_count("courses"),
        "项目—课程关系": db_count("program_course"), "科研项目": db_count("research_projects"),
        "科研成果": db_count("research_outputs"), "学生发展": db_count("student_development"),
        "原始附件": db_count("attachments"), "原文片段": db_count("raw_fragments"),
        "证据关系": db_count("source_links"),
        "待核验事项": con.execute("SELECT count(*) FROM review_issues WHERE status IN ('open','in_review')").fetchone()[0],
        "V1 原行差异": 0, "V1 兼容字段差异": 0,
    }
    gate = json.loads((REPORTS / "excel_verify.json").read_text(encoding="utf-8"))
    recalc = json.loads((REPORTS / "excel_recalc_result.json").read_text(encoding="utf-8"))
    result = {
        "verification_time": now(), "sqlite_sha256": sha(DB), "xlsx_sha256": sha(XLSX),
        "xlsx_bytes": XLSX.stat().st_size, "sheet_count": len(wb.sheetnames), "sheet_names_match": wb.sheetnames == expected_sheets,
        "comparison_scope": "21 张数据表＋质量概览；Excel 空字符串与空白单元格统一按空值核对。",
        "compared_cells": sum(x["compared_cells"] for x in sheet_results),
        "difference_count": sum(x["difference_count"] for x in sheet_results) + len(table_count_differences),
        "sheet_results": sheet_results, "table_count_formula_differences": table_count_differences,
        "dictionary_fields": wb["数据字典"].max_row - 1, "formula_count": len(formulas),
        "formula_cache_missing_count": len(missing_cache), "formula_error_count": len(formula_errors),
        "missing_cache_cells": missing_cache, "formula_errors": formula_errors,
        "intro_metrics": intro_metrics, "intro_metrics_match": intro_metrics == expected_metrics,
        "recalc_result": recalc, "gate_result": gate,
        "status": "pass",
    }
    expected_dictionary_fields = sum(len(con.execute(f"PRAGMA table_info({table})").fetchall()) for table in TABLES)
    expected_formula_count = len(TABLES) + 12
    if not (
        result["sheet_names_match"] and result["difference_count"] == 0 and result["dictionary_fields"] == expected_dictionary_fields
        and len(formulas) == expected_formula_count and not missing_cache and not formula_errors and result["intro_metrics_match"]
        and recalc.get("status") == "success" and recalc.get("delivery_file_recalculated") is True
        and gate.get("status") == "pass" and gate.get("formula_count") == expected_formula_count
    ):
        result["status"] = "fail"
    (REPORTS / "excel_sqlite_consistency.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    wb.close()
    cached.close()
    con.close()
    return result


def verify_full_attachments() -> dict:
    import zipfile
    import pymupdf

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM attachments ORDER BY attachment_id")]
    results = []
    for row in rows:
        path = (ROOT / row["local_path"]).resolve()
        try:
            path.relative_to(ROOT)
            safe = True
        except ValueError:
            safe = False
        item = {"attachment_id": row["attachment_id"], "university_id": row["university_id"], "path": row["local_path"], "checks": {}}
        item["checks"]["safe_path"] = safe
        item["checks"]["exists"] = safe and path.is_file()
        if item["checks"]["exists"]:
            item["checks"]["bytes"] = path.stat().st_size == row["file_size_bytes"]
            item["checks"]["sha256"] = sha(path) == row["file_hash"]
            if path.suffix.lower() == ".pdf":
                with pymupdf.open(path) as document:
                    actual_pages = len(document)
                item["actual_pages"] = actual_pages
                item["checks"]["pages"] = actual_pages == row["page_count"]
            elif path.suffix.lower() == ".docx":
                with zipfile.ZipFile(path) as archive:
                    item["checks"]["docx_crc"] = archive.testzip() is None
                    item["checks"]["document_xml"] = "word/document.xml" in archive.namelist()
        item["checks"]["allowed"] = row["download_permission"] == "allowed"
        item["checks"]["parsed"] = row["extraction_status"] == "parsed"
        item["passed"] = bool(item["checks"]) and all(item["checks"].values())
        results.append(item)
    pdf_pages = sum(x.get("actual_pages", 0) for x in results)
    summary = {
        "verification_time": now(), "database_sha256": sha(DB), "attachment_count": len(rows),
        "docx_count": sum(Path(x["local_path"]).suffix.lower() == ".docx" for x in rows),
        "pdf_count": sum(Path(x["local_path"]).suffix.lower() == ".pdf" for x in rows),
        "pdf_pages": pdf_pages, "allowed_count": sum(x["download_permission"] == "allowed" for x in rows),
        "parsed_count": sum(x["extraction_status"] == "parsed" for x in rows),
        "passed_files": sum(x["passed"] for x in results), "failed_files": sum(not x["passed"] for x in results),
        "permission_note": "全部附件由用户明确授权公开下载；授权不等于官方来源已核验。",
        "files": results,
    }
    summary["status"] = "pass" if (
        len(rows) == 80 and summary["docx_count"] == 56 and summary["pdf_count"] == 24
        and pdf_pages == 222 and summary["allowed_count"] == 80 and summary["parsed_count"] == 80
        and summary["failed_files"] == 0
    ) else "fail"
    con.close()
    (REPORTS / "full_attachment_verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def verify_browser() -> dict:
    report_path = ROOT / "tests" / "v2_browser_results.json"
    raw = json.loads(report_path.read_text(encoding="utf-8"))
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    expected_counts = {
        "已登记高校": con.execute("SELECT count(*) FROM universities").fetchone()[0],
        "培养项目／路径": con.execute("SELECT count(*) FROM programs").fetchone()[0],
        "课程／研究主题": con.execute("SELECT count(*) FROM courses").fetchone()[0],
        "科研项目": con.execute("SELECT count(*) FROM research_projects").fetchone()[0],
        "科研成果": con.execute("SELECT count(*) FROM research_outputs").fetchone()[0],
        "证据关系": con.execute("SELECT count(*) FROM source_links").fetchone()[0],
    }
    con.close()
    checks = raw.get("checks", [])
    downloads = raw.get("downloads", [])
    required_pages = {"数据库首页", "高校详情", "科研与学生发展", "来源与证据", "附件下载"}
    pages = set(raw.get("pages_tested", []))
    valid = (
        raw.get("status") == "pass" and raw.get("app_sha256") == sha(ROOT / "app.py")
        and raw.get("database_sha256") == sha(DB) and required_pages <= pages
        and checks and all(x.get("passed") for x in checks)
        and raw.get("observed_counts") == expected_counts and raw.get("expected_counts") == expected_counts
        and len(downloads) == 80 and all(x.get("passed") for x in downloads)
        and not raw.get("console_errors") and not raw.get("server_errors")
        and raw.get("mobile", {}).get("passed") is True
    )
    result = dict(raw)
    result.update({
        "verification_time": now(), "verified_app_sha256": sha(ROOT / "app.py"), "verified_database_sha256": sha(DB),
        "check_count": len(checks), "passed_count": sum(bool(x.get("passed")) for x in checks),
        "failed_count": sum(not bool(x.get("passed")) for x in checks),
        "download_count": len(downloads), "observed_counts_match": raw.get("observed_counts") == expected_counts,
        "status": "pass" if valid else "fail",
    })
    (REPORTS / "browser_regression.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    db_hash_before = sha(DB)
    xlsx_hash_before = sha(XLSX)
    legacy = verify_v1()
    excel = verify_excel()
    browser = verify_browser()
    constraints = json.loads((REPORTS / "constraint_tests.json").read_text(encoding="utf-8"))
    attachments = verify_full_attachments()
    full_import = json.loads((REPORTS / "full_import_summary.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((REPORTS / "database_bootstrap_test.json").read_text(encoding="utf-8"))
    deployment = json.loads((REPORTS / "deployment_database.json").read_text(encoding="utf-8"))
    archive = ROOT / "data" / "language_ai_cases.db.gz"
    bootstrap_pass = (
        bootstrap.get("status") == "pass" and bootstrap.get("compressed_only") is True
        and bootstrap.get("exception_count") == 0 and bootstrap.get("observed_counts") == bootstrap.get("expected_counts")
        and bootstrap.get("app_sha256") == sha(ROOT / "app.py") and bootstrap.get("database_sha256") == db_hash_before
        and deployment.get("roundtrip_verified") is True and deployment.get("content_reduced") is False
        and deployment.get("sha256") == db_hash_before and deployment.get("compressed_sha256") == sha(archive)
        and deployment.get("compressed_bytes") == archive.stat().st_size
    )
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    object_counts = {
        kind: con.execute("SELECT count(*) FROM sqlite_master WHERE type=?", (kind,)).fetchone()[0]
        for kind in ("table", "view", "trigger")
    }
    object_counts["index"] = con.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchone()[0]
    object_counts["sqlite_autoindex"] = con.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND sql IS NULL").fetchone()[0]
    pk_not_null_failures = []
    for table in TABLES:
        for row in con.execute(f"PRAGMA table_info({table})"):
            if row[5] and not row[3]:
                pk_not_null_failures.append(f"{table}.{row[1]}")
    table_counts = {table: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in TABLES}
    disposition_issues = con.execute("SELECT count(*) FROM v_raw_fragment_disposition_issues").fetchone()[0]
    full_data = {
        "extracted_universities": con.execute("SELECT count(*) FROM universities WHERE data_status='extracted'").fetchone()[0],
        "validated_full_batches": con.execute("SELECT count(*) FROM import_batches WHERE batch_id LIKE 'BFULL_%' AND status='validated'").fetchone()[0],
        "unprocessed_fragments": con.execute("SELECT count(*) FROM raw_fragments WHERE disposition='unprocessed'").fetchone()[0],
        "allowed_attachments": con.execute("SELECT count(*) FROM attachments WHERE download_permission='allowed'").fetchone()[0],
        "parsed_attachments": con.execute("SELECT count(*) FROM attachments WHERE extraction_status='parsed'").fetchone()[0],
        "pdf_pages": con.execute("SELECT coalesce(sum(page_count),0) FROM attachments WHERE local_path LIKE '%.pdf'").fetchone()[0],
        "business_records_without_evidence": con.execute("""SELECT count(*) FROM v_business_records b
            LEFT JOIN source_links s ON s.entity_type=b.entity_type AND s.entity_id=b.entity_id
            WHERE s.link_id IS NULL""").fetchone()[0],
    }
    con.close()
    full_data_pass = (
        full_data["extracted_universities"] == 56 and full_data["validated_full_batches"] == 56
        and full_data["unprocessed_fragments"] == 0 and full_data["allowed_attachments"] == 80
        and full_data["parsed_attachments"] == 80 and full_data["pdf_pages"] == 222
        and full_data["business_records_without_evidence"] == 0
        and full_import.get("mode") == "full" and full_import.get("promoted") is True
        and full_import.get("database_sha256") == db_hash_before
    )
    component_statuses = {
        "v1_lossless_migration": legacy["status"], "excel_sqlite_consistency": excel["status"],
        "browser_regression": browser["status"], "database_constraints": constraints["status"],
        "attachment_integrity": attachments["status"], "full_data_gates": "pass" if full_data_pass else "fail",
        "compressed_database_bootstrap": "pass" if bootstrap_pass else "fail",
    }
    structure_pass = (
        object_counts["table"] == 21 and object_counts["view"] == 17 and object_counts["trigger"] == 44
        and object_counts["index"] == 47 and not pk_not_null_failures and disposition_issues == 0
    )
    unchanged = db_hash_before == sha(DB) and xlsx_hash_before == sha(XLSX)
    result = {
        "verification_time": now(), "object_counts": object_counts, "primary_key_not_null_failures": pk_not_null_failures,
        "raw_fragment_disposition_issues": disposition_issues, "structure_status": "pass" if structure_pass else "fail",
        "full_data": full_data, "full_data_status": "pass" if full_data_pass else "fail",
        "compressed_database": {"status": "pass" if bootstrap_pass else "fail", "bytes": archive.stat().st_size, "sha256": sha(archive), "bootstrap_app_sha256": bootstrap.get("app_sha256")},
        "table_counts": table_counts, "component_statuses": component_statuses,
        "database_and_excel_unchanged_during_verification": unchanged,
        "status": "pass" if structure_pass and unchanged and all(x == "pass" for x in component_statuses.values()) else "fail",
    }
    (REPORTS / "final_acceptance_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": result["status"], "object_counts": object_counts, "v1_total_rows": legacy["v1_total_rows"],
        "raw_row_mismatches": legacy["raw_row_mismatches"], "legacy_field_differences": legacy["legacy_field_differences"],
        "excel_compared_cells": excel["compared_cells"], "excel_differences": excel["difference_count"],
        "excel_formulas": excel["formula_count"], "browser_checks": browser["check_count"],
        "browser_failures": browser["failed_count"], "constraint_tests": constraints["test_count"],
        "attachment_files": attachments["passed_files"], "database_and_excel_unchanged": unchanged,
    }, ensure_ascii=False, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
