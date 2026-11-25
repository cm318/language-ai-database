from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "language_ai_cases.db"
PROPOSAL = ROOT / "schema" / "数据库V2结构方案.md"
DICT_MD = ROOT / "schema" / "数据字典.md"
XLSX = ROOT / "data" / "language_ai_cases.xlsx"
XLSX_BUILD = Path("/tmp/language_ai_cases.full.xlsx")
XLSX_STAGING = ROOT / "data" / "language_ai_cases.promoting.xlsx"
TABLES = [
    "universities", "programs", "objectives", "courses", "faculty", "practice",
    "evaluation", "organizations", "sources", "program_course", "faculty_organization",
    "research_projects", "research_project_links", "research_outputs", "research_output_links",
    "student_development", "attachments", "raw_fragments", "source_links", "review_issues", "import_batches",
]
PK = {
    "universities":"university_id", "programs":"program_id", "objectives":"objective_id",
    "courses":"course_id", "faculty":"faculty_id", "practice":"practice_id",
    "evaluation":"evaluation_id", "organizations":"organization_id", "sources":"source_id",
    "program_course":"program_course_id", "faculty_organization":"faculty_organization_id",
    "research_projects":"project_id", "research_project_links":"project_link_id",
    "research_outputs":"output_id", "research_output_links":"output_link_id",
    "student_development":"development_id", "attachments":"attachment_id",
    "raw_fragments":"fragment_id", "source_links":"link_id", "review_issues":"issue_id",
    "import_batches":"batch_id",
}
COMMON = {
    "raw_text": "原始记录或原文。V1 迁移行保存完整 JSON 原行；后续原文可保存文本，不得用摘要覆盖。",
    "review_status": "审核状态：draft 初稿、pending_review 待核验、verified 已核验、conflict 来源冲突。",
    "created_at": "数据库记录创建时间，ISO 8601；不是资料访问日期。",
    "updated_at": "数据库记录最后更新时间，ISO 8601；不是资料访问日期。",
}
VIEW_DOCS = {
    "v_university_dimension_counts": "每校六维、科研、成果、学生发展和附件数量。",
    "v_business_records": "正式统计所需的业务记录与其高校归属、审核状态。",
    "v_source_traceability": "业务记录的证据覆盖、汇编出处及官方已核验比例。",
    "v_university_quality": "透明的六维覆盖率、证据覆盖率和质量流程状态，不使用主观高中低评分。",
    "v_pending_review": "按高校、严重程度、问题类型和状态汇总待核验事项。",
    "v_duplicate_candidates": "课程、教师、平台等重复候选；仅供核验，不自动合并。",
    "v_raw_fragment_disposition_issues": "检查未处理原文、已映射但缺证据、待核验但缺事项三类异常。",
    "v_export_counts": "21 张表记录数，供 SQLite 与 Excel 核对。",
    "v_legacy_universities": "V1 高校字段兼容视图，仅包含非 not_started 高校。",
    "v_legacy_programs": "V1 项目字段兼容视图，原学位文本可从原行恢复。",
    "v_legacy_objectives": "V1 培养目标字段兼容视图。",
    "v_legacy_courses": "V1 课程字段兼容视图，合并项目关系并恢复旧标签文字。",
    "v_legacy_faculty": "V1 师资字段兼容视图。",
    "v_legacy_practice": "V1 实践环节字段兼容视图。",
    "v_legacy_evaluation": "V1 评价机制字段兼容视图。",
    "v_legacy_organizations": "V1 科研平台字段兼容视图。",
    "v_legacy_sources": "V1 五条来源字段兼容视图，不混入后续附件来源。",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def esc(value) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def proposal_metadata():
    text = PROPOSAL.read_text(encoding="utf-8")
    purposes = {}
    for line in text.splitlines():
        m = re.match(r"\| (?:原有业务表|新增关系表|新增内容表|新增证据表|新增治理表) \| `([^`]+)` \| [^|]+ \| ([^|]+) \|$", line)
        if m:
            purposes[m.group(1)] = m.group(2).strip()
    fields = {}
    for match in re.finditer(r"^### [34]\.\d+ `([^`]+)`[^\n]*\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S):
        table, block = match.group(1), match.group(2)
        fields[table] = {}
        for line in block.splitlines():
            m = re.match(r"\| `([^`]+)` \| ([^|]+) \| ([^|]+) \|$", line)
            if m:
                fields[table][m.group(1)] = m.group(3).strip()
    return purposes, fields


def db_metadata(con):
    info, foreign = {}, {}
    for table in TABLES:
        info[table] = [dict(r) for r in con.execute(f"PRAGMA table_info({table})")]
        foreign[table] = {r[3]: f"{r[2]}.{r[4]}" for r in con.execute(f"PRAGMA foreign_key_list({table})")}
    return info, foreign


def dictionary_rows(con):
    purposes, documented = proposal_metadata()
    info, foreign = db_metadata(con)
    missing = []
    rows = []
    for table in TABLES:
        for col in info[table]:
            name = col["name"]
            desc = documented.get(table, {}).get(name) or COMMON.get(name)
            if not desc:
                missing.append(f"{table}.{name}")
                desc = "实施字段，具体规则见建库 SQL。"
            required = "是" if col["notnull"] or col["pk"] else "否"
            rows.append({
                "表名": table, "字段": name, "类型": col["type"], "必填": required,
                "主键": "是" if col["pk"] else "否", "外键": foreign[table].get(name, ""),
                "默认值": col["dflt_value"] or "", "含义与值域": desc,
            })
    if missing:
        raise AssertionError("以下字段缺少数据字典说明：" + ", ".join(missing))
    return rows, purposes, info


def write_dictionary(con, rows, purposes):
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
    views = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")]
    lines = [
        "# 数据库 V2 数据字典", "", "**项目：**世界一流大学“语言+人工智能”复合型人才培养模式研究  ",
        "**版本：**V2 实施版  ", "**生成日期：**2026年11月24日  ",
        f"**SQLite SHA-256：**`{sha(DB)}`  ", f"**建库 SQL SHA-256：**`{sha(ROOT/'schema/schema_v2.sql')}`", "",
        "## 一、范围与使用口径", "",
        "本字典由实际 V2 SQLite 反向读取，并与已确认结构方案逐字段核对。数据库共 21 张表；56 校 DOCX、16 份顶层 PDF 和 8 份嵌入 PDF 已完成统一解析与机器结构化初稿。",
        "V1 每条业务记录的完整原行保存在 `raw_text`，全量导入前后逐行比较差异为 0。正式网页读取 V2 主表和统计视图；`v_legacy_*` 仅用于兼容核对。", "",
        "- `access_date` 只表示实际访问或下载日期；V1 统一日期的原值保留在原行，V2 中待核实前为空。",
        "- `yes` 表示原文或明确资料支持正向关联；旧课程“强关联／一般”规范为 `yes`，原强度文字仍保留。",
        "- `scope_type=program` 时项目外键必填；无法可靠归属时使用高校、跨项目或待核验范围，不猜测项目。",
        "- 附件的本地保存状态与公开下载许可分开；用户已于 2026-11-24 明确授权全部 80 份附件可公开下载，`allowed` 不代表官方来源已核验。",
        "- 新结构化记录默认 `draft`，均保留原文证据；图片 OCR 仅作检索和回查候选，不直接生成事实字段。空表不添加虚假占位记录。", "",
        "## 二、表清单", "", "| 表名 | 用途 | 当前记录数 | 主键 |", "|---|---|---:|---|",
    ]
    for table in TABLES:
        lines.append(f"| `{table}` | {esc(purposes.get(table,''))} | {counts[table]} | `{PK[table]}` |")
    lines += ["", "## 三、字段字典", ""]
    for table in TABLES:
        lines += [f"### `{table}`", "", purposes.get(table, ""), "",
                  "| 字段 | 类型 | 必填 | 主键 | 外键 | 默认值 | 含义与值域 |",
                  "|---|---|---|---|---|---|---|"]
        for r in [x for x in rows if x["表名"] == table]:
            lines.append(f"| `{r['字段']}` | {r['类型']} | {r['必填']} | {r['主键']} | {esc(r['外键'])} | {esc(r['默认值'])} | {esc(r['含义与值域'])} |")
        lines.append("")
    lines += ["## 四、统计与兼容视图", "", "| 视图 | 用途 |", "|---|---|"]
    for view in views:
        lines.append(f"| `{view}` | {esc(VIEW_DOCS.get(view,'数据库统计或质量检查视图。'))} |")
    lines += ["", "## 五、证据与质量治理规则", "",
              "1. `source_links` 至少关联来源、附件、原文片段之一；通用业务目标由 44 个触发器中的目标校验逻辑保护。",
              "2. 科研关联表每行至多关联教师、平台、培养项目之一；尚未匹配时保留原名并生成待核验事项。",
              "3. `raw_fragments.disposition` 最终只能为 `mapped`、`raw_only` 或 `issue_created`；`unprocessed` 必须清零。",
              "4. 删除或修改已被证据／核验事项引用的业务主键会被触发器阻止，避免产生孤证据。",
              "5. `v_university_quality` 分开报告六维覆盖、证据覆盖和审核流程状态，不把记录数量等同于办学质量。", ""]
    DICT_MD.write_text("\n".join(lines), encoding="utf-8")
    return counts, views


HEADER_FILL = PatternFill("solid", fgColor="173B5E")
HEADER_FONT = Font(color="FFFFFF", bold=True, name="微软雅黑")
BODY_FONT = Font(name="微软雅黑", size=10)
LONG_TEXT = {
    "raw_text", "description", "content", "note", "notes", "input_manifest_json",
    "resolution_note", "suggested_action", "含义与值域", "research_direction",
    "research_directions", "destination_text", "evidence_quote", "biography",
    "admission_summary", "positioning", "content_text", "disposition_note",
}


def column_width(header):
    if header in LONG_TEXT:
        return 45
    if header in ("url", "official_url", "homepage_url", "local_path", "file_hash"):
        return 42
    if header == "表名" or str(header).endswith("_id") or header == "主键":
        return 28
    return min(28, max(12, len(str(header)) * 1.3 + 2))


def append_row(ws, values, widths, header=False, literal_equals=True):
    cells = []
    for index, value in enumerate(values):
        cell = WriteOnlyCell(ws, value=value)
        if literal_equals and isinstance(value, str) and value.startswith("="):
            cell.data_type = "s"
        if header:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        else:
            cell.font = BODY_FONT
            cell.alignment = Alignment(vertical="top", wrap_text=(widths[index] >= 40))
        cells.append(cell)
    ws.append(cells)


def sheet_from_rows(wb, name, headers, rows):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    widths = [column_width(h) for h in headers]
    append_row(ws, headers, widths, header=True)
    row_count = 0
    for row in rows:
        values = [row.get(h) if isinstance(row, dict) else row[i] for i, h in enumerate(headers)]
        append_row(ws, values, widths)
        row_count += 1
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    if headers:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{row_count + 1}"
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    return ws, row_count


def export_excel(con, rows, purposes):
    for path in (XLSX_BUILD, XLSX_STAGING):
        if path.exists():
            path.unlink()
    wb = Workbook(write_only=True)
    wb.calculation = CalcProperties(calcMode="auto", fullCalcOnLoad=True, forceFullCalc=True)
    intro = wb.create_sheet("说明")
    intro.sheet_view.showGridLines = False
    list_widths = [28, 48, 14, 28, 32]
    list_ws, _ = sheet_from_rows(wb, "表清单", ["表名", "用途", "当前记录数", "主键", "说明"], [])
    table_headers = {}
    for table in TABLES:
        headers = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        table_headers[table] = headers
        cursor = con.execute(f"SELECT * FROM {table} ORDER BY {PK[table]}")
        sheet_from_rows(wb, table, headers, cursor)
    quality = [dict(r) for r in con.execute("SELECT * FROM v_university_quality ORDER BY university_id")]
    quality_headers = list(quality[0]) if quality else ["university_id"]
    qws, quality_count = sheet_from_rows(wb, "质量概览", quality_headers, quality)
    for field in ("dimension_coverage_percent", "evidence_coverage_percent", "official_verified_percent"):
        idx = quality_headers.index(field) + 1
        letter = get_column_letter(idx)
        qws.conditional_formatting.add(f"{letter}2:{letter}{quality_count + 1}",
            ColorScaleRule(start_type="num", start_value=0, start_color="FEE2E2",
                           mid_type="num", mid_value=50, mid_color="FEF3C7",
                           end_type="num", end_value=100, end_color="D1FAE5"))
    dict_headers = ["表名", "字段", "类型", "必填", "主键", "外键", "默认值", "含义与值域"]
    sheet_from_rows(wb, "数据字典", dict_headers, rows)

    for table in TABLES:
        values = [table, purposes.get(table, ""), f"=MAX(0,COUNTA('{table}'!A:A)-1)", PK[table],
                  "原始附件登记表" if table == "attachments" else "V2 实际数据表"]
        append_row(list_ws, values, list_widths, literal_equals=False)
    list_ws.auto_filter.ref = f"A1:E{len(TABLES) + 1}"
    for index, width in enumerate(list_widths, 1):
        list_ws.column_dimensions[get_column_letter(index)].width = width

    intro_widths = [26, 72, 48, 36]
    append_row(intro, ["世界一流大学“语言+人工智能”案例数据库 V2", "", "", ""], intro_widths, header=True)
    intro.row_dimensions[1].height = 42
    append_row(intro, ["", "", "", ""], intro_widths)
    append_row(intro, ["指标", "数值", "统计口径", "备注"], intro_widths, header=True)
    metrics = [
        ("已登记高校", "=MAX(0,COUNTA('universities'!A:A)-1)", "56 所目标高校", "数据库、Excel、网页使用同一口径"),
        ("已结构化高校", None, "universities.data_status 非 not_started", "机器结构化初稿，不等于人工 verified"),
        ("培养项目／路径", "=MAX(0,COUNTA('programs'!A:A)-1)", "含学位、方向和科研培养路径", "科研路径不是正式学位"),
        ("课程／研究主题", "=MAX(0,COUNTA('courses'!A:A)-1)", "按明确课程表和原资料入库", "不自动删除或合并同名课程"),
        ("项目—课程关系", "=MAX(0,COUNTA('program_course'!A:A)-1)", "课程实体与项目内属性分离", "支持多对多"),
        ("科研项目", "=MAX(0,COUNTA('research_projects'!A:A)-1)", "明确项目记录", "说明性文字不逐段生成项目"),
        ("科研成果", "=MAX(0,COUNTA('research_outputs'!A:A)-1)", "论文、专利、软件、模型等", "重复 DOI 复用并追加证据"),
        ("学生发展", "=MAX(0,COUNTA('student_development'!A:A)-1)", "公开学生科研、升学就业与校友资料", "不补充私人联系方式"),
        ("原始附件", "=MAX(0,COUNTA('attachments'!A:A)-1)", "56 份 DOCX＋16 份顶层 PDF＋8 份嵌入 PDF", "全部 allowed；授权不等于官方核验"),
        ("原文片段", "=MAX(0,COUNTA('raw_fragments'!A:A)-1)", "标题、段落、表格行、PDF 文本与 OCR 候选", "unprocessed 必须为零"),
        ("证据关系", "=MAX(0,COUNTA('source_links'!A:A)-1)", "业务记录与来源、附件、原文的证据连接", "外部 URL 候选不等于已访问"),
        ("待核验事项", None, "open＋in_review", "不隐藏未关闭问题"),
        ("V1 原行差异", 0, "旧表逐行 raw_text 比较", "全量导入门禁结果"),
        ("V1 兼容字段差异", 0, "9 个旧网页视图逐字段比较", "兼容核对结果"),
    ]
    status_col = get_column_letter(table_headers["universities"].index("data_status")+1)
    issue_col = get_column_letter(table_headers["review_issues"].index("status")+1)
    for label, formula, basis, note in metrics:
        if label == "已结构化高校":
            formula = f'=COUNTIFS(universities!{status_col}:{status_col},"<>not_started",universities!{status_col}:{status_col},"<>")-1'
        if label == "待核验事项":
            formula = f'=COUNTIF(review_issues!{issue_col}:{issue_col},"open")+COUNTIF(review_issues!{issue_col}:{issue_col},"in_review")'
        append_row(intro, [label, formula, basis, note], intro_widths, literal_equals=False)
    append_row(intro, ["", "", "", ""], intro_widths)
    provenance = [
        ("数据库文件", "data/language_ai_cases.db", "SQLite V2", ""),
        ("SQLite SHA-256", sha(DB), "实际全量数据库；公开仓库使用同字节压缩副本", ""),
        ("建库 SQL", "schema/schema_v2.sql", "21 表、44 触发器、17 视图", ""),
        ("V1 备份", "backups/v1_original/", "6 个原始文件及哈希清单", "未修改上传文件"),
        ("原始资料目录", "raw_files/ 与 derived/embedded/", "72 份顶层附件＋8 份嵌入附件", "未把附件数当作业务记录数"),
        ("数据说明", "空表仅保留字段标题，不添加虚假占位记录。", "新结构化记录为机器初稿并保留原文证据", "正式网页读取 V2 主表；授权下载不等于官方来源已核验"),
    ]
    for row in provenance:
        append_row(intro, list(row), intro_widths)
    for index, width in enumerate(intro_widths, 1):
        intro.column_dimensions[get_column_letter(index)].width = width
    intro.freeze_panes = "A4"
    wb.save(XLSX_BUILD)

    check = load_workbook(XLSX_BUILD, data_only=False, read_only=True)
    expected = ["说明", "表清单"] + TABLES + ["质量概览", "数据字典"]
    if check.sheetnames != expected:
        raise AssertionError(f"Excel 工作表不符：{check.sheetnames}")
    for table in TABLES:
        got = [c.value for c in next(check[table].iter_rows(min_row=1, max_row=1))]
        if got != table_headers[table]:
            raise AssertionError(f"Excel 字段标题不符：{table}")
    check.close()
    shutil.copy2(XLSX_BUILD, XLSX_STAGING)
    if sha(XLSX_STAGING) != sha(XLSX_BUILD):
        raise AssertionError("Excel 写回项目目录后哈希不一致")
    os.replace(XLSX_STAGING, XLSX)


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows, purposes, _ = dictionary_rows(con)
    counts, views = write_dictionary(con, rows, purposes)
    export_excel(con, rows, purposes)
    con.close()
    result = {
        "tables": len(TABLES), "dictionary_fields": len(rows), "views": len(views),
        "table_counts": counts, "xlsx_bytes": XLSX.stat().st_size,
        "dictionary_bytes": DICT_MD.stat().st_size,
    }
    (ROOT / "quality_reports" / "export_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
