from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
V1_DIR = ROOT / "backups" / "v1_original"
V1_DB = V1_DIR / "data" / "language_ai_cases.db"
RAW_ZIP = Path(os.environ.get("LANGUAGE_AI_RAW_ZIP", str(ROOT / "所有学校数据.zip")))
RAW_ROOT = ROOT / "raw_files"
DEST = ROOT / "data" / "language_ai_cases.db"
SCHEMA = ROOT / "schema" / "schema_v2.sql"
NOW = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
PARSER_VERSION = "v1-to-v2-migration-1.0.0"
OLD_TABLES = ["universities", "programs", "objectives", "courses", "faculty", "practice", "evaluation", "organizations", "sources"]
PK = {
    "universities": "university_id", "programs": "program_id", "objectives": "objective_id",
    "courses": "course_id", "faculty": "faculty_id", "practice": "practice_id",
    "evaluation": "evaluation_id", "organizations": "organization_id", "sources": "source_id",
}
DIMENSION = {
    "universities": "university_overview", "programs": "program_overview",
    "objectives": "培养目标", "courses": "课程体系", "faculty": "师资配置",
    "practice": "实践环节", "evaluation": "评价机制", "organizations": "科研平台与相关机构",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_json(row) -> str:
    return json.dumps(dict(row), ensure_ascii=False, separators=(",", ":"))


def insert(con: sqlite3.Connection, table: str, values: dict) -> None:
    cols = list(values)
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
    con.execute(sql, [values[c] for c in cols])


def tag(value):
    return {"是": "yes", "否": "no", "强关联": "yes", "一般": "yes"}.get(value, "unknown")


def clean_doc_school(stem: str) -> str:
    return re.sub(r"-2\.0$", "", stem).strip()


def school_for(path: PurePosixPath) -> str:
    if path.suffix.lower() == ".docx":
        return clean_doc_school(path.stem)
    return re.sub(r"^\d+", "", path.parent.name).strip()


def region_for(path: PurePosixPath) -> str:
    top = path.parts[0]
    if top.startswith(("美国", "北美")):
        return "北美"
    if top.startswith(("英国", "欧洲")):
        return "欧洲"
    if top.startswith("大洋洲"):
        return "大洋洲"
    if top.startswith("中国"):
        return "中国"
    return "亚洲"


def country_for(path: PurePosixPath, school: str) -> str:
    top = path.parts[0]
    if top.startswith("中国"):
        return "中国香港" if school.startswith("香港") else "中国"
    if top.startswith("美国"):
        return "美国"
    if top.startswith("英国"):
        return "英国"
    if top.startswith("日本"):
        return "日本"
    return "待核验"


def extract_raw_files():
    if not RAW_ZIP.is_file():
        raise FileNotFoundError(f"找不到原始学校 ZIP：{RAW_ZIP}；请设置 LANGUAGE_AI_RAW_ZIP 环境变量。")
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    with ZipFile(RAW_ZIP) as z:
        for info in z.infolist():
            if info.is_dir() or info.filename.endswith(".DS_Store"):
                continue
            rel = PurePosixPath(info.filename)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"unsafe path: {rel}")
            data = z.read(info)
            target = RAW_ROOT.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = sha256_bytes(data)
            if target.exists():
                if sha256_file(target) != digest:
                    raise RuntimeError(f"本地附件与原始 ZIP 不一致，停止覆盖：{target}")
            else:
                target.write_bytes(data)
            records.append({
                "path": rel, "school": school_for(rel), "region": region_for(rel),
                "country": country_for(rel, school_for(rel)), "bytes": len(data),
                "sha256": digest, "data": data, "target": target,
            })
    if len(records) != 72:
        raise AssertionError(f"原始附件应为 72 份，实际 {len(records)}")
    if sum(r["path"].suffix.lower() == ".docx" for r in records) != 56:
        raise AssertionError("DOCX 数量不是 56")
    if sum(r["path"].suffix.lower() == ".pdf" for r in records) != 16:
        raise AssertionError("PDF 数量不是 16")
    return records


def verify_v1_backup():
    manifest = json.loads((V1_DIR / "backup_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        p = V1_DIR / item["path"]
        if not p.exists() or sha256_file(p) != item["sha256"]:
            raise RuntimeError(f"V1 备份哈希不一致：{p}")


def pdf_pages(data: bytes):
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    return len(PdfReader(BytesIO(data)).pages)


def main():
    verify_v1_backup()
    raw_files = extract_raw_files()
    old = sqlite3.connect(f"file:{V1_DB}?mode=ro", uri=True)
    old.row_factory = sqlite3.Row
    old_rows = {t: [dict(r) for r in old.execute(f"SELECT * FROM {t}")] for t in OLD_TABLES}

    existing_by_alias = {
        "巴黎萨克雷大学": "U001", "巴黎-萨克雷大学": "U001",
        "宾夕法尼亚大学": "U002", "东京大学": "U003", "南京大学": "U004",
    }
    schools = sorted({r["school"] for r in raw_files})
    if len(schools) != 56:
        raise AssertionError(f"高校数应为 56，实际 {len(schools)}")
    uid_by_school = {s: existing_by_alias[s] for s in schools if s in existing_by_alias}
    next_id = 5
    for school in sorted(s for s in schools if s not in uid_by_school):
        uid_by_school[school] = f"U{next_id:03d}"
        next_id += 1
    school_paths = defaultdict(list)
    for r in raw_files:
        school_paths[r["school"]].append(r["path"].as_posix())

    tmp = ROOT / "data" / "language_ai_cases.building.db"
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("PRAGMA user_version=2")
    con.execute("BEGIN")

    # 高校：4 所旧高校 ID 不变；其余仅登记附件身份，不进入旧网页结构化统计。
    for r in old_rows["universities"]:
        website = r["official_website"] if str(r["official_website"] or "").startswith(("http://", "https://")) else None
        aliases = "巴黎萨克雷大学" if r["university_id"] == "U001" else None
        insert(con, "universities", {
            "university_id": r["university_id"], "university_name_cn": r["university_name_cn"],
            "university_name_en": r["university_name_en"], "name_aliases": aliases,
            "country": r["country"], "region": r["region"], "university_type": r["university_type"],
            "ranking_info": r["ranking_info"], "official_website": website,
            "collection_year": r["collection_year"], "data_status": "extracted",
            "completeness": r["completeness"], "notes": "V1 原记录迁移；completeness 仅作历史备查。",
            "raw_text": raw_json(r), "review_status": "pending_review",
            "created_at": NOW, "updated_at": NOW,
        })
    old_uids = {r["university_id"] for r in old_rows["universities"]}
    for school in schools:
        uid = uid_by_school[school]
        if uid in old_uids:
            continue
        sample = next(r for r in raw_files if r["school"] == school)
        insert(con, "universities", {
            "university_id": uid, "university_name_cn": school, "university_name_en": None,
            "name_aliases": None, "country": sample["country"], "region": sample["region"],
            "university_type": None, "ranking_info": None, "official_website": None,
            "collection_year": None, "data_status": "not_started", "completeness": None,
            "notes": "仅依据原始附件登记高校身份，待逐校结构化；未推断官网、项目或师资信息。",
            "raw_text": json.dumps({"registration_origin": school_paths[school]}, ensure_ascii=False),
            "review_status": "pending_review", "created_at": NOW, "updated_at": NOW,
        })

    # 来源：原访问日期保留在 raw_text，V2 access_date 待真实核验。
    official_source_ids = set()
    for r in old_rows["sources"]:
        official = r["source_type"] == "官网资料"
        if official:
            official_source_ids.add(r["source_id"])
        note = r["note"]
        if r["access_date"]:
            note = (note or "") + " V1 access_date 已保留于 raw_text，其实际访问日期语义待核验。"
        insert(con, "sources", {
            "source_id": r["source_id"], "university_id": r["university_id"],
            "source_type": "official_web" if official else "compilation",
            "source_name": r["source_name"], "url": r["url"] or None,
            "publisher": None, "publication_date": None, "access_date": None, "language": None,
            "is_official": int(official), "verification_status": "needs_review", "note": note,
            "raw_text": raw_json(r), "review_status": "pending_review",
            "created_at": NOW, "updated_at": NOW,
        })

    for r in old_rows["organizations"]:
        insert(con, "organizations", {
            "organization_id": r["organization_id"], "university_id": r["university_id"],
            "parent_organization_id": None, "parent_org_text": r["parent_org"], "name": r["name"],
            "name_en": None, "org_type": r["org_type"], "research_directions": None,
            "ai_related": tag(r["ai_related"]), "language_related": tag(r["language_related"]),
            "interdisciplinary": tag(r["interdisciplinary"]), "description": r["description"],
            "raw_text": raw_json(r), "review_status": "pending_review",
            "created_at": NOW, "updated_at": NOW,
        })

    non_degree = {"P201", "P302", "P303"}
    specializations = {"P001", "P301"}
    for r in old_rows["programs"]:
        kind = ("research_training" if r["program_id"] in non_degree else
                "specialization" if r["program_id"] in specializations else "degree_program")
        formal = int(r["program_id"] not in non_degree)
        insert(con, "programs", {
            "program_id": r["program_id"], "university_id": r["university_id"],
            "parent_program_id": None, "host_organization_id": None, "program_kind": kind,
            "is_formal_degree": formal, "level": r["level"], "level_raw": r["level"],
            "program_name_cn": r["program_name_cn"], "program_name_en": r["program_name_en"],
            "degree": "不适用" if not formal else r["degree"], "host_unit_text": None,
            "duration": r["duration"], "language_of_instruction": r["language_of_instruction"],
            "entry_level": r["entry_level"], "admission_summary": r["admission_summary"],
            "positioning": r["positioning"], "program_size": r["program_size"], "sequence_no": None,
            "raw_text": raw_json(r), "review_status": "pending_review",
            "created_at": NOW, "updated_at": NOW,
        })

    program_uid = {r["program_id"]: r["university_id"] for r in old_rows["programs"]}
    for r in old_rows["objectives"]:
        insert(con, "objectives", {
            "objective_id": r["objective_id"], "university_id": program_uid[r["program_id"]],
            "program_id": r["program_id"], "scope_type": "program", "dimension": r["dimension"],
            "description": r["description"], "sequence_no": None, "raw_text": raw_json(r),
            "review_status": "pending_review", "created_at": NOW, "updated_at": NOW,
        })

    for r in old_rows["courses"]:
        insert(con, "courses", {
            "course_id": r["course_id"], "university_id": r["university_id"], "course_code": None,
            "course_name": r["course_name"], "course_name_raw": r["course_name"],
            "course_name_en": None, "course_name_zh": None, "language": None, "description": None,
            "ai_tag": tag(r["ai_tag"]), "language_tag": tag(r["language_tag"]),
            "practice_tag": tag(r["practice_tag"]), "raw_text": raw_json(r),
            "review_status": "pending_review", "created_at": NOW, "updated_at": NOW,
        })
        stage = r["semester"] if re.fullmatch(r"M[12]", str(r["semester"] or "")) else None
        insert(con, "program_course", {
            "program_course_id": "PC_" + r["course_id"], "program_id": r["program_id"],
            "course_id": r["course_id"], "module": r["module"], "stage": stage,
            "semester": r["semester"], "academic_year": None,
            "required_elective": r["module"] if r["module"] in ("必修", "选修", "限选", "任选") else None,
            "credits": r["ects"], "credit_system": "ECTS" if r["ects"] is not None else None,
            "lecture_hours": r["lecture_hours"], "directed_study_hours": r["directed_study_hours"],
            "practical_hours": r["practical_hours"], "relation_note": None, "raw_text": raw_json(r),
            "review_status": "pending_review", "created_at": NOW, "updated_at": NOW,
        })

    for r in old_rows["faculty"]:
        insert(con, "faculty", {
            "faculty_id": r["faculty_id"], "university_id": r["university_id"], "name": r["name"],
            "name_raw": r["name"], "primary_unit_text": r["organization"], "title": r["title"],
            "research_direction": r["research_direction"], "homepage_url": None, "orcid": None,
            "biography": None, "ai_tag": tag(r["ai_tag"]), "language_tag": tag(r["language_tag"]),
            "interdisciplinary_tag": tag(r["interdisciplinary_tag"]), "raw_text": raw_json(r),
            "review_status": "pending_review", "created_at": NOW, "updated_at": NOW,
        })

    for r in old_rows["practice"]:
        insert(con, "practice", {
            "practice_id": r["practice_id"], "university_id": r["university_id"],
            "program_id": r["program_id"], "scope_type": "program" if r["program_id"] else "university",
            "practice_type": r["practice_type"], "name": r["name"], "duration": r["duration"],
            "credits": r["credits"], "credit_system": None, "content": r["content"],
            "assessment": r["assessment"], "raw_text": raw_json(r), "review_status": "pending_review",
            "created_at": NOW, "updated_at": NOW,
        })

    for r in old_rows["evaluation"]:
        insert(con, "evaluation", {
            "evaluation_id": r["evaluation_id"], "university_id": r["university_id"],
            "program_id": r["program_id"], "scope_type": "program" if r["program_id"] else "university",
            "evaluation_type": r["evaluation_type"], "method": r["method"], "criteria": r["criteria"],
            "weight": r["weight"], "output": r["output"], "raw_text": raw_json(r),
            "review_status": "pending_review", "created_at": NOW, "updated_at": NOW,
        })

    # 每校附件登记批次。只登记，不把附件数量当作已结构化记录。
    by_school = defaultdict(list)
    for r in raw_files:
        by_school[r["school"]].append(r)
    special_xml = {"南京大学", "南洋理工大学", "昆士兰大学", "巴黎萨克雷大学"}
    for school in schools:
        uid = uid_by_school[school]
        files = sorted(by_school[school], key=lambda x: x["path"].as_posix())
        batch_id = f"BRAW_{uid}"
        manifest = []
        for i, r in enumerate(files, 1):
            manifest.append({
                "attachment_id": f"ATT_{uid}_{i:03d}", "source_id": f"SRC_{uid}_{i:03d}",
                "path": "raw_files/" + r["path"].as_posix(), "sha256": r["sha256"],
            })
        insert(con, "import_batches", {
            "batch_id": batch_id, "university_id": uid,
            "input_manifest_json": json.dumps(manifest, ensure_ascii=False), "file_count": len(files),
            "parser_version": "attachment-registrar-1.0.0", "status": "started", "started_at": NOW,
            "finished_at": None, "quality_report_path": None,
            "notes": "仅登记原始附件和文件指纹，尚未逐校解析原文片段。",
            "created_at": NOW, "updated_at": NOW,
        })
        for i, r in enumerate(files, 1):
            att_id = f"ATT_{uid}_{i:03d}"
            src_id = f"SRC_{uid}_{i:03d}"
            path_text = r["path"].as_posix()
            lower_name = r["path"].name.lower()
            is_docx = r["path"].suffix.lower() == ".docx"
            if is_docx:
                source_type, attachment_type = "compilation", "raw_docx"
            elif "handbook" in lower_name:
                source_type, attachment_type = "handbook", "handbook"
            elif any(x in lower_name for x in ("课程", "毕业计划")):
                source_type, attachment_type = "catalog", "curriculum"
            else:
                source_type, attachment_type = "other", "other"
            file_meta = {k: v for k, v in manifest[i-1].items()}
            insert(con, "sources", {
                "source_id": src_id, "university_id": uid, "source_type": source_type,
                "source_name": r["path"].stem, "url": None, "publisher": None,
                "publication_date": None, "access_date": None, "language": None,
                "is_official": 0, "verification_status": "unverified",
                "note": "原始资料包内附件；官方属性、原始链接和实际访问日期待逐校核验。",
                "raw_text": json.dumps(file_meta, ensure_ascii=False), "review_status": "pending_review",
                "created_at": NOW, "updated_at": NOW,
            })
            extraction = "registered_only"
            if is_docx and school in special_xml:
                extraction = "requires_xml_fallback"
            insert(con, "attachments", {
                "attachment_id": att_id, "batch_id": batch_id, "source_id": src_id,
                "university_id": uid, "attachment_type": attachment_type, "file_name": r["path"].name,
                "local_path": "raw_files/" + path_text, "official_url": None,
                "mime_type": mimetypes.guess_type(r["path"].name)[0], "file_hash": r["sha256"],
                "file_size_bytes": r["bytes"], "page_count": None if is_docx else pdf_pages(r["data"]),
                "language": None, "access_date": None, "storage_status": "local_copy_present",
                "download_permission": "unknown", "extraction_status": extraction,
                "note": "上传原始资料的只读副本；许可不明，不在网页提供本地下载。",
                "raw_text": json.dumps(file_meta, ensure_ascii=False), "review_status": "pending_review",
                "created_at": NOW, "updated_at": NOW,
            })
            insert(con, "source_links", {
                "link_id": f"SLRAW_{uid}_{i:03d}", "source_id": src_id, "attachment_id": att_id,
                "fragment_id": None, "entity_type": "universities", "entity_id": uid,
                "dimension": "university_overview", "relation_type": "compiled_origin",
                "locator": path_text, "evidence_quote": None, "is_primary": 0,
                "note": "原始附件与高校身份的登记关系，不表示内容已结构化。", "created_at": NOW,
            })

    # 四所旧高校的迁移批次，供质量报告和核验事项引用。
    for uid in sorted(old_uids):
        insert(con, "import_batches", {
            "batch_id": f"BMIG_{uid}", "university_id": uid,
            "input_manifest_json": json.dumps([{
                "path": "backups/v1_original/data/language_ai_cases.db", "sha256": sha256_file(V1_DB)
            }], ensure_ascii=False), "file_count": 1, "parser_version": PARSER_VERSION,
            "status": "started", "started_at": NOW, "finished_at": None,
            "quality_report_path": f"quality_reports/{uid}_迁移质量报告.md",
            "notes": "V1 到 V2 无损迁移；原文回查补录不在本批次自动推断。",
            "created_at": NOW, "updated_at": NOW,
        })

    # 旧 source_id 全部迁移为证据关系；课程实体与项目关系分别保留出处。
    link_no = 1
    def add_old_link(entity_type, entity_id, source_id, dimension):
        nonlocal link_no
        if not source_id:
            return
        insert(con, "source_links", {
            "link_id": f"SLM{link_no:06d}", "source_id": source_id, "attachment_id": None,
            "fragment_id": None, "entity_type": entity_type, "entity_id": entity_id,
            "dimension": dimension,
            "relation_type": "official_verification" if source_id in official_source_ids else "compiled_origin",
            "locator": None, "evidence_quote": None, "is_primary": 1,
            "note": "V1 source_id 迁移；是否已完成官方核验由 sources.verification_status 单独判断。",
            "created_at": NOW,
        })
        link_no += 1

    for table in OLD_TABLES:
        if table == "sources":
            continue
        for r in old_rows[table]:
            add_old_link(table, r[PK[table]], r["source_id"], DIMENSION[table])
            if table == "courses":
                add_old_link("program_course", "PC_" + r["course_id"], r["source_id"], "课程体系")

    issue_no = 1
    def add_issue(uid, entity_type, entity_id, field_name, issue_type, severity, description, action):
        nonlocal issue_no
        insert(con, "review_issues", {
            "issue_id": f"RI{issue_no:05d}", "batch_id": f"BMIG_{uid}", "university_id": uid,
            "entity_type": entity_type, "entity_id": entity_id, "fragment_id": None,
            "field_name": field_name, "issue_type": issue_type, "severity": severity,
            "description": description, "suggested_action": action, "status": "open",
            "resolution_note": None, "created_at": NOW, "resolved_at": None,
        })
        issue_no += 1

    for r in old_rows["sources"]:
        if r["access_date"]:
            add_issue(r["university_id"], "sources", r["source_id"], "access_date",
                      "access_date_unverified", "low",
                      f"V1 记录日期为 {r['access_date']}，无法确认是实际访问日还是统一入库日；原值保存在 raw_text，V2 access_date 置空。",
                      "回查采集记录或实际重新访问官方来源后再填写核验日期。")
    if any(r["university_id"] == "U001" and r["official_website"] == "未在案例文档中给出" for r in old_rows["universities"]):
        add_issue("U001", "universities", "U001", "official_website", "not_public", "low",
                  "V1 使用文字占位而非官方 URL；V2 已转为 NULL，原文仍保留。", "只依据原资料或真实官方页面补充，不按校名猜测。")
    for pid in ("P201", "P302", "P303"):
        r = next(x for x in old_rows["programs"] if x["program_id"] == pid)
        add_issue(r["university_id"], "programs", pid, "program_kind", "entity_type_review", "medium",
                  "V1 将学位项目与课程／研究训练混合存放；V2 暂标 research_training、is_formal_degree=0，原层次和学位文本保存在 raw_text。",
                  "回查原文后确认其具体路径类型及与正式学位项目的层级关系。")
    tokyo_courses = [r for r in old_rows["courses"] if r["university_id"] == "U003"]
    for r in tokyo_courses:
        add_issue("U003", "courses", r["course_id"], "course_name", "entity_type_review", "medium",
                  f"“{r['course_name']}” 在 V1 中作为课程／研究主题保存；迁移不删除，但不得直接视为正式课程。",
                  "回查东京大学原文，确认应保留为课程、研究项目主题或科研培养内容。")
    duplicate_groups = list(old.execute("""
        SELECT university_id, course_name, count(*) AS n, group_concat(course_id) AS ids
        FROM courses WHERE university_id='U001'
        GROUP BY university_id, course_name HAVING count(*)>1 ORDER BY course_name
    """))
    for g in duplicate_groups:
        ids = g["ids"].split(",")
        add_issue(g["university_id"], "courses", ids[0], "course_name", "duplicate_candidate", "medium",
                  f"同名课程 {g['course_name']} 对应 {g['n']} 个旧课程 ID：{g['ids']}。迁移未合并。",
                  "核对课程代码、M1／M2 关系和官方课程页；确认共享课程后再合并实体并保留多条项目关系。")
    if len(duplicate_groups) != 6:
        raise AssertionError(f"巴黎萨克雷同名课程组应为 6，实际 {len(duplicate_groups)}")
    datacamp = [r for r in old_rows["courses"] if r["course_name"] == "Data Camp - IPP"]
    if len({r["module"] for r in datacamp}) > 1:
        add_issue("U001", "courses", datacamp[0]["course_id"], "module", "conflict", "medium",
                  "Data Camp - IPP 在旧记录中的模块分别为“核心”和“软技能”，可能属于不同项目或存在冲突。",
                  "回查 M1／M2 课程表，不把模块差异静默覆盖。")
    for r in old_rows["courses"]:
        if (r["course_name"].startswith("TER -") or r["course_name"].startswith("Ecole thématique")) and r["practice_tag"] == "否":
            add_issue(r["university_id"], "courses", r["course_id"], "practice_tag", "pending_review", "low",
                      f"{r['course_name']} 名称包含研究训练或实习含义，但 V1 practice_tag=否。",
                      "依据课程原文复核实践标签，不仅凭名称自动改成“是”。")
    for r in old_rows["universities"]:
        if r["completeness"] == "高" and r["university_id"] in ("U001", "U002", "U004"):
            add_issue(r["university_id"], "universities", r["university_id"], "completeness", "pending_review", "low",
                      "V1 完整度“高”与原始资料缺口不完全匹配；旧值仅作历史备查，V2 使用可复核质量视图。",
                      "完成原文补录后按六维覆盖、证据链和待核验事项重新评估。")

    # 迁移自检：原行 JSON 完全一致，旧网页视图逐字段一致。
    raw_mismatches = []
    for table in OLD_TABLES:
        for r in old_rows[table]:
            stored = con.execute(f"SELECT raw_text FROM {table} WHERE {PK[table]}=?", (r[PK[table]],)).fetchone()[0]
            if json.loads(stored) != r:
                raw_mismatches.append({"table": table, "id": r[PK[table]]})
    if raw_mismatches:
        raise AssertionError(f"raw_text 原行不一致：{raw_mismatches[:5]}")

    legacy_differences = []
    for table in OLD_TABLES:
        v1 = sorted(old_rows[table], key=lambda r: r[PK[table]])
        v2 = [dict(r) for r in con.execute(f"SELECT * FROM v_legacy_{table}")]
        v2 = sorted(v2, key=lambda r: r[PK[table]])
        if v1 != v2:
            for a, b in zip(v1, v2):
                for key in a:
                    if a[key] != b.get(key):
                        legacy_differences.append({"table": table, "id": a[PK[table]], "field": key,
                                                   "v1": a[key], "v2": b.get(key)})
            if len(v1) != len(v2):
                legacy_differences.append({"table": table, "count_v1": len(v1), "count_v2": len(v2)})
    if legacy_differences:
        (ROOT / "quality_reports" / "legacy_differences.json").write_text(
            json.dumps(legacy_differences, ensure_ascii=False, indent=2), encoding="utf-8")
        raise AssertionError(f"旧网页兼容视图存在 {len(legacy_differences)} 处差异")

    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
    if integrity != "ok" or fk_errors:
        raise AssertionError(f"数据库完整性失败：{integrity}, {fk_errors[:5]}")
    expected_metrics = {"universities": 4, "programs": 10, "courses": 77, "faculty": 31, "organizations": 14}
    metrics = {t: con.execute(f"SELECT count(*) FROM v_legacy_{t}").fetchone()[0] for t in expected_metrics}
    if metrics != expected_metrics:
        raise AssertionError(f"旧网页指标变化：{metrics}")
    if con.execute("SELECT count(*) FROM program_course").fetchone()[0] != 77:
        raise AssertionError("项目—课程关系数不是 77")
    if con.execute("SELECT count(*) FROM attachments").fetchone()[0] != 72:
        raise AssertionError("附件登记数不是 72")
    if con.execute("SELECT count(*) FROM v_raw_fragment_disposition_issues").fetchone()[0] != 0:
        raise AssertionError("原文去向视图存在异常")

    for uid in sorted(old_uids):
        con.execute("""UPDATE import_batches SET status='validated', finished_at=?,
                       quality_report_path=?, updated_at=? WHERE batch_id=?""",
                    (NOW, f"quality_reports/{uid}_迁移质量报告.md", NOW, f"BMIG_{uid}"))
    con.commit()
    counts = {r[0]: r[1] for r in con.execute("SELECT table_name, record_count FROM v_export_counts")}
    quality = [dict(r) for r in con.execute("SELECT * FROM v_university_quality ORDER BY university_id")]
    con.close()
    old.close()

    if DEST.exists():
        previous = ROOT / "backups" / "previous_v2"
        previous.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(DEST, previous / f"language_ai_cases_{stamp}.db")
    tmp.replace(DEST)
    summary = {
        "migration_time": NOW, "v1_db_sha256": sha256_file(V1_DB), "v2_db_sha256": sha256_file(DEST),
        "schema_sha256": sha256_file(SCHEMA), "raw_zip_sha256": sha256_file(RAW_ZIP),
        "integrity_check": integrity, "foreign_key_errors": len(fk_errors),
        "raw_row_mismatches": len(raw_mismatches), "legacy_field_differences": len(legacy_differences),
        "legacy_metrics": metrics, "table_counts": counts, "registered_universities": len(schools),
        "not_started_universities": len(schools)-len(old_uids), "attachments": 72,
        "docx_attachments": 56, "pdf_attachments": 16,
        "review_issues": counts["review_issues"], "quality": quality,
    }
    (ROOT / "quality_reports" / "migration_self_check.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
