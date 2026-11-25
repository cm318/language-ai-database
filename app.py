from __future__ import annotations

import gzip
import hashlib
import html
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent
LOCAL_DB = BASE / "data" / "language_ai_cases.db"
DB_ARCHIVE = BASE / "data" / "language_ai_cases.db.gz"
DB_MANIFEST = BASE / "data" / "database_manifest.json"
XLSX = BASE / "data" / "language_ai_cases.xlsx"
PAGES = ["数据库首页", "高校详情"]
DIMENSIONS = [
    ("01", "培养目标", "人才定位、知识—能力—素养"),
    ("02", "课程体系", "语言、人工智能与交叉课程组织"),
    ("03", "师资配置", "跨院系、跨学科师资结构"),
    ("04", "实践环节", "科研、项目、实习与产学合作"),
    ("05", "评价机制", "课程、项目、论文与成果评价"),
    ("06", "科研平台与相关机构", "研究中心、实验室与协同平台"),
]
ENTITY_TYPES = {
    "培养项目／路径": ("programs", "program_id", "program_name_cn"),
    "培养目标": ("objectives", "objective_id", "description"),
    "课程": ("courses", "course_id", "course_name"),
    "师资": ("faculty", "faculty_id", "name"),
    "实践环节": ("practice", "practice_id", "name"),
    "评价机制": ("evaluation", "evaluation_id", "evaluation_type"),
    "科研平台与相关机构": ("organizations", "organization_id", "name"),
    "科研项目": ("research_projects", "project_id", "project_name"),
    "科研成果": ("research_outputs", "output_id", "title"),
    "学生发展": ("student_development", "development_id", "content"),
}
DETAIL_TABLES = {
    "programs": ("program_id", "sequence_no,program_id"),
    "objectives": ("objective_id", "sequence_no,objective_id"),
    "faculty": ("faculty_id", "name,faculty_id"),
    "practice": ("practice_id", "practice_id"),
    "evaluation": ("evaluation_id", "evaluation_id"),
    "organizations": ("organization_id", "name,organization_id"),
    "research_projects": ("project_id", "project_id"),
    "research_outputs": ("output_id", "publication_year,output_id"),
    "student_development": ("development_id", "event_year,development_id"),
    "sources": ("source_id", "source_id"),
    "review_issues": ("issue_id", "issue_id"),
}
LABELS = {
    "university_name_cn": "高校", "university_name_en": "英文校名", "country": "国家／地区", "region": "区域",
    "program_count": "项目／路径数", "courses_count": "课程数", "research_projects_count": "科研项目数",
    "research_outputs_count": "科研成果数", "dimension_coverage_count": "六维覆盖",
    "evidence_coverage_percent": "证据覆盖率（%）", "official_verified_percent": "官方已核验（%）",
    "open_issue_count": "开放问题", "unprocessed_fragment_count": "未处理原文", "quality_status": "质量流程状态",
    "content_type": "内容类型", "content_text": "原文内容", "locator": "定位", "disposition": "原文去向",
    "disposition_note": "去向说明", "n": "数量",
    "program_name_cn": "项目／路径名称", "program_kind": "记录类型", "is_formal_degree": "正式学位标记",
    "level": "培养层次", "level_raw": "原培养层次", "degree": "学位", "host_unit_text": "培养单位原文",
    "duration": "学制", "language_of_instruction": "授课语言", "admission_summary": "招生／基础要求",
    "positioning": "定位", "dimension": "维度", "description": "说明", "scope_type": "归属范围",
    "course_code": "课程号", "course_name": "课程／研究主题", "course_name_en": "英文名",
    "course_name_zh": "中文名", "language": "语言", "ai_tag": "人工智能标签", "language_tag": "语言标签",
    "practice_tag": "实践标签", "module": "模块", "stage": "阶段", "semester": "学期",
    "academic_year": "学年", "required_elective": "课程属性", "credits": "学分", "credit_system": "学分制",
    "lecture_hours": "讲授学时", "directed_study_hours": "指导学习学时", "practical_hours": "实践学时",
    "name": "名称", "title": "标题／职称", "primary_unit_text": "主要单位原文", "research_direction": "研究方向",
    "research_directions": "研究方向", "homepage_url": "个人主页", "biography": "简介", "practice_type": "实践类型",
    "content": "内容", "assessment": "评价方式", "evaluation_type": "评价类型", "method": "方法",
    "criteria": "标准", "weight": "权重", "output": "成果要求", "org_type": "机构类型",
    "project_name": "项目名称", "project_type": "项目类型", "funder": "资助方", "grant_number": "项目编号",
    "start_date": "开始日期", "end_date": "结束日期", "status": "状态", "output_type": "成果类型",
    "authors_text": "作者原文", "publication_year": "发表年份", "publication_date": "发表日期", "venue": "刊物／发布平台",
    "doi": "DOI", "url": "链接", "record_type": "记录类型", "subject_type": "对象类型",
    "person_name_public": "公开姓名", "student_status": "学生状态", "degree_level": "学位层次",
    "study_period": "就读时期", "achievement": "成果", "destination_type": "去向类型",
    "destination_text": "去向原文", "destination_organization": "去向机构", "destination_role": "去向角色",
    "event_year": "年份", "source_type": "来源类型", "source_name": "来源名称", "publisher": "发布者",
    "access_date": "实际访问日期", "is_official": "官方标记", "verification_status": "核验状态", "note": "备注",
    "file_name": "文件名", "attachment_type": "附件类型", "file_size_bytes": "字节数", "page_count": "页数",
    "download_permission": "下载许可", "extraction_status": "解析状态", "local_path": "本地路径", "file_hash": "SHA-256",
    "issue_type": "问题类型", "severity": "严重程度", "suggested_action": "建议处理", "resolution_note": "处理说明",
}

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@st.cache_resource(show_spinner="正在准备并校验案例数据库……")
def resolve_database() -> Path:
    """优先使用本地完整库；公开仓库只有压缩副本时解压并逐字节校验。"""
    if not DB_MANIFEST.is_file():
        if LOCAL_DB.is_file():
            return LOCAL_DB
        raise FileNotFoundError("未找到数据库或 database_manifest.json。")

    manifest = json.loads(DB_MANIFEST.read_text(encoding="utf-8"))
    expected_hash = str(manifest["sha256"])
    expected_bytes = int(manifest["bytes"])
    if len(expected_hash) != 64 or expected_bytes <= 0:
        raise ValueError("数据库清单的大小或 SHA-256 无效。")
    bytes.fromhex(expected_hash)

    if LOCAL_DB.is_file():
        if LOCAL_DB.stat().st_size != expected_bytes or file_sha256(LOCAL_DB) != expected_hash:
            raise RuntimeError("本地 SQLite 与部署清单不一致，已停止启动。")
        return LOCAL_DB

    if not DB_ARCHIVE.is_file():
        raise FileNotFoundError("未找到本地 SQLite 或其完整压缩副本。")
    if file_sha256(DB_ARCHIVE) != manifest["compressed_sha256"]:
        raise RuntimeError("压缩数据库 SHA-256 与部署清单不一致，已停止启动。")

    cache_dir = Path(tempfile.gettempdir()) / "language_ai_database_runtime"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"language_ai_cases_{expected_hash[:16]}.db"
    if target.is_file() and target.stat().st_size == expected_bytes and file_sha256(target) == expected_hash:
        return target

    temporary = cache_dir / f".extract_{os.getpid()}_{DB_ARCHIVE.stat().st_mtime_ns}.tmp"
    digest = hashlib.sha256()
    written = 0
    try:
        with gzip.open(DB_ARCHIVE, "rb") as source, temporary.open("wb") as output:
            for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                output.write(chunk)
                digest.update(chunk)
                written += len(chunk)
        if written != expected_bytes or digest.hexdigest() != expected_hash:
            raise RuntimeError("解压后的数据库大小或 SHA-256 与清单不一致。")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    if target.stat().st_size != expected_bytes or file_sha256(target) != expected_hash:
        raise RuntimeError("本机运行数据库复核失败，已停止启动。")
    return target


st.set_page_config(
    page_title="世界一流大学“语言＋人工智能”案例数据库",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
:root{
  color-scheme:dark;
  --navy-900:#00205b;--navy-900:oklch(0.2672 0.1125 260.562);
  --navy-800:#102244;--navy-800:oklch(0.2577 0.0683 261.809);
  --navy-950:#071a3d;--navy-950:oklch(0.2263 0.0719 261.116);
  --blue-700:#173765;--blue-700:oklch(0.3395 0.0893 257.817);
  --blue-300:#8cb4e7;--blue-300:oklch(0.7598 0.0856 254.781);
  --blue-100:#c9d9f2;--blue-100:oklch(0.8811 0.0387 259.287);
  --ice-50:#f4f8ff;--ice-50:oklch(0.9781 0.0103 261.789);
  --page:var(--navy-900);--surface:var(--navy-800);--surface-deep:var(--navy-950);
  --text:var(--ice-50);--text-secondary:var(--blue-100);--accent:var(--blue-300);
  --line:rgba(140,180,231,.28);--line-strong:rgba(140,180,231,.52);
  --surface-glass:rgba(16,34,68,.82);--accent-soft:rgba(140,180,231,.12);
  --shadow:0 22px 60px rgba(0,10,35,.26);--radius-lg:22px;--radius-md:14px;
}
.stApp{
  background:
    radial-gradient(circle at 88% 2%,rgba(140,180,231,.14),transparent 31rem),
    linear-gradient(180deg,rgba(0,32,91,.98),rgba(0,32,91,1) 38rem);
  color:var(--text);
}
[data-testid="stHeader"]{background:rgba(0,32,91,.82);backdrop-filter:blur(14px)}
.block-container{max-width:1480px;padding:4rem 2.4rem 4rem}
html,body,[class*="css"],.stApp{
  font-family:"DM Sans",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
  font-size:16px;line-height:1.65;
}
h1,h2,h3,h4,.serif{font-family:inherit;color:var(--text);font-style:normal;letter-spacing:-.025em}
h1{font-size:2.7rem;font-weight:700;line-height:1.18}h2{font-size:1.85rem;font-weight:680;margin-top:2.2rem;padding-bottom:.65rem;border-bottom:1px solid var(--line)}h3{font-size:1.25rem;font-weight:650;line-height:1.4}
p,li{color:var(--text)}a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:4px;transition:color .18s ease,text-underline-offset .18s ease}a:hover{color:var(--text);text-underline-offset:6px}
.hero{
  display:grid;grid-template-columns:minmax(0,2.5fr) minmax(250px,.9fr);
  margin:1.2rem 0 2.2rem;border:1px solid var(--line);border-radius:var(--radius-lg);
  overflow:hidden;background:linear-gradient(135deg,rgba(16,34,68,.98),rgba(23,55,101,.72));box-shadow:var(--shadow)
}
.hero-copy{padding:3.2rem 3.4rem;align-self:center}.hero h1{font-size:clamp(2.35rem,4.2vw,4.5rem);line-height:1.09;letter-spacing:-.045em;margin:.9rem 0 1.5rem;max-width:1000px}
.hero p{font-size:1.03rem;line-height:1.85;max-width:850px;margin:0;color:var(--text-secondary)}
.hero-number{background:var(--accent);color:var(--navy-950);padding:2.2rem;display:flex;flex-direction:column;justify-content:flex-end;clip-path:polygon(12% 0,100% 0,100% 100%,0 100%)}
.hero-number strong{font-family:inherit;font-size:clamp(5rem,8vw,8.4rem);font-weight:700;line-height:.88;letter-spacing:-.075em;color:var(--navy-950)}
.hero-number span{font-size:1.03rem;font-weight:600;line-height:1.75;margin-top:1.25rem;color:var(--navy-950)}
.kicker{font-size:.76rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}.rule{height:1px;background:var(--line);margin:1.6rem 0}
.school-head{border:1px solid var(--line);border-radius:var(--radius-lg);padding:2rem 2.2rem;margin:1.2rem 0;background:linear-gradient(120deg,var(--surface-glass),rgba(23,55,101,.55));box-shadow:var(--shadow)}
.school-head h1{margin:.45rem 0;font-size:clamp(2.1rem,4vw,3.7rem)}.school-head p{color:var(--text-secondary);margin:0;font-size:1.02rem}
.flat{border-top:1px solid var(--line-strong);padding:1.15rem .2rem 1.25rem;height:100%;transition:background .18s ease,padding .18s ease}.flat:hover{background:var(--accent-soft);padding-left:.8rem;padding-right:.8rem}.flat .no{font-size:.74rem;font-weight:700;letter-spacing:.12em;color:var(--accent)}.flat h3{margin:.55rem 0}.flat p{color:var(--text-secondary);line-height:1.7;margin:0;font-size:.94rem}
.notice{border:1px solid var(--line);border-radius:var(--radius-md);padding:1rem 1.15rem;background:var(--accent-soft);line-height:1.75;color:var(--text-secondary);margin:.8rem 0 1.2rem}.notice strong{color:var(--text)}.yellow{background:var(--accent);color:var(--navy-950);padding:0 .18em}
.compare{width:100%;border-collapse:separate;border-spacing:0;margin:.8rem 0 1.2rem;background:var(--surface-glass);border:1px solid var(--line);border-radius:var(--radius-md);overflow:hidden}
.compare th,.compare td{border-bottom:1px solid var(--line);padding:.85rem .9rem;text-align:left;vertical-align:top;color:var(--text)}.compare th{background:rgba(140,180,231,.15);color:var(--text);font-weight:650}.compare th:first-child{width:20%}.compare td:first-child{font-weight:650;color:var(--text-secondary)}.compare tr:last-child td{border-bottom:0}
.small{font-size:.86rem;color:var(--text-secondary);line-height:1.75}
div[data-testid="stMetric"]{border:1px solid var(--line);border-radius:var(--radius-md);padding:1.05rem 1.1rem;background:var(--surface-glass);box-shadow:0 10px 28px rgba(0,10,35,.14);transition:border-color .18s ease,transform .18s ease}
div[data-testid="stMetric"]:hover{border-color:var(--line-strong);transform:translateY(-2px)}div[data-testid="stMetricLabel"]{color:var(--text-secondary)}div[data-testid="stMetricLabel"] p{color:var(--text-secondary);font-size:.88rem}div[data-testid="stMetricValue"]{color:var(--text);font-weight:700}
div[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:var(--radius-md);background:var(--surface);box-shadow:0 12px 34px rgba(0,10,35,.16);max-width:100%}
div[data-testid="stDataFrameResizable"]{border-radius:calc(var(--radius-md) - 1px);overflow:hidden}div[data-testid="stDataFrame"] .stElementToolbar{z-index:5}
div[data-testid="stExpander"]{border:1px solid var(--line);border-radius:var(--radius-md);background:rgba(16,34,68,.62);overflow:hidden}div[data-testid="stExpander"] summary{color:var(--text)}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{border:1px solid var(--line-strong);border-radius:999px;background:var(--surface);color:var(--text);font-weight:650;min-height:2.85rem;padding:.55rem 1.3rem;box-shadow:0 8px 22px rgba(0,10,35,.16);transition:background .18s ease,color .18s ease,border-color .18s ease,transform .18s ease}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover{background:var(--accent);color:var(--navy-950);border-color:var(--accent);transform:translateY(-1px)}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:var(--accent);color:var(--navy-950);border-color:var(--accent)}
.stButton>button:focus-visible,.stDownloadButton>button:focus-visible,.stFormSubmitButton>button:focus-visible,a:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
div[data-baseweb="input"],div[data-baseweb="select"]>div,div[data-baseweb="base-input"],div[data-baseweb="textarea"]{border-radius:12px;background-color:var(--surface);border-color:var(--line-strong);color:var(--text)}
input,textarea{color:var(--text)!important;-webkit-text-fill-color:var(--text)!important}input::placeholder,textarea::placeholder{color:var(--text-secondary)!important;opacity:.82;-webkit-text-fill-color:var(--text-secondary)!important}
div[data-testid="stTextInput"] label p,div[data-testid="stSelectbox"] label p,div[data-testid="stMultiSelect"] label p{color:var(--text-secondary);font-weight:600}
div[data-testid="stRadio"] div[role="radiogroup"]{gap:.35rem;width:fit-content;padding:.35rem;background:rgba(16,34,68,.72);border:1px solid var(--line);border-radius:999px}
div[data-testid="stRadio"] div[role="radiogroup"] label{min-height:44px;padding:.48rem 1.15rem;border-radius:999px;transition:background .18s ease,color .18s ease}
div[data-testid="stRadio"] div[role="radiogroup"] label:hover{background:var(--accent-soft)}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){background:var(--accent)}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p{color:var(--navy-950);font-weight:700}
.stTabs [data-baseweb="tab-list"]{gap:.35rem;border-bottom:1px solid var(--line);overflow-x:auto;scrollbar-width:thin}.stTabs [data-baseweb="tab"]{font-weight:600;padding:.7rem 1rem;border-radius:999px!important;color:var(--text-secondary);white-space:nowrap;transition:background .18s ease,color .18s ease}
.stTabs [data-baseweb="tab"]:hover{background:var(--accent-soft);color:var(--text)}.stTabs [aria-selected="true"]{background:var(--accent)!important;color:var(--navy-950)!important}.stTabs [data-baseweb="tab-highlight"]{display:none}
[data-testid="stCaptionContainer"],.stCaption{color:var(--text-secondary)!important}
#MainMenu{visibility:hidden}footer{visibility:hidden}
@media(max-width:760px){
  .block-container{padding:4rem 1rem 3rem}.hero{grid-template-columns:1fr;border-radius:18px}.hero-copy{padding:1.7rem}.hero h1{font-size:clamp(2rem,8.2vw,2.6rem);line-height:1.16}
  .hero-number{clip-path:none;border-top:1px solid var(--line);padding:1.5rem}.hero-number strong{font-size:4.8rem}.school-head{padding:1.5rem;border-radius:18px}
  h2{font-size:1.55rem}.compare{display:block;overflow-x:auto;font-size:.84rem}.compare th,.compare td{padding:.6rem}.flat{padding-top:1rem}
  div[data-testid="stRadio"] div[role="radiogroup"]{max-width:100%}.stTabs [data-baseweb="tab"]{padding:.65rem .8rem}
}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

try:
    DB = resolve_database()
except Exception as exc:
    st.error(f"数据库启动校验失败：{exc}")
    st.stop()
DB_STAMP = DB.stat().st_mtime_ns


@st.cache_data(show_spinner=False)
def query(stamp: int, sql: str, params: tuple = ()) -> pd.DataFrame:
    del stamp
    uri = f"file:{DB.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        return pd.read_sql_query(sql, con, params=params)


def scalar(stamp: int, sql: str, params: tuple = ()):
    frame = query(stamp, sql, params)
    return None if frame.empty else frame.iloc[0, 0]


U = query(DB_STAMP, "SELECT * FROM universities ORDER BY university_id")
DIM = query(DB_STAMP, "SELECT * FROM v_university_dimension_counts ORDER BY university_id")
QUALITY = query(DB_STAMP, "SELECT * FROM v_university_quality ORDER BY university_id")
COUNT_ROWS = query(DB_STAMP, "SELECT * FROM v_export_counts")
COUNTS = dict(zip(COUNT_ROWS.table_name, COUNT_ROWS.record_count)) if not COUNT_ROWS.empty else {}
NAME = dict(zip(U.university_id, U.university_name_cn))


def count(table: str) -> int:
    return int(COUNTS.get(table, 0) or 0)


def related(table: str, uid: str) -> pd.DataFrame:
    _, order = DETAIL_TABLES[table]
    return query(DB_STAMP, f"SELECT * FROM {table} WHERE university_id=? ORDER BY {order}", (uid,))


def university(uid: str) -> pd.Series:
    return U.loc[U.university_id == uid].iloc[0]


def show_frame(frame: pd.DataFrame, columns: list[str] | None = None, empty: str = "现有资料未提供可统一结构化的信息，数据库不作推断补录。"):
    if columns is not None:
        frame = frame[[c for c in columns if c in frame.columns]]
    if frame.empty:
        st.info(empty)
        return
    shown = frame.rename(columns={c: LABELS.get(c, c) for c in frame.columns}).copy()
    for column in shown.columns:
        if shown[column].dtype == "object":
            shown[column] = shown[column].where(shown[column].notna(), "")
            types = {type(v) for v in shown[column] if pd.notna(v)}
            if len(types) > 1:
                shown[column] = shown[column].map(lambda v: "" if pd.isna(v) else str(v))
    link_columns = {}
    for original in ("homepage_url", "url"):
        label = LABELS.get(original, original)
        if label in shown.columns:
            link_columns[label] = st.column_config.LinkColumn(label)
    st.dataframe(shown, width="stretch", hide_index=True, column_config=link_columns)


def scope_filter(frame: pd.DataFrame, program_id: str) -> pd.DataFrame:
    if program_id == "ALL" or "program_id" not in frame.columns:
        return frame
    return frame[(frame.program_id == program_id) | (frame.program_id.isna())]


def open_school(uid: str):
    st.session_state.selected_uid = uid
    st.session_state.page = "高校详情"


def open_evidence(uid: str):
    st.session_state.evidence_uid = uid
    st.session_state.page = "来源与证据"


def safe_attachment(row: pd.Series) -> Path | None:
    candidate = (BASE / str(row.local_path)).resolve()
    try:
        candidate.relative_to(BASE)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def attachment_download(row: pd.Series, key: str):
    if row.download_permission != "allowed":
        st.warning("该附件未标记为允许公开下载。")
        return
    path = safe_attachment(row)
    if path is None:
        st.error("附件记录存在，但部署目录中未找到对应文件。")
        return
    st.download_button(
        f"下载 {row.file_name}",
        data=path.read_bytes(),
        file_name=str(row.file_name),
        mime=str(row.mime_type or "application/octet-stream"),
        key=key,
        type="primary",
        width="stretch",
    )


def comparison_table(frame: pd.DataFrame, metrics: list[tuple[str, str]]):
    heads = "".join(f"<th>{html.escape(str(x))}</th>" for x in frame.columns)
    body = []
    for key, label in metrics:
        cells = "".join(f"<td>{html.escape(str(frame.loc[key, col]))}</td>" for col in frame.columns)
        body.append(f"<tr><td>{html.escape(label)}</td>{cells}</tr>")
    st.markdown(f"<table class='compare'><thead><tr><th>比较指标</th>{heads}</tr></thead><tbody>{''.join(body)}</tbody></table>", unsafe_allow_html=True)


def home():
    structured = int((U.data_status != "not_started").sum())
    st.markdown(f"""
    <section class="hero">
      <div class="hero-copy"><div class="kicker">山东大学 · 国家语委项目成果 · V2 全量结构化初稿</div>
      <h1>世界一流大学<br>“语言＋人工智能”<br>复合型人才培养模式</h1>
      <p>围绕培养目标、课程体系、师资配置、实践环节、评价机制、科研平台与相关机构六个维度，统一整理 {len(U)} 所高校的培养项目、科研、成果、学生发展和原文证据。</p></div>
      <div class="hero-number"><strong>{structured:02d}</strong><span>所高校已完成机器结构化<br>{count('attachments')} 份附件 · {count('raw_fragments')} 条原文片段</span></div>
    </section>""", unsafe_allow_html=True)

    st.markdown("## 数据库总览")
    cols = st.columns(6)
    metrics = [
        ("已登记高校", len(U)), ("培养项目／路径", count("programs")),
        ("课程／研究主题", count("courses")), ("科研项目", count("research_projects")),
        ("科研成果", count("research_outputs")), ("证据关系", count("source_links")),
    ]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, f"{value:,}")
    st.markdown("<div class='notice'>数据库底层保留结构化记录、原文证据与附件，专家展示页面聚焦培养模式与科研数据。机器结构化初稿不等于人工已核验；附件获准公开下载也不等于其来源已经成为官方已核验来源。记录数量只反映资料覆盖，不用于高校办学质量排名。</div>", unsafe_allow_html=True)

    st.markdown("## 高校检索")
    c1, c2 = st.columns([2, 1])
    with c1:
        term = st.text_input("高校名称", placeholder="输入中文高校名称，例如：北京大学")
    with c2:
        regions = sorted(x for x in U.region.dropna().unique() if str(x).strip())
        region = st.selectbox("区域", ["全部"] + regions)
    mask = pd.Series(True, index=U.index)
    if term.strip():
        needle = term.strip().lower()
        searchable = U["university_name_cn"].fillna("").str.lower()
        mask &= searchable.str.contains(needle, regex=False)
    if region != "全部":
        mask &= U.region == region
    results = U[mask].merge(DIM[["university_id", "program_count", "courses_count", "research_projects_count", "research_outputs_count"]], on="university_id", how="left")
    st.caption(f"检索到 {len(results)} 所高校")
    show_frame(results, ["university_name_cn", "region", "program_count", "courses_count", "research_projects_count", "research_outputs_count"], "没有符合当前条件的高校，请调整检索词或筛选条件。")
    if not results.empty:
        uid = st.selectbox("选择要打开的高校", results.university_id.tolist(), format_func=lambda x: NAME.get(x, x), key="home_uid")
        st.button("打开高校完整档案", type="primary", on_click=open_school, args=(uid,))

    st.markdown("## 2—4 校比较")
    default_compare = [x for x in ("U013", "U041", "U005", "U008") if x in NAME][:2]
    chosen = st.multiselect("选择高校", U.university_id.tolist(), default=default_compare, max_selections=4, format_func=lambda x: NAME.get(x, x))
    if len(chosen) == 1:
        st.info("再选择至少 1 所高校即可比较。")
    elif chosen:
        comp = DIM[DIM.university_id.isin(chosen)].set_index("university_id").loc[chosen]
        comp.index = [NAME[x] for x in comp.index]
        comparison_table(comp.T, [
            ("program_count", "培养项目／路径"), ("objectives_count", "培养目标"),
            ("courses_count", "课程／研究主题"), ("faculty_count", "师资"),
            ("practice_count", "实践环节"), ("evaluation_count", "评价机制"),
            ("organizations_count", "科研平台与相关机构"), ("research_projects_count", "科研项目"),
            ("research_outputs_count", "科研成果"), ("student_development_count", "学生发展"),
            ("attachment_count", "附件"),
        ])
        st.caption("比较值均由 V2 统计视图实时生成，仅表示已收录记录数。")

    st.markdown("## 六维分析框架")
    cols = st.columns(3)
    for i, (no, title, desc) in enumerate(DIMENSIONS):
        cols[i % 3].markdown(f"<div class='flat'><div class='no'>{no}</div><h3>{title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)

    st.markdown("## 数据覆盖与质量流程")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 高校区域分布")
        chart = U.assign(region=U.region.fillna("未注明")).groupby("region").size().rename("高校数").to_frame()
        st.bar_chart(chart, color="#8cb4e7")
    with c2:
        st.markdown("### 培养层次／路径分布")
        levels = query(DB_STAMP, "SELECT coalesce(nullif(level,''),'未注明') AS level,count(*) AS n FROM programs GROUP BY coalesce(nullif(level,''),'未注明') ORDER BY n DESC")
        if levels.empty:
            st.info("当前没有培养项目／路径记录。")
        else:
            st.bar_chart(levels.set_index("level"), color="#8cb4e7")
    quality_columns = ["university_name_cn", "dimension_coverage_count", "evidence_coverage_percent"]
    show_frame(QUALITY, quality_columns)
    st.caption("六维覆盖与证据覆盖率分别报告；数量与覆盖指标不用于评价高校办学水平。")


def course_rows(uid: str, program_id: str) -> pd.DataFrame:
    params: list = [uid]
    condition = ""
    if program_id != "ALL":
        condition = " AND pc.program_id=?"
        params.append(program_id)
    return query(DB_STAMP, f"""
        SELECT c.course_code,c.course_name,c.course_name_en,c.course_name_zh,c.language,
               c.ai_tag,c.language_tag,c.practice_tag,p.program_name_cn,pc.module,pc.stage,
               pc.semester,pc.academic_year,pc.required_elective,pc.credits,pc.credit_system,
               pc.lecture_hours,pc.directed_study_hours,pc.practical_hours
        FROM courses c
        LEFT JOIN program_course pc ON pc.course_id=c.course_id
        LEFT JOIN programs p ON p.program_id=pc.program_id
        WHERE c.university_id=? {condition}
        ORDER BY c.course_id,pc.program_course_id
    """, tuple(params))


def program_overview(programs: pd.DataFrame):
    show_frame(programs, ["program_name_cn", "program_kind", "is_formal_degree", "level", "degree", "duration", "language_of_instruction"])
    for _, row in programs.iterrows():
        with st.expander(str(row.program_name_cn), expanded=len(programs) == 1):
            if pd.notna(row.positioning) and str(row.positioning).strip():
                st.markdown("**项目定位**")
                st.write(row.positioning)
            if pd.notna(row.admission_summary) and str(row.admission_summary).strip():
                st.markdown("**招生／基础要求**")
                st.write(row.admission_summary)
            st.caption(f"记录类型：{row.program_kind or '未注明'}｜培养层次：{row.level or row.level_raw or '未注明'}｜审核状态：{row.review_status}")


def detail():
    if st.session_state.get("selected_uid") not in NAME:
        st.session_state.selected_uid = U.university_id.iloc[0]
    uid = st.selectbox("高校", U.university_id.tolist(), format_func=lambda x: NAME.get(x, x), key="selected_uid")
    u = university(uid)
    st.markdown(f"<div class='school-head'><div class='kicker'>{html.escape(str(u.country))} · {html.escape(str(u.region))} · {html.escape(str(uid))}</div><h1>{html.escape(str(u.university_name_cn))}</h1><p>{html.escape(str(u.university_name_en or ''))}</p></div>", unsafe_allow_html=True)
    drow = DIM[DIM.university_id == uid]
    d = drow.iloc[0] if not drow.empty else pd.Series(dtype=object)
    cols = st.columns(6)
    detail_metrics = [
        ("项目／路径", d.get("program_count", 0)), ("课程", d.get("courses_count", 0)),
        ("师资", d.get("faculty_count", 0)), ("科研项目", d.get("research_projects_count", 0)),
        ("科研成果", d.get("research_outputs_count", 0)), ("附件", d.get("attachment_count", 0)),
    ]
    for col, (label, value) in zip(cols, detail_metrics):
        col.metric(label, f"{int(value or 0):,}")
    qrow = QUALITY[QUALITY.university_id == uid]
    if not qrow.empty:
        q = qrow.iloc[0]
        st.markdown(f"<div class='notice'>数据状态：<strong>{html.escape(str(u.data_status))}</strong>　审核状态：{html.escape(str(u.review_status))}　六维覆盖：{int(q.dimension_coverage_count)}/6　证据覆盖：{q.evidence_coverage_percent:.1f}%　官方已核验：{q.official_verified_percent:.1f}%　未处理原文：{int(q.unprocessed_fragment_count)}</div>", unsafe_allow_html=True)

    programs = related("programs", uid)
    program_options = ["ALL"] + programs.program_id.tolist()
    program_names = dict(zip(programs.program_id, programs.program_name_cn))
    selected_program = st.selectbox("项目筛选（学校层面记录仍保留）", program_options, format_func=lambda x: "全部项目／路径" if x == "ALL" else program_names.get(x, x))
    if selected_program != "ALL":
        programs = programs[programs.program_id == selected_program]

    tabs = st.tabs([
        "学校概览", "培养目标", "课程体系", "师资配置", "实践环节", "评价机制",
        "科研平台与相关机构", "科研项目", "科研成果", "学生发展",
    ])
    with tabs[0]:
        st.markdown("### 培养项目／路径")
        program_overview(programs)
        st.markdown("### 高校登记信息")
        info = pd.DataFrame([
            {"项目": "高校类型", "内容": u.university_type}, {"项目": "排名信息原文", "内容": u.ranking_info},
            {"项目": "采集年份", "内容": u.collection_year}, {"项目": "官方网站", "内容": u.official_website},
            {"项目": "备注", "内容": u.notes},
        ])
        show_frame(info)
    with tabs[1]:
        frame = scope_filter(related("objectives", uid), selected_program)
        show_frame(frame, ["dimension", "description"])
    with tabs[2]:
        show_frame(course_rows(uid, selected_program))
    with tabs[3]:
        frame = related("faculty", uid)
        show_frame(frame, ["name", "title", "primary_unit_text", "research_direction", "homepage_url", "biography", "ai_tag", "language_tag"])
        st.caption("教师与平台的多对多关系、个人主页和简介按原资料保留；未明确的单位归属不作推断。")
    with tabs[4]:
        frame = scope_filter(related("practice", uid), selected_program)
        show_frame(frame, ["practice_type", "name", "duration", "credits", "credit_system", "content", "assessment"])
    with tabs[5]:
        frame = scope_filter(related("evaluation", uid), selected_program)
        show_frame(frame, ["evaluation_type", "method", "criteria", "weight", "output"])
    with tabs[6]:
        frame = related("organizations", uid)
        show_frame(frame, ["name", "name_en", "org_type", "research_directions", "description"])
    with tabs[7]:
        frame = related("research_projects", uid)
        show_frame(frame, ["project_name", "project_name_en", "project_type", "funder", "grant_number", "start_date", "end_date", "status", "description", "review_status"])
        st.caption("科研团队、研究课题和培养项目分开记录；科研项目不自动视为正式学位项目。")
    with tabs[8]:
        frame = related("research_outputs", uid)
        show_frame(frame, ["output_type", "title", "authors_text", "publication_year", "venue", "doi", "url", "description", "review_status"])
    with tabs[9]:
        frame = scope_filter(related("student_development", uid), selected_program)
        show_frame(frame, ["record_type", "subject_type", "person_name_public", "student_status", "degree_level", "study_period", "content", "achievement", "destination_type", "destination_text", "destination_organization", "event_year", "review_status"])
        st.caption("仅展示公开资料中的学生科研、升学就业与校友信息，不补充私人联系方式或推测去向。")


def research():
    st.markdown("<div class='kicker'>RESEARCH / DEVELOPMENT</div><h1>科研与学生发展</h1><div class='rule'></div>", unsafe_allow_html=True)
    uid = st.selectbox("高校", U.university_id.tolist(), format_func=lambda x: NAME.get(x, x), key="research_uid")
    kind = st.radio("记录类别", ["科研项目", "科研成果", "学生发展"], horizontal=True)
    table = {"科研项目": "research_projects", "科研成果": "research_outputs", "学生发展": "student_development"}[kind]
    frame = related(table, uid)
    term = st.text_input("在当前高校记录中检索", key=f"research_search_{kind}", placeholder="输入题名、姓名、方向、年份或说明文字")
    if term.strip():
        needle = term.strip().lower()
        mask = frame.fillna("").astype(str).agg(" ".join, axis=1).str.lower().str.contains(needle, regex=False)
        frame = frame[mask]
    if kind == "科研项目":
        types = sorted(x for x in frame.project_type.dropna().unique() if str(x).strip()) if not frame.empty else []
        selected = st.multiselect("项目类型", types)
        if selected:
            frame = frame[frame.project_type.isin(selected)]
        st.metric("当前记录", len(frame))
        show_frame(frame, ["project_name", "project_name_en", "project_type", "funder", "grant_number", "start_date", "end_date", "status", "description", "review_status"])
    elif kind == "科研成果":
        c1, c2 = st.columns(2)
        with c1:
            types = sorted(x for x in frame.output_type.dropna().unique() if str(x).strip()) if not frame.empty else []
            selected = st.multiselect("成果类型", types)
        with c2:
            years = sorted((int(x) for x in frame.publication_year.dropna().unique()), reverse=True) if not frame.empty else []
            selected_years = st.multiselect("发表年份", years)
        if selected:
            frame = frame[frame.output_type.isin(selected)]
        if selected_years:
            frame = frame[frame.publication_year.isin(selected_years)]
        st.metric("当前记录", len(frame))
        show_frame(frame, ["output_type", "title", "authors_text", "publication_year", "venue", "volume_issue_pages", "doi", "url", "description", "review_status"])
    else:
        types = sorted(x for x in frame.record_type.dropna().unique() if str(x).strip()) if not frame.empty else []
        selected = st.multiselect("发展记录类型", types)
        if selected:
            frame = frame[frame.record_type.isin(selected)]
        st.metric("当前记录", len(frame))
        show_frame(frame, ["record_type", "subject_type", "person_name_public", "student_status", "degree_level", "study_period", "content", "achievement", "destination_type", "destination_text", "destination_organization", "event_year", "review_status"])
    st.button("回查当前高校的来源与证据", on_click=open_evidence, args=(uid,))


def source_directory(uid: str):
    frame = related("sources", uid)
    c1, c2 = st.columns(2)
    with c1:
        types = sorted(x for x in frame.source_type.dropna().unique() if str(x).strip()) if not frame.empty else []
        selected_types = st.multiselect("来源类型", types)
    with c2:
        statuses = sorted(x for x in frame.verification_status.dropna().unique() if str(x).strip()) if not frame.empty else []
        selected_status = st.multiselect("核验状态", statuses)
    term = st.text_input("检索来源名称、链接或备注", key="source_term")
    if selected_types:
        frame = frame[frame.source_type.isin(selected_types)]
    if selected_status:
        frame = frame[frame.verification_status.isin(selected_status)]
    if term.strip():
        frame = frame[frame.fillna("").astype(str).agg(" ".join, axis=1).str.contains(term.strip(), case=False, regex=False)]
    st.caption(f"当前显示 {len(frame)} 条来源。外部 URL 候选若未实际访问，不会标记为官方已核验。")
    show_frame(frame, ["source_name", "source_type", "url", "publisher", "publication_date", "access_date", "is_official", "verification_status", "note", "review_status"])


def evidence_explorer(uid: str):
    entity_label = st.selectbox("业务记录类型", list(ENTITY_TYPES))
    table, pk, label = ENTITY_TYPES[entity_label]
    records = query(DB_STAMP, f"SELECT * FROM {table} WHERE university_id=? ORDER BY {pk}", (uid,))
    term = st.text_input("先筛选业务记录", key="evidence_record_term", placeholder="输入名称、题名或内容片段")
    if term.strip() and not records.empty:
        records = records[records.fillna("").astype(str).agg(" ".join, axis=1).str.contains(term.strip(), case=False, regex=False)]
    if records.empty:
        st.info("该校当前类别没有符合筛选条件的业务记录。")
        return
    total = len(records)
    if total > 300:
        st.caption(f"筛选后有 {total} 条记录，选择框仅列出前 300 条；请进一步缩小范围。")
        records = records.head(300)
    def record_label(value):
        row = records[records[pk] == value].iloc[0]
        text = str(row[label] or value)
        return f"{text[:90]}{'…' if len(text) > 90 else ''}｜{value}"
    entity_id = st.selectbox("选择业务记录", records[pk].tolist(), format_func=record_label)
    selected = records[records[pk] == entity_id].iloc[0]
    with st.expander("查看该记录的结构化字段", expanded=False):
        details = pd.DataFrame({"字段": selected.index, "值": [str(v) if pd.notna(v) else "" for v in selected.values]})
        show_frame(details[details["字段"] != "raw_text"])
    evidence = query(DB_STAMP, """
        SELECT s.relation_type,s.dimension,s.locator,s.evidence_quote,s.is_primary,s.note,
               src.source_name,src.url,src.verification_status,a.file_name,
               f.content_text,f.locator AS fragment_locator,f.disposition
        FROM source_links s
        LEFT JOIN sources src ON src.source_id=s.source_id
        LEFT JOIN attachments a ON a.attachment_id=s.attachment_id
        LEFT JOIN raw_fragments f ON f.fragment_id=s.fragment_id
        WHERE s.entity_type=? AND s.entity_id=?
        ORDER BY s.link_id
    """, (table, entity_id))
    st.markdown(f"### 原文证据：{len(evidence)} 条")
    if evidence.empty:
        st.warning("该业务记录没有证据连接，应进入质量核验流程。")
        return
    for i, row in evidence.iterrows():
        title = row.source_name or row.file_name or f"证据 {i + 1}"
        with st.expander(f"{i + 1}. {title}", expanded=len(evidence) == 1):
            st.caption(f"定位：{row.locator or row.fragment_locator or '未注明'}｜关系：{row.relation_type or '未注明'}｜来源核验：{row.verification_status or '未注明'}")
            quote = row.evidence_quote if pd.notna(row.evidence_quote) and str(row.evidence_quote).strip() else row.content_text
            if pd.notna(quote) and str(quote).strip():
                st.write(quote)
            if pd.notna(row.note) and str(row.note).strip():
                st.caption(row.note)
            if pd.notna(row.url) and str(row.url).strip():
                st.markdown(f"[来源链接]({row.url})")
    st.markdown("### 搜索该校原文片段")
    with st.form(f"fragment_search_{uid}"):
        fragment_term = st.text_input("原文关键词", placeholder="提交后在 raw_fragments 中检索，最多返回 100 条")
        submitted = st.form_submit_button("检索原文")
    if submitted:
        if len(fragment_term.strip()) < 2:
            st.warning("请输入至少 2 个字符。")
        else:
            fragments = query(DB_STAMP, """
                SELECT f.content_type,f.content_text,f.locator,f.disposition,f.disposition_note,a.file_name
                FROM raw_fragments f LEFT JOIN attachments a ON a.attachment_id=f.attachment_id
                WHERE f.university_id=? AND f.content_text LIKE ? ESCAPE '\\'
                ORDER BY f.sequence_no,f.fragment_id LIMIT 100
            """, (uid, "%" + fragment_term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"))
            st.caption(f"返回 {len(fragments)} 条（最多 100 条）")
            show_frame(fragments, ["content_type", "content_text", "locator", "disposition", "disposition_note", "file_name"], "未找到包含该关键词的原文片段。")


def quality_status(uid: str):
    q = QUALITY[QUALITY.university_id == uid]
    if q.empty:
        st.info("当前高校没有质量视图记录。")
    else:
        row = q.iloc[0]
        cols = st.columns(5)
        for col, label, value in [
            (cols[0], "六维覆盖", f"{int(row.dimension_coverage_count)}/6"),
            (cols[1], "证据覆盖", f"{row.evidence_coverage_percent:.1f}%"),
            (cols[2], "官方已核验", f"{row.official_verified_percent:.1f}%"),
            (cols[3], "开放问题", int(row.open_issue_count)),
            (cols[4], "未处理原文", int(row.unprocessed_fragment_count)),
        ]:
            col.metric(label, value)
        st.caption(f"质量流程状态：{row.quality_status}。数量与流程指标不用于评价高校办学水平。")
    issues = related("review_issues", uid)
    show_frame(issues, ["issue_type", "severity", "entity_type", "field_name", "description", "suggested_action", "status", "resolution_note"], "该校没有登记的待核验事项。")
    st.markdown("### 全库原文去向")
    disposition = query(DB_STAMP, "SELECT disposition,count(*) AS n FROM raw_fragments GROUP BY disposition ORDER BY disposition")
    show_frame(disposition)
    unprocessed = int(scalar(DB_STAMP, "SELECT count(*) FROM raw_fragments WHERE disposition='unprocessed'") or 0)
    if unprocessed == 0:
        st.success("全库 unprocessed=0；所有原文片段均已标记为 mapped、raw_only 或 issue_created。")
    else:
        st.error(f"全库仍有 {unprocessed} 条 unprocessed 原文，需要继续处理。")


def sources_page():
    st.markdown("<div class='kicker'>PROVENANCE / EVIDENCE / QUALITY</div><h1>来源与证据</h1><div class='rule'></div>", unsafe_allow_html=True)
    if st.session_state.get("evidence_uid") not in NAME:
        st.session_state.evidence_uid = st.session_state.get("selected_uid") if st.session_state.get("selected_uid") in NAME else U.university_id.iloc[0]
    uid = st.selectbox("高校", U.university_id.tolist(), format_func=lambda x: NAME.get(x, x), key="evidence_uid")
    mode = st.radio("查看内容", ["来源目录", "原文证据", "质量状态"], horizontal=True)
    if mode == "来源目录":
        source_directory(uid)
    elif mode == "原文证据":
        evidence_explorer(uid)
    else:
        quality_status(uid)


def downloads():
    st.markdown("<div class='kicker'>AUTHORIZED SOURCE FILES</div><h1>附件下载</h1><div class='rule'></div>", unsafe_allow_html=True)
    st.markdown("<div class='notice'>用户已于 2026-11-24 明确授权全部文件公开下载。此授权仅改变下载许可，不代表附件来源已核验为官方来源。文件按数据库登记的本地路径提供，页面会同时显示 SHA-256、解析状态和页数。</div>", unsafe_allow_html=True)
    all_attachments = query(DB_STAMP, """
        SELECT a.attachment_id,a.university_id,u.university_name_cn,a.file_name,a.attachment_type,
               a.file_size_bytes,a.page_count,a.download_permission,a.extraction_status,a.local_path,a.file_hash
        FROM attachments a JOIN universities u USING(university_id) ORDER BY a.attachment_id
    """)
    cols = st.columns(4)
    cols[0].metric("附件总数", len(all_attachments))
    cols[1].metric("允许下载", int((all_attachments.download_permission == "allowed").sum()))
    cols[2].metric("DOCX", int(all_attachments.file_name.str.lower().str.endswith(".docx").sum()))
    cols[3].metric("PDF 总页数", int(all_attachments.page_count.fillna(0).sum()))
    term = st.text_input("检索附件目录", placeholder="输入高校、文件名或路径")
    catalog = all_attachments
    if term.strip():
        catalog = catalog[catalog.fillna("").astype(str).agg(" ".join, axis=1).str.contains(term.strip(), case=False, regex=False)]
    show_frame(catalog, ["university_name_cn", "file_name", "attachment_type", "file_size_bytes", "page_count", "download_permission", "extraction_status", "local_path", "file_hash"])
    st.markdown("## 按高校下载")
    uid = st.selectbox("高校", U.university_id.tolist(), format_func=lambda x: NAME.get(x, x), key="download_uid")
    frame = all_attachments[all_attachments.university_id == uid]
    if frame.empty:
        st.info("该校没有附件记录。")
    else:
        aid = st.selectbox("附件", frame.attachment_id.tolist(), format_func=lambda x: frame.loc[frame.attachment_id == x, "file_name"].iloc[0])
        selected = frame[frame.attachment_id == aid].iloc[0]
        full = query(DB_STAMP, "SELECT * FROM attachments WHERE attachment_id=?", (aid,)).iloc[0]
        st.caption(f"文件大小：{int(full.file_size_bytes):,} 字节｜SHA-256：{full.file_hash}")
        attachment_download(full, f"download_{aid}")
    st.markdown("## 同步数据文件")
    if XLSX.exists():
        st.download_button("下载同步 Excel（21 张数据表）", data=XLSX.read_bytes(), file_name="language_ai_cases.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    else:
        st.warning("部署目录中未找到同步 Excel 文件。")


def main():
    if "page" not in st.session_state:
        st.session_state.page = "数据库首页"
    if st.session_state.page not in PAGES:
        st.session_state.page = "数据库首页"
    st.radio("主导航", PAGES, horizontal=True, label_visibility="collapsed", key="page")
    page = st.session_state.page
    if page == "数据库首页":
        home()
    else:
        detail()
    st.markdown("<div class='rule'></div><p class='small'>世界一流大学“语言＋人工智能”复合型人才培养模式研究｜依托山东大学<br>数据库、Excel 与网页使用同一 V2 SQLite 数据源；不推断缺失信息，不以记录数量替代质量判断。</p>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
