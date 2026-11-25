from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "language_ai_cases.db"
REPORTS = ROOT / "quality_reports"
SCHOOL_REPORTS = REPORTS / "schools"
USER_REVISED_STAGE = REPORTS / "阶段总体验收报告.md"
TABLES = [
    "universities", "programs", "objectives", "courses", "faculty", "practice",
    "evaluation", "organizations", "sources", "program_course", "faculty_organization",
    "research_projects", "research_project_links", "research_outputs", "research_output_links",
    "student_development", "attachments", "raw_fragments", "source_links", "review_issues", "import_batches",
]


def load(name):
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md(value) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def main() -> None:
    today = date.today()
    report_date = f"{today.year}年{today.month}月{today.day}日"
    legacy = load("final_legacy_comparison.json")
    excel = load("excel_sqlite_consistency.json")
    browser = load("browser_regression.json")
    constraints = load("constraint_tests.json")
    attachments = load("full_attachment_verification.json")
    acceptance = load("final_acceptance_checks.json")
    full_import = load("full_import_summary.json")
    bootstrap = load("database_bootstrap_test.json")
    deployment = load("deployment_database.json")
    assert acceptance["status"] == "pass"
    assert all(x["status"] == "pass" for x in [legacy, excel, browser, constraints, attachments])
    assert full_import["mode"] == "full" and full_import["promoted"] is True
    assert full_import["database_sha256"] == sha(DB)
    assert bootstrap["status"] == "pass" and bootstrap["app_sha256"] == sha(ROOT / "app.py")
    assert deployment["roundtrip_verified"] is True and deployment["content_reduced"] is False
    revised_hash = sha(USER_REVISED_STAGE) if USER_REVISED_STAGE.exists() else None

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    universities = [dict(r) for r in con.execute("SELECT * FROM universities ORDER BY university_id")]
    quality = {r["university_id"]: dict(r) for r in con.execute("SELECT * FROM v_university_quality")}
    dimensions = {r["university_id"]: dict(r) for r in con.execute("SELECT * FROM v_university_dimension_counts")}
    SCHOOL_REPORTS.mkdir(parents=True, exist_ok=True)

    for university in universities:
        uid = university["university_id"]
        name = university["university_name_cn"]
        q = quality[uid]
        d = dimensions[uid]
        dispositions = dict(con.execute(
            "SELECT disposition,count(*) FROM raw_fragments WHERE university_id=? GROUP BY disposition", (uid,)))
        source_status = dict(con.execute(
            "SELECT verification_status,count(*) FROM sources WHERE university_id=? GROUP BY verification_status", (uid,)))
        atts = [dict(r) for r in con.execute(
            """SELECT attachment_id,file_name,local_path,file_hash,file_size_bytes,page_count,
                      extraction_status,download_permission FROM attachments WHERE university_id=? ORDER BY attachment_id""", (uid,))]
        issues = [dict(r) for r in con.execute(
            """SELECT issue_id,entity_type,entity_id,field_name,issue_type,severity,description,suggested_action
               FROM review_issues WHERE university_id=? AND status IN ('open','in_review') ORDER BY issue_id""", (uid,))]
        batches = [dict(r) for r in con.execute(
            """SELECT batch_id,parser_version,status,file_count,notes FROM import_batches
               WHERE university_id=? AND batch_id IN (?,?) ORDER BY batch_id""", (uid, f"BRAW_{uid}", f"BFULL_{uid}"))]
        fragment_count = sum(dispositions.values())
        lines = [
            f"# {name}（{uid}）全量结构化质量报告", "",
            f"**报告日期：**{report_date}  ",
            "**报告范围：**主 DOCX、顶层 PDF、DOCX 嵌入 PDF、图片 OCR 检索候选、结构化业务记录、来源证据与附件许可。", "",
            "## 一、结论与口径", "",
            "- **技术处理：通过。**该校已完成统一解析，原文片段均有 `mapped／raw_only／issue_created` 去向，未处理原文为 0。",
            "- **内容状态：机器结构化初稿。**`draft` 不等于人工或官方已核验；数量只表示当前资料中识别出的记录，不用于评价办学质量。",
            f"- 六维记录覆盖 {q['dimension_coverage_count']}/6；业务记录证据关系覆盖 {q['evidence_records']}/{q['business_records']}（{q['evidence_coverage_percent']:.1f}%）。",
            f"- 已审核业务记录 {q['verified_records']} 条；官方已核验比例 {q['official_verified_percent']:.1f}%；开放核验事项 {q['open_issue_count']} 条。",
            "- 图片 OCR 仅用于检索与回查候选，不直接生成事实字段；无法可靠归属的内容保留学校层面或原文，不强行归入项目。", "",
            "## 二、处理批次", "", "| 批次 | 解析器 | 状态 | 文件数 | 说明 |", "|---|---|---|---:|---|",
        ]
        for batch in batches:
            lines.append(f"| `{batch['batch_id']}` | {md(batch['parser_version'])} | {batch['status']} | {batch['file_count']} | {md(batch['notes'])} |")
        lines += [
            "", "## 三、当前记录数量", "", "| 数据对象 | 记录数 | 数据对象 | 记录数 |", "|---|---:|---|---:|",
            f"| 培养项目／路径 | {d['program_count']} | 培养目标 | {d['objectives_count']} |",
            f"| 课程／研究主题 | {d['courses_count']} | 师资 | {d['faculty_count']} |",
            f"| 实践环节 | {d['practice_count']} | 评价机制 | {d['evaluation_count']} |",
            f"| 科研平台与相关机构 | {d['organizations_count']} | 科研项目 | {d['research_projects_count']} |",
            f"| 科研成果 | {d['research_outputs_count']} | 学生发展 | {d['student_development_count']} |",
            f"| 原文片段 | {fragment_count} | 附件 | {d['attachment_count']} |", "",
            "课程实体与项目课程关系分开统计；科研团队、科研课题和正式学位项目不作混同。", "",
            "## 四、原文去向与来源状态", "", "| 原文去向 | 片段数 |", "|---|---:|",
        ]
        for key in sorted(dispositions):
            lines.append(f"| `{key}` | {dispositions[key]} |")
        lines += ["", "| 来源核验状态 | 来源数 |", "|---|---:|"]
        for key in sorted(source_status):
            lines.append(f"| `{key}` | {source_status[key]} |")
        if uid in legacy.get("per_university", {}):
            old = legacy["per_university"][uid]
            lines += ["", f"该校 V1 共 {old['v1_rows']} 行；完整原行差异 {old['raw_row_mismatches']}，兼容字段差异 {old['legacy_field_differences']}。"]
        lines += [
            "", "## 五、附件", "",
            "全部附件已由用户明确授权公开下载；该授权不代表官方来源已核验。下表路径、大小、SHA-256 和 PDF 页数已逐文件复核。", "",
            "| 附件 | 文件 | 字节 | PDF页数 | 解析状态 | 下载许可 | SHA-256 |", "|---|---|---:|---:|---|---|---|",
        ]
        for a in atts:
            lines.append(f"| `{a['attachment_id']}` | {md(a['file_name'])} | {a['file_size_bytes']} | {a['page_count'] if a['page_count'] is not None else '—'} | {a['extraction_status']} | {a['download_permission']} | `{a['file_hash']}` |")
        lines += ["", "## 六、开放核验事项", "", "| 编号 | 严重程度 | 类型 | 对象 | 字段 | 问题 | 建议处理 |", "|---|---|---|---|---|---|---|"]
        if not issues:
            lines.append("| — | — | — | — | — | 当前没有开放核验事项；这不等于全部内容已人工核验。 | — |")
        for issue in issues:
            target = f"{issue['entity_type']}:{issue['entity_id']}" if issue["entity_type"] else "—"
            lines.append(f"| {issue['issue_id']} | {issue['severity']} | {issue['issue_type']} | `{md(target)}` | {md(issue['field_name'])} | {md(issue['description'])} | {md(issue['suggested_action'])} |")
        lines += ["", "## 七、使用边界", "",
                  "1. 网页和 Excel 均读取同一 SQLite 数据源；原文证据可在网页“来源与证据”页按业务记录回查。",
                  "2. 不得为减少问题数量而自动关闭事项，不得为字段完整而推断高校、教师、课程、项目或学生去向。",
                  "3. 后续人工修订前必须备份数据库，并重新执行 Excel 导出、真实重算、三方一致性和网页回归测试。", ""]
        (SCHOOL_REPORTS / f"{uid}_{name}_质量报告.md").write_text("\n".join(lines), encoding="utf-8")

    att_lines = [
        "# 80份附件完整性核验报告", "", f"**核验日期：**{report_date}  ", "",
        "## 一、核验结论", "",
        f"- 共 **{attachments['attachment_count']} 份**：{attachments['docx_count']} 份 DOCX、{attachments['pdf_count']} 份 PDF（16 份顶层 PDF＋8 份 DOCX 嵌入 PDF）。",
        f"- **{attachments['passed_files']}/{attachments['attachment_count']}** 份通过安全相对路径、文件存在、字节数、SHA-256、格式结构、解析状态和下载许可检查。",
        f"- 24 份 PDF 实际页数合计 **{attachments['pdf_pages']} 页**，与数据库登记一致。",
        "- 56 份 DOCX 均通过 ZIP CRC 和 `word/document.xml` 可读检查；未修改任何原始附件。",
        "- 全部附件为 `download_permission=allowed`、`extraction_status=parsed`。授权不等于官方来源已核验，也不等于可以推断实际访问日期。", "",
        "## 二、范围说明", "",
        "- 72 份顶层附件继续沿用上传 ZIP、SQLite 和本地目录的三方指纹核验结果。",
        "- 8 份嵌入附件从 DOCX 的 OLE `Ole10Native` 对象只读提取，使用规范中文文件名；同名不同内容不得覆盖。",
        "- 早期 OLE 工具产生的下划线／乱码重复文件属于中间产物，不属于数据库登记的 80 份附件，不纳入最终部署包。", "",
        "逐文件结果见 `quality_reports/full_attachment_verification.json`；56 校逐校清单见 `quality_reports/schools/`。", "",
    ]
    (REPORTS / "80份附件完整性核验报告.md").write_text("\n".join(att_lines), encoding="utf-8")

    table_counts = acceptance["table_counts"]
    constraint_categories = Counter(x["category"] for x in constraints["results"])
    stage = [
        "# 世界一流大学“语言＋人工智能”案例数据库 V2 全量结构化验收报告", "",
        f"**验收日期：**{report_date}  ",
        "**验收范围：**56 校统一解析、80 份附件、V2 数据库、21 表 Excel、正式 V2 网页和下载工作流。", "",
        "## 一、验收结论", "",
        "**本地技术验收通过。**56 校均已完成机器结构化初稿；80 份附件均允许下载并完成逐文件核验；数据库、Excel 与网页使用同一 V2 数据源。",
        "**内容不等于人工或官方已核验。**新结构化记录保留 `draft`、原文证据、来源状态和待核验事项；不将记录数量作为高校办学质量排名。", "",
        "## 二、全量导入与原文去向", "",
        f"- 解析器：`{full_import['parser_version']}`；56 个 `BFULL` 批次均为 `validated`，56 校均为 `extracted`。",
        f"- 原文片段 {table_counts['raw_fragments']} 条，`unprocessed=0`；证据关系 {table_counts['source_links']} 条。",
        f"- PDF 共 {attachments['pdf_pages']} 页；附件 {table_counts['attachments']} 份，全部 `allowed` 且 `parsed`。",
        f"- V1 共 {legacy['v1_total_rows']} 行原记录：完整原行差异 {legacy['raw_row_mismatches']}，兼容字段差异 {legacy['legacy_field_differences']}。", "",
        "## 三、数据库结构与记录数", "",
        f"- 实际对象：{acceptance['object_counts']['table']} 张表、{acceptance['object_counts']['view']} 个视图、{acceptance['object_counts']['trigger']} 个触发器、{acceptance['object_counts']['index']} 个显式索引；另有 {acceptance['object_counts']['sqlite_autoindex']} 个自动唯一索引。",
        "- 完整性、外键、证据目标、主键保护、多对多关系和原文去向均通过检查。", "",
        "| 表 | 记录数 | 表 | 记录数 |", "|---|---:|---|---:|",
    ]
    for i in range(0, len(TABLES), 2):
        left = TABLES[i]
        right = TABLES[i + 1] if i + 1 < len(TABLES) else None
        stage.append(f"| `{left}` | {table_counts[left]} | {f'`{right}`' if right else ''} | {table_counts[right] if right else ''} |")
    stage += [
        "", "## 四、Excel 与网页实测", "",
        f"- Excel 共 {excel['sheet_count']} 个工作表；21 张数据表和质量概览逐单元格核对 {excel['compared_cells']:,} 个，差异 {excel['difference_count']}。",
        f"- Excel 公式 {excel['formula_count']} 个，真实重算后缓存缺失 {excel['formula_cache_missing_count']}，公式错误 {excel['formula_error_count']}。",
        f"- 网页回归 {browser['check_count']} 项，通过 {browser['passed_count']}，失败 {browser['failed_count']}；覆盖首页、检索、详情、比较、科研、学生发展、来源证据和附件下载。",
        f"- 浏览器逐份下载 {browser['download_count']}/80 份附件并核对 SHA-256；移动端首页、详情和下载页均通过，控制台、HTTP 和服务日志无异常。",
        f"- 完整 SQLite 的 gzip 副本 {deployment['compressed_bytes']:,} 字节，往返解压哈希一致；已在只有压缩库的隔离副本中实测启动，未删减任何数据。",
        f"- 数据库约束测试 {constraints['test_count']} 项；类型分布：{dict(constraint_categories)}。", "",
        "## 五、交付与使用边界", "",
        "- `data/language_ai_cases.db`：正式 V2 SQLite；`data/language_ai_cases.xlsx`：同步工作簿。",
        "- `app.py`：直接读取 V2 主表和统计视图的 Streamlit 应用；`v_legacy_*` 仅用于无损核对。",
        "- `quality_reports/schools/`：56 校逐校报告；`quality_reports/full_import_summary.json`：全量导入机器可读摘要。",
        "- 原始 DOCX／PDF 不删除；早期中间重复文件和隔离临时库不进入最终部署包。",
        "- GitHub 推送与 Streamlit Cloud 在线状态以实际部署记录为准；本地验收通过不等于已经推送或上线。", "",
    ]
    (REPORTS / "全量结构化验收报告.md").write_text("\n".join(stage), encoding="utf-8")
    con.close()
    if revised_hash is not None:
        assert sha(USER_REVISED_STAGE) == revised_hash, "用户修订的阶段报告不得被覆盖"
    summary = {
        "status": "pass", "school_reports": len(universities), "attachment_report": "quality_reports/80份附件完整性核验报告.md",
        "full_acceptance_report": "quality_reports/全量结构化验收报告.md", "user_revised_stage_report_preserved": revised_hash is not None,
        "user_revised_stage_report_sha256": revised_hash, "database_sha256": sha(DB),
    }
    (REPORTS / "full_quality_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
