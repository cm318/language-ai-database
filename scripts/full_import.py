from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile

import fitz
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "language_ai_cases.db"
BASE = ROOT / "backups" / "pre_full_56_20261124" / "data" / "language_ai_cases.db"
BUILD = Path("/tmp/language_ai_cases.full.building.db")
OUTPUT_BUILD = ROOT / "data" / "language_ai_cases.full.building.db"
PROMOTE_STAGING = ROOT / "data" / "language_ai_cases.full.promoting.db"
RAW = ROOT / "raw_files"
EMBEDDED_MANIFEST = ROOT / "quality_reports" / "source_audit" / "embedded_files_manifest.json"
OCR_JSON = ROOT / "quality_reports" / "source_audit" / "docx_image_ocr.json"
SUMMARY_JSON = ROOT / "quality_reports" / "full_import_summary.json"
NOW = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
PARSER_VERSION = "full-source-import-1.0.1"
W = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
URL_RE = re.compile(r"https?://[^\s<>\"'】）]+", re.I)
SEARCH_HOSTS = {"bing.com", "www.bing.com", "google.com", "www.google.com", "baidu.com", "www.baidu.com"}
DIM = {
    "universities": "university_overview", "programs": "program_overview",
    "objectives": "培养目标", "courses": "课程体系", "program_course": "课程体系",
    "faculty": "师资配置", "faculty_organization": "师资配置", "practice": "实践环节",
    "evaluation": "评价机制", "organizations": "科研平台与相关机构",
    "research_projects": "research_projects", "research_project_links": "research_projects",
    "research_outputs": "research_outputs", "research_output_links": "research_outputs",
    "student_development": "student_development",
}
PREFIX = {
    "programs": "P", "objectives": "OBJ", "courses": "C", "program_course": "PC",
    "faculty": "F", "faculty_organization": "FO", "practice": "PRAC", "evaluation": "EV",
    "organizations": "O", "research_projects": "RP", "research_project_links": "RPL",
    "research_outputs": "RO", "research_output_links": "ROL", "student_development": "SD",
    "source_links": "SLF", "review_issues": "RIF", "sources": "SRCURL",
}
TABLE_PK = {
    "programs": "program_id", "objectives": "objective_id", "courses": "course_id",
    "program_course": "program_course_id", "faculty": "faculty_id",
    "faculty_organization": "faculty_organization_id", "practice": "practice_id",
    "evaluation": "evaluation_id", "organizations": "organization_id",
    "research_projects": "project_id", "research_project_links": "project_link_id",
    "research_outputs": "output_id", "research_output_links": "output_link_id",
    "student_development": "development_id", "source_links": "link_id",
    "review_issues": "issue_id", "sources": "source_id",
}

GENERIC_HEADINGS = {
    "简介", "介绍", "个人简介", "概况", "概述", "课程", "课程设置", "课程概览", "课程结构", "培养方案",
    "项目概览", "专业概览", "培养目标", "培养要求", "毕业要求", "入学要求", "招生要求", "招生信息",
    "研究方向", "研究领域", "研究工作", "研究", "核心成果", "代表性成果", "代表性出版物", "出版物",
    "论文", "论文发表", "发表成果", "专利", "专利列表", "软件", "开源项目", "书籍", "著作", "奖项",
    "荣誉奖励", "荣誉奖项", "科研项目", "研究项目", "课题", "实践", "实习", "科研训练", "评价", "考核",
    "教学工作", "教学", "学术服务", "学术任职", "教育与经历", "教育经历", "工作经历", "学术背景",
    "学术出版", "学术兼职", "主要荣誉", "部分出版物", "核心成员", "现成员", "前成员", "在读学生",
    "毕业生", "学术人员", "研究人员", "荣誉人员", "讲师", "设施", "资源", "职业前景", "职业机会",
    "未来前景", "就业", "升学", "课程地图", "标准修读形式", "修读规定", "学分要求", "考试科目",
    "报考资格要求", "招生流程", "模块手册", "学习和考试规定", "课程列表", "选修课程", "必修课程",
    "通识课程", "专业课程", "师资", "师资力量", "实验室", "研究所", "研究中心", "研究院", "研究组",
    "团队", "平台", "科研平台", "相关机构", "中心主任", "指导委员会", "研究人员 staff", "附属成员",
    "主要优势", "课程基础", "职业发展", "研究生", "博士生", "硕士生", "博士后与博士生", "其他", "初试", "复试",
}
STOP_CONTENT = {
    "简介", "课程", "课程设置", "培养方案", "研究方向", "研究领域", "科研项目", "研究项目", "论文",
    "出版物", "核心成果", "代表性成果", "专利", "奖项", "荣誉奖励", "学生培养", "学生发展", "师资力量",
}
LEVEL_WORDS = [
    (r"硕博连读|硕博|master.*ph\.?d|integrated.*ph\.?d", "硕博"),
    (r"本研贯通|本硕|贯通", "本研贯通"),
    (r"博士后|postdoctoral|postdoc", "博士后"),
    (r"博士|ph\.?d|doctor", "博士"),
    (r"硕士|研究生硕士|master|msc|meng|mres|m\.phil|mphil", "硕士"),
    (r"本科|学士|undergraduate|bachelor", "本科"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compact(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def norm(value) -> str:
    value = compact(value).lower()
    value = re.sub(r"^[（(]?[一二三四五六七八九十百0-9]+[）)]?[、.．:：]?\s*", "", value)
    value = re.sub(r"^[（(][一二三四五六七八九十百0-9]+[）)]\s*", "", value)
    return re.sub(r"[\s,，。.．:：;；/\\_—–-]+", "", value)


def strip_number(value: str) -> str:
    value = compact(value)
    value = re.sub(r"^[一二三四五六七八九十百]+[、.．]?\s*", "", value)
    value = re.sub(r"^[（(][一二三四五六七八九十百0-9]+[）)]\s*", "", value)
    value = re.sub(r"^\d+[、.．]\s*", "", value)
    return value.strip(" ,，")


def main_section(value: str):
    raw = compact(value)
    # 项目内部的“（5）师资力量”等栏目不得切换全校主章节。
    if re.match(r"^[（(][一二三四五六七八九十百0-9]+[）)]", raw):
        return None
    numbered = bool(re.match(r"^(?:[一二三四五六七八九十百]+|\d+)[、.．]", raw))
    bare = strip_number(raw)
    if not numbered and raw != bare:
        return None
    text = norm(raw)
    if any(x in text for x in ("学科与专业设置", "学科和专业设置", "学了与专业设置")):
        return "academic"
    if "科研平台" in text or ("相关机构" in text and "师资" not in text):
        return "organizations"
    if "师资力量" in text or norm(bare) in ("师资", "教师队伍"):
        return "faculty"
    if any(x in text for x in ("学生发展", "学生培养", "人才培养")):
        return "student"
    return None


def level_of(value: str):
    text = compact(value).lower()
    if len(text) > 45 or any(x in text for x in ("课程", "学分", "培养目标", "招生", "简介")):
        return None
    for pattern, label in LEVEL_WORDS:
        if re.search(pattern, text, re.I):
            return label
    return None


def is_level_marker(value: str, level):
    text = compact(value).lower()
    patterns = {
        "本科": r"本科(?:专业|项目|阶段|层次|培养|生)?|undergraduate(?: programs?)?|bachelor(?: programs?)?",
        "硕士": r"硕士(?:专业|项目|阶段|层次|培养|生|研究生)?|master(?: programs?)?",
        "博士": r"博士(?:专业|项目|阶段|层次|培养|生|研究生)?|ph\.?d\.?(?: programs?)?|doctoral(?: programs?)?",
        "硕博": r"硕博(?:连读|专业|项目|阶段|层次|培养)?",
        "本研贯通": r"本研贯通|本硕贯通",
        "博士后": r"博士后|postdoctoral|postdoc",
    }
    return bool(level in patterns and re.fullmatch(patterns[level], text, re.I))


def generic_heading(value: str) -> bool:
    text = strip_number(value).strip(" ,，")
    n = norm(text)
    if n in {norm(x) for x in GENERIC_HEADINGS}:
        return True
    if re.fullmatch(r"进阶\s*\d+|路径\s*\d+", text, re.I) or re.search(r"年制(?:学士)?$", text):
        return True
    return any(n.startswith(norm(x)) and len(n) <= len(norm(x)) + 8 for x in
               ("简介", "课程设置", "培养方案", "科研项目", "研究方向", "核心成员", "研究人员", "学术人员"))


def classify_topic(value: str):
    text = compact(value).lower()
    if not text or len(text) > 100:
        return None
    if re.search(r"培养目标|培养要求|学习目标|学习成果|人才定位|能力要求|learning outcomes?|program objectives?", text):
        return "objective"
    if re.search(r"招生|入学要求|申请要求|初试科目|复试科目|考试科目|报考资格|admission|entry requirements?|application", text):
        return "admission"
    if re.search(r"毕业要求|学位要求|评价|考核|考试|修读规定|学分要求|assessment|examinations?|graduation requirements?|degree requirements?", text):
        return "evaluation"
    if re.search(r"实习|实践|科研训练|项目训练|产学|capstone|internship|directed study|毕业论文|thesis", text):
        return "practice"
    if re.search(r"科研项目|研究项目|研究课题|课题|research projects?|funded projects?|project list", text):
        return "project"
    if re.search(r"成果|论文|出版物|发表|专利|软著|软件|模型|书籍|著作|奖项|奖励|publications?|papers?|patents?|software|awards?|books?|talks?", text):
        return "output"
    if re.search(r"课程|培养方案|模块|curriculum|courses?|modules?", text):
        return "course"
    if re.search(r"研究方向|研究领域|研究重点|research directions?|research areas?|research interests?", text):
        return "research_direction"
    if re.search(r"简介|介绍|概况|概述|项目概览|专业概览|overview|introduction", text):
        return "intro"
    if re.search(r"职业|就业|升学|前景|careers?|alumni|employment", text):
        return "career"
    return None


def pdf_topic(value: str):
    """仅在明确PDF栏目标题处切换状态，避免正文关键词污染后续页面。"""
    text = compact(value)
    if not text or len(text) > 80:
        return None
    if re.search(r"课程号\s*课程名称|课程代码\s*课程名称|course (?:code|no\.?|number).*course (?:name|title)", text, re.I):
        return "course"
    text = re.sub(r"^(?:[一二三四五六七八九十百]+|\d+)[、.．]\s*", "", text)
    if re.search(r"\d+(?:\.\d+)?\s*学分|学分[:：]?\s*\d", text):
        return None
    if not re.match(r"^(?:培养目标|培养要求|学习目标|学习成果|毕业要求|学位要求|评价|考核|考试|修读规定|学分要求|实践环节|实习|科研训练|课程设置|课程列表|课程体系|curriculum|courses?|modules?|assessment|graduation requirements?)", text, re.I):
        return None
    return classify_topic(text)


def course_values_from_text(text: str):
    """只识别行首明确课程号，避免把修读要求中的课程清单误记为评价。"""
    text = compact(text)
    match = re.match(r"^([A-Z]{2,5}\d{3,4}[A-Z]?)[\s:：-]+(.+)$", text)
    if not match:
        return None
    code, name = match.group(1), compact(match.group(2))
    credit = None
    credit_match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:A\.?U\.?s?|credits?|units?|学分)(?!\w)\s*[\])）]?\s*$", name, re.I)
    if credit_match:
        credit = credit_match.group(1)
        name = name[:credit_match.start()].rstrip(" ([（-")
    if len(name) < 2 or not re.search(r"[\u4e00-\u9fffA-Za-z]", name):
        return None
    values = {"课程代码": code, "课程名称": name}
    if credit:
        values["学分"] = credit
    return values


def looks_like_evaluation(text: str):
    return bool(re.search(
        r"要求|标准|考核|考试|评分|评审|学分|毕业|学位|必修|选修|修读|总计|合计|"
        r"assessment|requirements?|criteria|examinations?|graduation|grading|marked?|marks?|"
        r"grade|credits?|compulsory|elective|\bA\.?U\.?s?\b",
        compact(text), re.I))


def looks_like_course_description(text: str):
    text = compact(text)
    return len(text) >= 30 and bool(re.search(
        r"本课程|该课程|课程介绍|课程探讨|课程首先|课程旨在|"
        r"^this course|^the course|\bcourse (?:introduces|covers|explores|begins|provides|examines|aims)|"
        r"goal of this course|purpose of this course|course is to",
        text, re.I))


def looks_like_project(text: str):
    text = compact(text)
    if len(text) < 8 or generic_heading(text):
        return False
    if re.search(r"项目组成员|项目组宗旨|团队组成|合作伙伴|合作机构", text) and len(text) < 100:
        return False
    funded = re.search(r"基金|资助|立项|grant|funded|funding|EPSRC|UKRI|NSF|ERC|Innovate UK|AQA", text, re.I)
    project_word = re.search(r"项目|课题|project|programme|fellowship", text, re.I)
    if funded and (year_of(text) or project_word or re.search(r"研究|课题|research", text, re.I)):
        return True
    if re.search(r"立项", text) and len(text) <= 600:
        return True
    if year_of(text) and project_word and len(text) <= 600:
        return True
    if year_of(text) and len(text) <= 500 and re.search(r"研究中心|科学院|大学|图书馆|出版社|University|Center|Centre", text, re.I):
        return True
    return bool(len(text) <= 240 and re.search(r"研究项目|研究课题", text) and not re.search(r"简介|说明|成员|宗旨", text))


def looks_like_output(text: str):
    text = compact(text)
    if len(text) < 4 or generic_heading(text):
        return False
    without_urls = compact(URL_RE.sub("", text)).strip(" ，。；、:：[]()（）")
    if extract_urls(text) and len(without_urls) < 20:
        return False
    if len(text) < 20 and re.search(r"示意图|框架图|流程图|架构图|截图|照片", text):
        return False
    strong = re.search(r"10\.\d{4,9}/|(?:19|20)\d{2}|论文|发表|期刊|会议|专利|软著|软件|开源|著作|专著|出版社|奖项|奖励|publication|paper|journal|conference|proceedings|patent|software|github|award|book|doi|isbn|模型|数据集|系统|平台", text, re.I)
    if strong:
        return True
    return bool(len(text) >= 30 and re.search(r"提出|研发|开源|发布|构建|开发", text))


def person_name(value: str):
    text = strip_number(value).strip(" ,，")
    if not text or len(text) > 75 or generic_heading(text) or classify_topic(text):
        return None
    if re.search(r"实验室|研究中心|研究所|研究院|研究组|团队|大学|学院|平台|中心|成员|学生|课程|项目|专业|主任|委员会|faculty|staff|members?|students?|research|lab(?:oratory)?|centre|center|department|school", text, re.I):
        return None
    text = re.sub(r"^(prof(?:essor)?\.?|dr\.?|教授|副教授|讲师|助理教授|研究员)\s*", "", text, flags=re.I).strip()
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}(?:\s*[（(][^）)]{2,45}[）)])?", text):
        return text
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}", text):
        return text
    if re.fullmatch(r"[A-Z][A-Za-z.'-]+(?:\s+(?:de|van|von|der|da|di|[A-Z][A-Za-z.'-]+)){1,4}", text):
        return text
    return None


def tags(text: str):
    low = compact(text).lower()
    ai = "yes" if re.search(r"人工智能|机器学习|深度学习|自然语言处理|大模型|神经网络|artificial intelligence|machine learning|deep learning|\bai\b|\bnlp\b|\bllm\b", low) else "unknown"
    language = "yes" if re.search(r"语言|语言学|语音|语义|句法|翻译|语料库|linguistic|language|speech|translation|corpus", low) else "unknown"
    inter = "yes" if re.search(r"跨学科|交叉| interdisciplinary|multidisciplinary|cross-disciplinary", low) else "unknown"
    practice = "yes" if re.search(r"实习|实践|实验|项目|实训|capstone|internship|project|laboratory|\blab\b", low) else "unknown"
    return ai, language, inter, practice


def extract_urls(text: str):
    urls = []
    for match in URL_RE.finditer(text or ""):
        raw = match.group(0)
        url = raw.rstrip(".,;，。；、")
        try:
            host = (urlsplit(url).hostname or "").lower()
        except ValueError:
            continue
        if not host or host in SEARCH_HOSTS or (host.endswith("bing.com") and "/search" in url):
            continue
        if url not in urls:
            urls.append(url)
    return urls


def year_of(text: str):
    years = [int(x) for x in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text or "")]
    return years[0] if years else None


def number_of(text):
    if text is None:
        return None
    m = re.search(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", compact(text))
    return float(m.group(1)) if m else None


def output_type(topic_text: str, text: str = ""):
    value = (topic_text + " " + text).lower()
    if re.search(r"专利|patent", value): return "patent"
    if re.search(r"软著|software copyright", value): return "software_copyright"
    if re.search(r"数据集|dataset", value): return "dataset"
    if re.search(r"模型|model", value): return "model"
    if re.search(r"软件|开源|software|github", value): return "software"
    if re.search(r"书籍|著作|专著|book", value): return "book"
    if re.search(r"奖项|奖励|荣誉|award|prize", value): return "award"
    if re.search(r"报告|演讲|talk|presentation|keynote", value): return "talk"
    if re.search(r"论文|出版物|发表|paper|publication|journal|conference|proceedings|doi", value): return "paper"
    return "other"


def student_type(path: str, text: str):
    value = (path + " " + text).lower()
    if re.search(r"竞赛|比赛|competition|contest", value): return "competition"
    if re.search(r"升学|深造|攻读|further study|graduate school|ph\.?d\.", value): return "further_study"
    if re.search(r"就业|工作|任职|就职|employment|career|position", value): return "employment"
    if re.search(r"校友|毕业生|前成员|alumni|former|graduates?", value): return "alumni"
    if re.search(r"论文|软件|成果|获奖|publication|software|achievement", value): return "project_output"
    if re.search(r"科研|项目|研究|research|project", value): return "student_research"
    return "group_development"


def docx_school(path: Path):
    return re.sub(r"-2\.0$", "", path.stem)


def xml_text(node):
    return compact("".join(node.xpath(".//w:t/text()", namespaces=W)))


def parse_docx(path: Path, ocr_by_key):
    blocks = []
    with ZipFile(path) as z:
        doc = etree.fromstring(z.read("word/document.xml"))
        styles = {}
        if "word/styles.xml" in z.namelist():
            st = etree.fromstring(z.read("word/styles.xml"))
            for style in st.xpath("//w:style", namespaces=W):
                sid = style.get(f"{{{W['w']}}}styleId")
                name = style.find("w:name", W)
                styles[sid] = name.get(f"{{{W['w']}}}val") if name is not None else sid
        rels = {}
        if "word/_rels/document.xml.rels" in z.namelist():
            rr = etree.fromstring(z.read("word/_rels/document.xml.rels"))
            rels = {x.get("Id"): x.get("Target") for x in rr}

        def images_of(node):
            result = []
            for blip in node.xpath(".//a:blip[@r:embed]", namespaces=W):
                rid = blip.get(f"{{{W['r']}}}embed")
                target = rels.get(rid)
                if not target:
                    continue
                media = "word/" + target.lstrip("/") if not target.startswith("word/") else target
                media = str(Path(media))
                alts = []
                for dp in node.xpath(".//wp:docPr", namespaces=W):
                    alts.append({"name": dp.get("name"), "description": dp.get("descr"), "title": dp.get("title")})
                key = (str(path.relative_to(ROOT)), media)
                result.append({"media": media, "alt": alts[:3], "ocr": ocr_by_key.get(key, {})})
            return result

        def links_of(node):
            links = []
            for link in node.xpath(".//w:hyperlink", namespaces=W):
                rid = link.get(f"{{{W['r']}}}id")
                target = rels.get(rid)
                if target and target not in ("../NULL", "NULL"):
                    links.append({"text": xml_text(link), "target": target})
            return links

        body = doc.find("w:body", W)
        pno = table_index = 0
        for child in body:
            tag = etree.QName(child).localname
            if tag == "p":
                pno += 1
                text = xml_text(child)
                ps = child.find("w:pPr/w:pStyle", W)
                sid = ps.get(f"{{{W['w']}}}val") if ps is not None else None
                style = styles.get(sid, sid)
                if str(style or "").lower().startswith("toc"):
                    continue
                outline = child.find("w:pPr/w:outlineLvl", W)
                outline_level = int(outline.get(f"{{{W['w']}}}val")) + 1 if outline is not None else None
                images = images_of(child)
                if text:
                    blocks.append({"type": "p", "text": text, "style": style, "pno": pno,
                                   "outline_level": outline_level, "links": links_of(child), "images": images})
                elif images:
                    blocks.append({"type": "p", "text": "", "style": style, "pno": pno,
                                   "outline_level": outline_level, "links": [], "images": images})
            elif tag == "tbl":
                table_index += 1
                rows = []
                for tr in child.findall("w:tr", W):
                    cells = []
                    for tc in tr.findall("w:tc", W):
                        texts = [compact("".join(p.xpath(".//w:t/text()", namespaces=W)))
                                 for p in tc.findall(".//w:p", W)]
                        cells.append("\n".join(x for x in texts if x))
                    rows.append(cells)
                blocks.append({"type": "table", "rows": rows, "table_index": table_index,
                               "images": images_of(child), "links": links_of(child)})
        # Footnotes and endnotes are retained after the body with explicit locators.
        for part, label in (("word/footnotes.xml", "脚注"), ("word/endnotes.xml", "尾注")):
            if part not in z.namelist():
                continue
            root = etree.fromstring(z.read(part))
            for note in root:
                nid = note.get(f"{{{W['w']}}}id")
                if nid is not None and int(nid) < 0:
                    continue
                text = xml_text(note)
                if text:
                    pno += 1
                    blocks.append({"type": "p", "text": text, "style": label, "pno": pno,
                                   "outline_level": None, "links": links_of(note), "images": images_of(note)})
    return blocks


COURSE_NAME = {"课程名称", "课程名", "科目名称", "课程", "coursename", "coursetitle", "modulename", "moduletitle", "titleofcourse"}
COURSE_CODE = {"课程代码", "课程号", "课号", "课程编号", "科目编号", "coursecode", "courseno", "coursenumber", "modulecode", "code"}
CREDIT = {"学分", "学分数", "学分ects", "credits", "credit", "ects", "units", "unit"}
REQUIRED = {"课程性质", "修读性质", "必修选修", "必修/选修", "课程属性", "requirement", "compulsory/elective", "compulsoryorelective", "status"}
SEMESTER = {"学期", "推荐学期", "开课学期", "选课学期", "开课时间", "开课时间春/秋/夏", "semester", "term", "year/semester"}
MODULE = {"课程模块", "模块", "课程类别", "课程类型", "module", "coursemodule", "coursetype", "category"}
HOURS = {"总学时", "学时", "课时", "lecturehours", "contacthours", "hours"}
PRACTICE_HOURS = {"实践学时", "实践总学时", "实验学时", "practicalhours", "labhours"}
NAME_HEADERS = {"姓名", "教师姓名", "学生姓名", "成员姓名", "name", "fullname", "studentname", "facultyname", "membername"}
TITLE_HEADERS = {"职称", "职务", "岗位", "头衔", "title", "position", "role", "roletitle"}
RESEARCH_HEADERS = {"研究方向", "研究领域", "研究兴趣", "researchdirection", "researchdirections", "researchinterests", "researchareas"}
UNIT_HEADERS = {"单位", "院系", "所属单位", "所属机构", "团队", "机构", "organization", "unit", "department", "school", "affiliation"}
HOMEPAGE_HEADERS = {"个人主页", "主页", "网址", "homepage", "website", "url", "profile"}
PROJECT_HEADERS = {"项目名称", "课题名称", "项目", "课题", "projectname", "projecttitle", "researchproject"}
OUTPUT_HEADERS = {"成果名称", "论文题目", "论文名称", "专利名称", "出版物", "题目", "title", "outputtitle", "publicationtitle"}
PROGRAM_HEADERS = {"专业名称", "项目名称", "培养项目", "专业", "programname", "program", "degreename"}


def header_key(value):
    return re.sub(r"[\s（）()\-—–_：:。.,，/]+", "", compact(value).lower())


def header_matches(key, keys):
    if key in keys:
        return True
    # 保留原表头，同时兼容“课程名称（中文）”“姓名（英文）”等限定列。
    aliases = [x for x in keys if len(x) >= 4 and re.search(r"[\u4e00-\u9fff]", x)]
    if any(key.startswith(x) and len(key) <= len(x) + 12 for x in aliases):
        return True
    if keys & COURSE_NAME and (key.startswith(("课程名称", "课程名", "科目名称")) or
                               key.startswith(("coursename", "coursetitle", "modulename", "moduletitle"))):
        return True
    if keys & NAME_HEADERS and key.startswith(("姓名", "教师姓名", "学生姓名", "成员姓名")):
        return True
    if keys & CREDIT and key.startswith("学分"):
        return True
    return False


def has_header(values, keys):
    return any(header_matches(k, keys) for k in values)


def choose_header(rows):
    best = (None, -1, 0)
    identity_headers = COURSE_NAME | COURSE_CODE | NAME_HEADERS | PROJECT_HEADERS | OUTPUT_HEADERS | PROGRAM_HEADERS
    for idx, row in enumerate(rows[:6]):
        keys = [header_key(c) for c in row]
        score = sum(header_matches(k, identity_headers) for k in keys)
        if any(header_matches(k, COURSE_NAME) for k in keys):
            score += 3
        if any(header_matches(k, NAME_HEADERS) for k in keys):
            score += 2
        if score > best[2]:
            best = (idx, keys, score)
    return best if best[0] is not None and best[2] >= 2 else (None, [], 0)


def values_for(headers, row):
    result = defaultdict(list)
    for idx, key in enumerate(headers):
        if idx < len(row) and compact(row[idx]):
            result[key].append(compact(row[idx]))
    return {k: "\n".join(v) for k, v in result.items()}


def first_value(values, keys):
    for key in keys:
        if values.get(key):
            return values[key]
    candidates = [(k, v) for k, v in values.items() if v and header_matches(k, keys)]
    if keys is COURSE_NAME:
        candidates.sort(key=lambda item: ("英文" in item[0] or "english" in item[0], item[0]))
    return candidates[0][1] if candidates else None


class SchoolImporter:
    def __init__(self, con, uid, school):
        self.con = con
        self.uid = uid
        self.school = school
        self.batch_id = f"BFULL_{uid}"
        self.counters = defaultdict(int)
        self.frag = {}
        self.link_keys = set()
        self.new_records = defaultdict(list)
        self.used_fragments = set()
        self.stats = Counter()
        self.current_level = None
        self.current_program = None
        self.current_course = None
        self.current_program_level = None
        self.current_org = None
        self.current_org_level = None
        self.current_faculty = None
        self.current_faculty_level = None
        self.current_student = None
        self.current_unit = None
        self.topic = None
        self.section = None
        self.main_section_level = None
        self.stack = []
        self.module = None
        self.pdf_topic = None
        self.current_output = None
        self.current_output_context = None
        self.existing = {}
        self.load_existing()

    def load_existing(self):
        self.existing["program"] = {(norm(r[1]), r[2]): r[0] for r in self.con.execute(
            "SELECT program_id, program_name_cn, level FROM programs WHERE university_id=?", (self.uid,))}
        self.existing["course_code"] = {r[1]: r[0] for r in self.con.execute(
            "SELECT course_id, course_code FROM courses WHERE university_id=? AND course_code IS NOT NULL", (self.uid,))}
        self.existing["faculty"] = {norm(r[1]): r[0] for r in self.con.execute(
            "SELECT faculty_id, name FROM faculty WHERE university_id=?", (self.uid,))}
        self.existing["org"] = {norm(r[1]): r[0] for r in self.con.execute(
            "SELECT organization_id, name FROM organizations WHERE university_id=?", (self.uid,))}
        self.existing["pc"] = {tuple(r) for r in self.con.execute(
            """SELECT program_id, course_id, coalesce(module,''), coalesce(stage,''), coalesce(semester,''),
                      coalesce(academic_year,''), coalesce(required_elective,'')
               FROM program_course pc JOIN programs p USING(program_id) WHERE p.university_id=?""", (self.uid,))}
        self.existing["output_doi"] = {r[1].lower(): r[0] for r in self.con.execute(
            "SELECT output_id, doi FROM research_outputs WHERE university_id=? AND doi IS NOT NULL", (self.uid,))}
        self.existing["fo"] = {(r[1], r[2], r[3] or "", r[4] or ""): r[0] for r in self.con.execute(
            """SELECT fo.faculty_organization_id,fo.faculty_id,fo.organization_id,fo.role_title,fo.start_date
               FROM faculty_organization fo JOIN faculty f USING(faculty_id) WHERE f.university_id=?""", (self.uid,))}

    def next_id(self, table):
        self.counters[table] += 1
        if table in ("source_links", "review_issues"):
            return f"{PREFIX[table]}_{self.uid}_{self.counters[table]:07d}"
        if table == "sources":
            return f"{PREFIX[table]}_{self.uid}_{self.counters[table]:05d}"
        return f"{PREFIX[table]}_{self.uid}_{self.counters[table]:06d}"

    def insert(self, table, values):
        values = dict(values)
        values.setdefault("created_at", NOW)
        if table not in ("source_links", "review_issues", "raw_fragments", "import_batches"):
            values.setdefault("updated_at", NOW)
        if "review_status" in [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]:
            values.setdefault("review_status", "draft")
        cols = list(values)
        self.con.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                         [values[c] for c in cols])
        pk = TABLE_PK.get(table)
        if pk and values.get(pk) and not str(values[pk]).startswith(("P00", "C00", "F00", "O00")):
            self.new_records[table].append(values[pk])
        self.stats[table] += 1
        return values.get(pk)

    def add_issue(self, fragment_id, field_name, issue_type, severity, description, action,
                  entity_type="universities", entity_id=None):
        issue_id = self.next_id("review_issues")
        self.insert("review_issues", {
            "issue_id": issue_id, "batch_id": self.batch_id, "university_id": self.uid,
            "entity_type": entity_type, "entity_id": entity_id or self.uid, "fragment_id": fragment_id,
            "field_name": field_name, "issue_type": issue_type, "severity": severity,
            "description": description, "suggested_action": action, "status": "open",
            "resolution_note": None, "created_at": NOW, "resolved_at": None,
        })
        if fragment_id:
            self.con.execute("UPDATE raw_fragments SET disposition='issue_created', disposition_note=? WHERE fragment_id=?",
                             (description, fragment_id))
        return issue_id

    def add_fragment(self, attachment_id, content_type, text, *, heading_level=None, heading_text=None,
                     heading_path=None, content_json=None, table_index=None, row_index=None,
                     locator=None, confidence=0.96):
        row = self.con.execute("SELECT source_id FROM attachments WHERE attachment_id=?", (attachment_id,)).fetchone()
        seq = self.counters[f"frag_{attachment_id}"] + 1
        self.counters[f"frag_{attachment_id}"] = seq
        fragment_id = f"FR_{attachment_id}_{seq:07d}"
        parent = self.stack[-1][2] if self.stack else None
        program_hint = self.con.execute("SELECT program_name_cn FROM programs WHERE program_id=?",
                                        (self.current_program,)).fetchone() if self.current_program else None
        values = {
            "fragment_id": fragment_id, "batch_id": self.batch_id, "source_id": row[0] if row else None,
            "attachment_id": attachment_id, "university_id": self.uid, "parent_fragment_id": parent,
            "sequence_no": seq, "content_type": content_type, "heading_level": heading_level,
            "heading_text": heading_text, "heading_path": heading_path,
            "level_hint": self.current_level, "program_hint": program_hint[0] if program_hint else None,
            "content_text": text if text else "[空白／无文本]", "content_json": json.dumps(content_json, ensure_ascii=False) if content_json is not None else None,
            "table_index": table_index, "row_index": row_index, "locator": locator,
            "parse_confidence": confidence, "disposition": "unprocessed", "disposition_note": None,
            "review_status": "draft", "created_at": NOW,
        }
        self.insert("raw_fragments", values)
        self.frag[fragment_id] = values
        return fragment_id

    def link(self, entity_type, entity_id, fragment_id, relation="compiled_origin", note=None, dimension=None):
        if not fragment_id or not entity_id:
            return
        f = self.frag[fragment_id]
        key = (entity_type, entity_id, f["source_id"], f["attachment_id"], fragment_id, relation, f["locator"] or "")
        if key in self.link_keys:
            return
        self.link_keys.add(key)
        link_id = self.next_id("source_links")
        quote = f["content_text"][:1600]
        self.insert("source_links", {
            "link_id": link_id, "source_id": f["source_id"], "attachment_id": f["attachment_id"],
            "fragment_id": fragment_id, "entity_type": entity_type, "entity_id": entity_id,
            "dimension": dimension or DIM[entity_type], "relation_type": relation,
            "locator": f["locator"], "evidence_quote": quote, "is_primary": 1 if relation == "compiled_origin" else 0,
            "note": note or "原始附件定位证据；不等于官方网页已核验。", "created_at": NOW,
        })
        self.used_fragments.add(fragment_id)
        self.con.execute("UPDATE raw_fragments SET disposition='mapped', disposition_note=? WHERE fragment_id=?",
                         (f"已形成 {entity_type}/{entity_id} 的证据关系。", fragment_id))

    def raw_only(self, fragment_id, note="保留原文和定位；未形成可可靠独立业务字段。"):
        if not fragment_id or fragment_id in self.used_fragments:
            return
        self.con.execute("UPDATE raw_fragments SET disposition='raw_only', disposition_note=? WHERE fragment_id=?",
                         (note, fragment_id))

    def current_entity(self):
        if self.section == "academic" and self.current_program:
            return "programs", self.current_program
        if self.section == "organizations" and self.current_org:
            return "organizations", self.current_org
        if self.section == "faculty" and self.current_faculty:
            return "faculty", self.current_faculty
        return "universities", self.uid

    def update_stack(self, level, text, fid):
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append((level, text, fid))

    def heading_path(self):
        return " > ".join(x[1] for x in self.stack)

    def add_program(self, name, fid, level=None, parent=None, raw=None, host=None, kind=None):
        name = strip_number(name)
        if not name or len(name) > 240:
            return None
        level = level or self.current_level or "待核验"
        key = (norm(name), level)
        pid = self.existing["program"].get(key)
        if pid:
            self.link("programs", pid, fid)
            return pid
        low = name.lower()
        if kind is None:
            if re.search(r"辅修|minor|speciali[sz]ation|方向|stream|track", low):
                kind = "specialization"
            elif re.search(r"夏令营|短期|暑校|summer school|short", low):
                kind = "short_program"
            elif re.search(r"fellowship|奖学金", low):
                kind = "fellowship"
            elif re.search(r"研究组|科研团队|research group|lab(?:oratory)?", low):
                kind = "research_group"
            elif level in ("本科", "硕士", "博士", "硕博", "本研贯通") and not re.search(r"项目|project", low):
                kind = "degree_program"
            else:
                kind = "other"
        formal = int(kind == "degree_program")
        degree = None
        m = re.search(r"(理学学士|文学学士|工学学士|理学硕士|文学硕士|工学硕士|哲学博士|学士|硕士|博士)", name)
        if formal and m:
            degree = m.group(1)
        if not formal:
            degree = "不适用"
        ai, lang, inter, _ = tags(name)
        pid = self.next_id("programs")
        self.insert("programs", {
            "program_id": pid, "university_id": self.uid, "parent_program_id": parent,
            "host_organization_id": host, "program_kind": kind, "is_formal_degree": formal,
            "level": level, "level_raw": level, "program_name_cn": name, "program_name_en": name if not re.search(r"[\u4e00-\u9fff]", name) else None,
            "degree": degree, "host_unit_text": self.current_unit, "duration": None,
            "language_of_instruction": None, "entry_level": None, "admission_summary": None,
            "positioning": None, "program_size": None, "sequence_no": self.counters["programs"],
            "raw_text": raw or self.frag[fid]["content_text"], "review_status": "draft",
        })
        self.existing["program"][key] = pid
        self.link("programs", pid, fid, note=f"按标题和明确培养层次建立 {kind}；不是官方核验结论。")
        return pid

    def add_objective(self, text, fid, program=None, scope=None):
        program = program if program is not None else self.current_program
        scope = scope or ("program" if program else "university")
        oid = self.next_id("objectives")
        self.insert("objectives", {
            "objective_id": oid, "university_id": self.uid, "program_id": program,
            "scope_type": scope, "dimension": "培养目标", "description": text,
            "sequence_no": self.counters["objectives"], "raw_text": self.frag[fid]["content_text"],
            "review_status": "draft",
        })
        self.link("objectives", oid, fid)
        return oid

    def add_practice(self, text, fid, name=None, program=None):
        program = program if program is not None else self.current_program
        pid = self.next_id("practice")
        self.insert("practice", {
            "practice_id": pid, "university_id": self.uid, "program_id": program,
            "scope_type": "program" if program else "university", "practice_type": "实践／科研训练",
            "name": strip_number(name or self.stack[-1][1] if self.stack else "实践环节")[:240],
            "duration": None, "credits": None, "credit_system": None, "content": text,
            "assessment": None, "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
        })
        self.link("practice", pid, fid)
        return pid

    def add_evaluation(self, text, fid, program=None):
        program = program if program is not None else self.current_program
        eid = self.next_id("evaluation")
        self.insert("evaluation", {
            "evaluation_id": eid, "university_id": self.uid, "program_id": program,
            "scope_type": "program" if program else "university", "evaluation_type": "培养／毕业／考核要求",
            "method": text, "criteria": text if re.search(r"要求|标准|学分|criteria|requirement", text, re.I) else None,
            "weight": None, "output": None, "raw_text": self.frag[fid]["content_text"],
            "review_status": "draft",
        })
        self.link("evaluation", eid, fid)
        return eid

    def add_course(self, values, fid, raw_row=None, program=None):
        name = first_value(values, COURSE_NAME)
        if not name or len(name) < 1 or header_matches(header_key(name), COURSE_NAME):
            return None
        name = compact(name)
        if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", name):
            return None
        if len(name) > 500 or name in STOP_CONTENT:
            return None
        code = first_value(values, COURSE_CODE)
        code = compact(code).strip() if code else None
        if code and not re.search(r"[A-Za-z0-9]", code):
            code = None
        cid = self.existing["course_code"].get(code) if code else None
        ai, lang, inter, practice = tags(name + " " + (raw_row or ""))
        if not cid:
            cid = self.next_id("courses")
            self.insert("courses", {
                "course_id": cid, "university_id": self.uid, "course_code": code,
                "course_name": name, "course_name_raw": name,
                "course_name_en": name if not re.search(r"[\u4e00-\u9fff]", name) else None,
                "course_name_zh": name if re.search(r"[\u4e00-\u9fff]", name) else None,
                "language": "中文" if re.search(r"[\u4e00-\u9fff]", name) else "英文／其他",
                "description": None, "ai_tag": ai, "language_tag": lang, "practice_tag": practice,
                "raw_text": raw_row or self.frag[fid]["content_text"], "review_status": "draft",
            })
            if code:
                self.existing["course_code"][code] = cid
        self.link("courses", cid, fid)
        program = program if program is not None else self.current_program
        if program:
            module = first_value(values, MODULE) or self.module
            required = first_value(values, REQUIRED)
            semester = first_value(values, SEMESTER)
            credits = number_of(first_value(values, CREDIT))
            key = (program, cid, module or "", "", semester or "", "", required or "")
            if key not in self.existing["pc"]:
                pcid = self.next_id("program_course")
                self.insert("program_course", {
                    "program_course_id": pcid, "program_id": program, "course_id": cid,
                    "module": module, "stage": None, "semester": semester, "academic_year": None,
                    "required_elective": required, "credits": credits,
                    "credit_system": "ECTS" if "ects" in compact(values).lower() else None,
                    "lecture_hours": first_value(values, HOURS),
                    "directed_study_hours": None, "practical_hours": first_value(values, PRACTICE_HOURS),
                    "relation_note": None, "raw_text": raw_row or self.frag[fid]["content_text"],
                    "review_status": "draft",
                })
                self.existing["pc"].add(key)
                self.link("program_course", pcid, fid)
        self.current_course = cid
        return cid

    def add_course_description(self, text, fid):
        if not self.current_course or not looks_like_course_description(text):
            return False
        cid = self.current_course
        if cid in self.new_records["courses"]:
            old = self.con.execute("SELECT description FROM courses WHERE course_id=?", (cid,)).fetchone()[0]
            if not old or text not in old:
                self.con.execute("UPDATE courses SET description=?,updated_at=? WHERE course_id=?",
                                 (compact((old or "") + "\n" + text), NOW, cid))
        self.link("courses", cid, fid, note="课程号后续的课程简介；未改写原课程名称。")
        return True

    def add_org(self, name, fid, parent_text=None):
        name = strip_number(name)
        if not name or len(name) > 240 or generic_heading(name):
            return None
        key = norm(name)
        oid = self.existing["org"].get(key)
        if oid:
            self.link("organizations", oid, fid)
            return oid
        low = name.lower()
        if re.search(r"实验室|laboratory|\blab\b", low): org_type = "实验室／研究组"
        elif re.search(r"研究所|institute", low): org_type = "研究所"
        elif re.search(r"中心|centre|center", low): org_type = "研究中心"
        elif re.search(r"联盟|alliance", low): org_type = "联盟"
        else: org_type = "相关科研机构"
        ai, lang, inter, _ = tags(name)
        oid = self.next_id("organizations")
        self.insert("organizations", {
            "organization_id": oid, "university_id": self.uid, "parent_organization_id": None,
            "parent_org_text": parent_text or self.current_unit, "name": name,
            "name_en": name if not re.search(r"[\u4e00-\u9fff]", name) else None,
            "org_type": org_type, "research_directions": None, "ai_related": ai,
            "language_related": lang, "interdisciplinary": inter, "description": None,
            "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
        })
        self.existing["org"][key] = oid
        self.link("organizations", oid, fid)
        return oid

    def add_faculty(self, name, fid, values=None):
        values = values or {}
        name = strip_number(name)
        if not name or len(name) > 160:
            return None
        key = norm(name)
        fid_entity = self.existing["faculty"].get(key)
        research = first_value(values, RESEARCH_HEADERS)
        title = first_value(values, TITLE_HEADERS)
        unit = first_value(values, UNIT_HEADERS) or self.current_unit
        homepage = first_value(values, HOMEPAGE_HEADERS)
        if homepage:
            urls = extract_urls(homepage)
            homepage = urls[0] if urls else None
        ai, lang, inter, _ = tags((research or "") + " " + name)
        if not fid_entity:
            fid_entity = self.next_id("faculty")
            self.insert("faculty", {
                "faculty_id": fid_entity, "university_id": self.uid, "name": name, "name_raw": name,
                "primary_unit_text": unit, "title": title, "research_direction": research,
                "homepage_url": homepage, "orcid": None, "biography": None,
                "ai_tag": ai, "language_tag": lang, "interdisciplinary_tag": inter,
                "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
            })
            self.existing["faculty"][key] = fid_entity
        self.link("faculty", fid_entity, fid)
        if self.current_org:
            self.link_faculty_org(fid_entity, self.current_org, fid, unit=unit, role=title)
        return fid_entity

    def link_faculty_org(self, faculty_id, org_id, fid, unit=None, role=None):
        # 与ux_faculty_organization_dedup完全一致：开始日期为空时也按空串去重。
        key = (faculty_id, org_id, role or "", "")
        foid = self.existing["fo"].get(key)
        if foid:
            self.link("faculty_organization", foid, fid, note="复用既有教师－平台关系并追加证据。")
            return foid
        foid = self.next_id("faculty_organization")
        self.insert("faculty_organization", {
            "faculty_organization_id": foid, "faculty_id": faculty_id, "organization_id": org_id,
            "role_title": role, "unit_text": unit or self.current_unit, "is_primary": None,
            "start_date": None, "end_date": None, "raw_text": self.frag[fid]["content_text"],
            "review_status": "draft",
        })
        self.existing["fo"][key] = foid
        self.link("faculty_organization", foid, fid)
        return foid

    def add_research(self, text, fid, kind, values=None, heading=None, force=False):
        values = values or {}
        text = compact(text)
        if len(text) < 4 or text in STOP_CONTENT or (len(text) < 20 and extract_urls(text)):
            return None
        context = self.heading_path()
        if (kind == "output" and re.match(r"^(?:Research output|研究输出)\s*[:：]", text, re.I)
                and self.current_output and self.current_output_context == context):
            oid = self.current_output
            self.link("research_outputs", oid, fid, note="上一条成果的类型／同行评议说明，不另建成果。")
            if oid in self.new_records["research_outputs"]:
                old = self.con.execute("SELECT description FROM research_outputs WHERE output_id=?", (oid,)).fetchone()[0]
                self.con.execute("UPDATE research_outputs SET description=?,updated_at=? WHERE output_id=?",
                                 (compact((old or "") + "\n" + text), NOW, oid))
            return oid
        if not force and ((kind == "project" and not looks_like_project(text)) or
                          (kind == "output" and not looks_like_output(text))):
            return None
        if kind == "project":
            name = first_value(values, PROJECT_HEADERS) or heading or text
            name = strip_number(name)[:500]
            if generic_heading(name):
                return None
            rid = self.next_id("research_projects")
            self.insert("research_projects", {
                "project_id": rid, "university_id": self.uid, "project_name": name,
                "project_name_en": name if not re.search(r"[\u4e00-\u9fff]", name) else None,
                "project_type": "科研／研究课题", "funder": first_value(values, {"资助机构", "资助方", "funder", "fundingbody"}),
                "grant_number": first_value(values, {"项目编号", "课题编号", "grantnumber", "projectnumber"}),
                "start_date": first_value(values, {"开始时间", "起始年份", "startdate", "startyear"}),
                "end_date": first_value(values, {"结束时间", "结题时间", "enddate", "endyear"}),
                "status": first_value(values, {"状态", "项目状态", "status"}),
                "funding_amount": first_value(values, {"资助金额", "经费", "金额", "fundingamount"}),
                "description": text, "evaluation_result": None,
                "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
            })
            self.link("research_projects", rid, fid)
            if self.current_faculty or self.current_org:
                lid = self.next_id("research_project_links")
                self.insert("research_project_links", {
                    "project_link_id": lid, "project_id": rid,
                    "faculty_id": self.current_faculty if self.current_faculty else None,
                    "organization_id": None if self.current_faculty else self.current_org,
                    "program_id": None, "relation_role": "相关教师" if self.current_faculty else "承载平台",
                    "linked_name_raw": None, "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
                })
                self.link("research_project_links", lid, fid)
            return rid
        title = first_value(values, OUTPUT_HEADERS) or heading or text
        title = strip_number(title)[:1000]
        if generic_heading(title):
            return None
        doi_match = re.search(r"(10\.\d{4,9}/[^\s，。；]+)", text, re.I)
        doi = doi_match.group(1).rstrip(".,") if doi_match else None
        urls = extract_urls(text)
        oid = self.existing["output_doi"].get(doi.lower()) if doi else None
        if oid:
            self.link("research_outputs", oid, fid, note="DOI与既有成果一致，复用成果并追加原文证据。")
        else:
            oid = self.next_id("research_outputs")
            self.insert("research_outputs", {
                "output_id": oid, "university_id": self.uid, "output_type": output_type(context, title),
                "title": title, "authors_text": first_value(values, {"作者", "作者列表", "authors", "author"}),
                "publication_date": first_value(values, {"发表日期", "出版日期", "授权日期", "date", "publicationdate"}),
                "publication_year": year_of(text), "venue": first_value(values, {"期刊", "会议", "出版社", "venue", "journal", "conference"}),
                "volume_issue_pages": first_value(values, {"卷期页码", "页码", "volume", "pages"}),
                "doi": doi, "url": urls[0] if urls else None, "version": None, "license": None,
                "description": text, "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
            })
            if doi:
                self.existing["output_doi"][doi.lower()] = oid
            self.link("research_outputs", oid, fid)
        if self.current_faculty or self.current_org:
            lid = self.next_id("research_output_links")
            self.insert("research_output_links", {
                "output_link_id": lid, "output_id": oid,
                "faculty_id": self.current_faculty if self.current_faculty else None,
                "organization_id": None if self.current_faculty else self.current_org,
                "program_id": None, "relation_role": "相关教师" if self.current_faculty else "发布平台",
                "author_order": None, "linked_name_raw": None,
                "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
            })
            self.link("research_output_links", lid, fid)
        self.current_output = oid
        self.current_output_context = context
        return oid

    def add_student(self, text, fid, values=None, person=None):
        values = values or {}
        text = compact(text)
        if not text or text in STOP_CONTENT:
            return None
        person = person or first_value(values, NAME_HEADERS) or self.current_student
        if not person:
            match = re.match(r"^([\u4e00-\u9fff·]{2,4})\s*[，,：:]\s*(?:[^，,。；]{0,30})(?:本科生|硕士生|博士生|研究生|校友)", text)
            if match:
                person = match.group(1)
        path = self.heading_path()
        record_type = student_type(path, text)
        subject = "individual" if person else ("cohort" if re.search(r"届|年级|全体| cohort", text, re.I) else "group")
        sid = self.next_id("student_development")
        destination = text if record_type in ("further_study", "employment", "alumni") else None
        self.insert("student_development", {
            "development_id": sid, "university_id": self.uid, "program_id": self.current_program,
            "scope_type": "program" if self.current_program else "university",
            "organization_id": self.current_org, "faculty_id": self.current_faculty,
            "record_type": record_type, "subject_type": subject, "person_name_public": person,
            "student_status": first_value(values, {"身份", "学生状态", "status"}) or ("公开资料中的个人" if person else "群体"),
            "degree_level": first_value(values, {"层次", "学位", "年级", "degree", "degreelevel"}) or self.current_level,
            "study_period": first_value(values, {"就读时间", "时间段", "studyperiod", "period"}),
            "content": text, "achievement": text if record_type in ("project_output", "competition") else None,
            "destination_type": {"further_study": "升学", "employment": "就业"}.get(record_type, "其他" if record_type == "alumni" else None),
            "destination_text": destination, "destination_organization": None,
            "destination_role": None, "event_year": year_of(text),
            "raw_text": self.frag[fid]["content_text"], "review_status": "draft",
        })
        self.link("student_development", sid, fid)
        return sid

    def handle_heading(self, text, level, fid):
        self.current_course = None
        self.update_stack(level, text, fid)
        candidate_section = main_section(text)
        new_section = candidate_section if candidate_section and (
            self.main_section_level is None or level <= self.main_section_level) else None
        if new_section:
            self.section = new_section
            self.main_section_level = level
            self.current_program = self.current_org = self.current_faculty = self.current_student = None
            self.current_program_level = self.current_org_level = self.current_faculty_level = None
            self.current_level = None
            self.current_unit = None
            self.topic = None
            self.link("universities", self.uid, fid, dimension="university_overview",
                      note=f"全文章节定位：{new_section}。")
            if "学了与专业设置" in text:
                self.add_issue(fid, "heading_text", "source_typo", "low",
                               "原文主标题为“学了与专业设置”，按上下文识别为学科与专业设置；原文未改写。",
                               "人工复核原汇编标题笔误。")
            return
        if self.section is None:
            self.raw_only(fid, "学校标题或正文结构标题，保留层级。")
            return
        clean = strip_number(text)
        topic = classify_topic(clean)
        if self.section == "academic":
            lev = level_of(clean)
            if lev and len(clean) <= 35 and is_level_marker(clean, lev):
                self.current_level = lev
                self.current_program = None
                self.current_program_level = None
                self.topic = None
                self.raw_only(fid, f"培养层次结构标题：{lev}。")
                return
            is_program = False
            program_exception = bool(re.search(r"辅修|\bminor\b|speciali[sz]ation", clean, re.I))
            previous_text = self.stack[-2][1] if len(self.stack) >= 2 else ""
            previous_clean = strip_number(previous_text)
            structured_parent = bool(is_level_marker(previous_clean, level_of(previous_clean)) or
                                     classify_topic(previous_clean) == "admission")
            admission_program_parent = bool(re.search(r"招生专业|programs?|degrees?", previous_clean, re.I))
            named_under_admission = bool(admission_program_parent and topic == "admission" and
                                         not re.match(r"^(?:\d+[、.．]\s*)?(?:招生|入学|申请|报考)", clean))
            admission_named = re.match(r"^(?:\d+[、.．]\s*)?招生专业\s*[:：]\s*(.+)$", clean)
            organization_not_program = bool(re.search(r"研究所|研究中心|实验室|研究院|平台|中心", clean) and
                                            not re.search(r"专业|学士|硕士|博士|项目|辅修", clean))
            if admission_named:
                is_program = bool(self.current_level)
            elif not generic_heading(clean) and not organization_not_program and (not topic or program_exception or named_under_admission):
                if self.current_program is None:
                    is_program = bool(self.current_level and (structured_parent or
                        re.search(r"专业|学士|硕士|博士|项目|方向|辅修|program|degree|bachelor|master|ph\.?d|linguistic|computing|data science|artificial intelligence", clean, re.I)))
                elif self.current_program_level is not None and level <= self.current_program_level:
                    is_program = True
            if is_program:
                parent = self.current_program if self.current_program_level is not None and level > self.current_program_level else None
                program_name = admission_named.group(1) if admission_named else clean
                pid = self.add_program(program_name, fid, parent=parent)
                if pid:
                    self.current_program = pid
                    self.current_program_level = level
                    self.topic = None
                    self.module = None
                    return
            if topic:
                if self.current_program and self.current_program_level is not None and level <= self.current_program_level:
                    self.current_program = None
                    self.current_program_level = None
                self.topic = topic
            elif self.current_program and self.current_program_level is not None and level <= self.current_program_level:
                self.current_program = None
                self.current_program_level = None
                self.topic = topic
            self.raw_only(fid, "项目内栏目或课程模块标题，保留层级。")
            return
        if self.section == "organizations":
            org_word = re.search(r"实验室|研究中心|研究所|研究院|研究组|团队|联盟|平台|中心|网络|laboratory|\blab\b|centre|center|institute|alliance|network|research group|association|initiative", clean, re.I)
            is_org = bool(org_word and not generic_heading(clean) and not topic and not person_name(clean))
            same_or_higher = self.current_org_level is None or level <= self.current_org_level
            if is_org and (self.current_org is None or same_or_higher):
                oid = self.add_org(clean, fid)
                if oid:
                    self.current_org = oid
                    self.current_org_level = level
                    self.current_unit = clean
                    self.current_faculty = None
                    self.topic = None
                    return
            if not topic and not generic_heading(clean) and self.current_org and same_or_higher:
                # 同级的新研究领域／分类标题会结束上一平台上下文。
                self.current_org = None
                self.current_org_level = None
                self.current_unit = clean
            if generic_heading(clean) and not topic and len(clean) < 30:
                self.current_unit = clean
            if topic:
                self.topic = topic
            if self.current_org:
                self.link("organizations", self.current_org, fid)
            else:
                self.raw_only(fid, "科研平台／研究领域分类标题，保留层级；未把领域名称直接当作机构。")
            return
        if self.section == "faculty":
            pname = person_name(clean)
            if pname:
                # A matching organization heading is a unit, not a person.
                person = self.add_faculty(pname, fid)
                if person:
                    self.current_faculty = person
                    self.current_faculty_level = level
                    self.topic = None
                    return
            if not topic and not generic_heading(clean):
                self.current_unit = clean
                self.current_org = self.existing["org"].get(norm(clean), self.current_org)
                self.current_faculty = None
            if generic_heading(clean) and not topic and len(clean) < 45:
                self.current_unit = clean
            if topic:
                self.topic = topic
            if self.current_faculty:
                self.link("faculty", self.current_faculty, fid)
            else:
                self.raw_only(fid, "师资团队或职务分类标题，保留层级。")
            return
        if self.section == "student":
            self.topic = topic or self.topic
            matched_org = self.existing["org"].get(norm(clean))
            if matched_org:
                self.current_org = matched_org
                self.current_unit = clean
            pname = person_name(clean)
            if pname and not matched_org:
                self.current_student = pname
                self.link("universities", self.uid, fid, dimension="student_development",
                          note="公开学生／校友姓名所在标题；具体发展记录见后续原文。")
            else:
                if generic_heading(clean):
                    self.current_student = None
                self.raw_only(fid, "学生发展分组标题，保留层级。")
            return
        self.raw_only(fid)

    def handle_paragraph(self, text, fid):
        text = compact(text)
        if not text:
            self.raw_only(fid, "空段落或仅含图片的段落；图片另建片段。")
            return
        if self.section == "academic":
            course_values = course_values_from_text(text) if self.topic in ("course", "evaluation", "practice") else None
            if course_values:
                cid = self.add_course(course_values, fid, raw_row=text)
                if cid:
                    return
            if self.topic == "objective":
                self.current_course = None
                self.add_objective(text, fid)
            elif self.topic == "evaluation":
                if looks_like_evaluation(text):
                    self.current_course = None
                    self.add_evaluation(text, fid)
                elif self.add_course_description(text, fid):
                    return
                else:
                    self.current_course = None
                    self.raw_only(fid, "修读／评价栏目中的课程或说明性文字；缺乏明确评价特征，保留原文但未生成评价记录。")
            elif self.topic == "practice":
                if re.search(r"评分|评审|分值|得分|满分|\d+\s*分|assessment criteria|grading|marked?|marks?", text, re.I):
                    self.current_course = None
                    self.add_evaluation(text, fid)
                elif self.add_course_description(text, fid):
                    return
                elif looks_like_course_description(text):
                    self.current_course = None
                    self.raw_only(fid, "实践栏目中的课程简介；无法可靠关联课程号时仅保留原文，不生成实践记录。")
                else:
                    self.current_course = None
                    self.add_practice(text, fid)
            else:
                if self.topic == "course" and self.add_course_description(text, fid):
                    return
                self.current_course = None
                if self.current_program:
                    self.link("programs", self.current_program, fid)
                    fields = {}
                    if self.topic == "intro":
                        fields["positioning"] = text
                    elif self.topic == "admission":
                        fields["admission_summary"] = text
                    if self.topic in ("intro", "admission"):
                        row = self.con.execute("SELECT positioning, admission_summary FROM programs WHERE program_id=?",
                                               (self.current_program,)).fetchone()
                        updates = []
                        for field, value in fields.items():
                            old = row[0] if field == "positioning" else row[1]
                            if self.current_program in self.new_records["programs"]:
                                value = compact((old or "") + "\n" + value)
                                updates.append((field, value))
                        for field, value in updates:
                            self.con.execute(f"UPDATE programs SET {field}=?, updated_at=? WHERE program_id=?",
                                             (value, NOW, self.current_program))
                else:
                    self.raw_only(fid, "学校／层次层面的培养说明，未可靠归属到具体项目。")
            return
        if self.section in ("organizations", "faculty"):
            if self.topic == "project":
                rid = self.add_research(text, fid, "project")
                if not rid:
                    self.raw_only(fid, "科研栏目中的说明、成员或合作信息；缺乏独立项目特征，保留原文但未生成项目。")
            elif self.topic == "output":
                oid = self.add_research(text, fid, "output")
                if not oid:
                    self.raw_only(fid, "成果栏目中的说明、合作机构、纯链接或图注；未生成独立成果。")
            else:
                entity_type, entity_id = self.current_entity()
                if entity_type != "universities":
                    self.link(entity_type, entity_id, fid)
                    if self.topic in ("intro", "research_direction") and entity_id in self.new_records[entity_type]:
                        field = (("description" if entity_type == "organizations" else "biography")
                                 if self.topic == "intro" else
                                 ("research_directions" if entity_type == "organizations" else "research_direction"))
                        old = self.con.execute(f"SELECT {field} FROM {entity_type} WHERE {TABLE_PK[entity_type]}=?", (entity_id,)).fetchone()[0]
                        self.con.execute(f"UPDATE {entity_type} SET {field}=?, updated_at=? WHERE {TABLE_PK[entity_type]}=?",
                                         (compact((old or "") + "\n" + text), NOW, entity_id))
                else:
                    self.raw_only(fid, "科研机构／师资章节中尚无可可靠关联实体的说明。")
            return
        if self.section == "student":
            self.add_student(text, fid)
            return
        self.raw_only(fid)

    def handle_table(self, block, attachment_id):
        rows = block["rows"]
        if not rows:
            return
        # 模块分组只在本表内继承，避免跨表串用。
        self.module = None
        header_idx, headers, score = choose_header(rows)
        fids = []
        for ridx, row in enumerate(rows):
            text = " | ".join(compact(c) for c in row)
            fid = self.add_fragment(attachment_id, "table_row", text,
                                    heading_path=self.heading_path(),
                                    content_json={"cells": row, "header_row": header_idx + 1 if header_idx is not None else None,
                                                  "headers": headers if ridx == header_idx else None},
                                    table_index=block["table_index"], row_index=ridx + 1,
                                    locator=f"Word表{block['table_index']}第{ridx + 1}行")
            fids.append(fid)
        if header_idx is None:
            for fid in fids:
                entity_type, entity_id = self.current_entity()
                if entity_type != "universities":
                    self.link(entity_type, entity_id, fid, note="未识别标准表头；作为当前实体的原始表格证据保留。")
                else:
                    self.raw_only(fid, "未识别标准表头的表格行；完整保留。")
            return
        for ridx, row in enumerate(rows):
            fid = fids[ridx]
            if ridx <= header_idx:
                self.raw_only(fid, "表格标题／表头／说明行，完整保留。")
                continue
            values = values_for(headers, row)
            if not values:
                self.raw_only(fid, "空表格行。")
                continue
            raw = json.dumps({"headers": headers, "cells": row}, ensure_ascii=False)
            keys = set(values)
            if has_header(values, PROGRAM_HEADERS) and self.section == "academic" and not has_header(values, COURSE_NAME):
                name = first_value(values, PROGRAM_HEADERS)
                if name and not header_matches(header_key(name), PROGRAM_HEADERS):
                    self.add_program(name, fid, raw=raw)
                    self.current_program = self.existing["program"].get((norm(strip_number(name)), self.current_level or "待核验"), self.current_program)
                else:
                    self.raw_only(fid)
            elif has_header(values, COURSE_NAME):
                course_name = first_value(values, COURSE_NAME)
                module_row = bool(course_name and len(values) == 1 and not first_value(values, COURSE_CODE)
                                  and len(course_name) <= 100
                                  and re.search(r"模块|类别|必修|选修|通识|基础课|专业课|核心课|module|category|required|elective|core courses?", course_name, re.I))
                if module_row:
                    self.module = course_name
                    self.raw_only(fid, "课程分组／模块行，作为本表后续课程关系上下文。")
                else:
                    cid = self.add_course(values, fid, raw)
                    if not cid:
                        self.raw_only(fid, "课程表中的说明或续行，未作为独立课程。")
            elif self.section == "student":
                self.add_student(" | ".join(compact(c) for c in row if compact(c)), fid, values)
            elif self.section == "faculty" and has_header(values, NAME_HEADERS):
                name = first_value(values, NAME_HEADERS)
                faculty = self.add_faculty(name, fid, values)
                if faculty:
                    self.current_faculty = faculty
            elif self.topic == "project":
                self.add_research(" | ".join(compact(c) for c in row if compact(c)), fid, "project", values, force=True)
            elif self.topic == "output":
                self.add_research(" | ".join(compact(c) for c in row if compact(c)), fid, "output", values, force=True)
            elif self.topic == "objective":
                self.add_objective(" | ".join(compact(c) for c in row if compact(c)), fid)
            elif self.topic == "evaluation":
                text = " | ".join(compact(c) for c in row if compact(c))
                if looks_like_evaluation(text):
                    self.add_evaluation(text, fid)
                else:
                    self.raw_only(fid, "评价／修读栏目中的表格说明；缺乏明确评价特征，保留原文。")
            elif self.topic == "practice":
                text = " | ".join(compact(c) for c in row if compact(c))
                if re.search(r"评分|评审|分值|得分|满分|\d+\s*分|assessment criteria|grading|marked?|marks?", text, re.I):
                    self.add_evaluation(text, fid)
                else:
                    self.add_practice(text, fid)
            else:
                entity_type, entity_id = self.current_entity()
                if entity_type != "universities":
                    self.link(entity_type, entity_id, fid, note="当前实体的补充表格证据；未强行拆分字段。")
                else:
                    self.raw_only(fid, "未识别为标准业务表的表格行；完整保留。")

    def add_image_fragments(self, images, attachment_id, block_locator):
        for image in images:
            ocr = image.get("ocr") or {}
            text = ocr.get("ocr_text") or ""
            payload = {"media": image["media"], "alt": image["alt"], "ocr_status": ocr.get("ocr_status"),
                       "ocr_engine": "tesseract chi_sim+eng" if text else None,
                       "note": "OCR仅用于检索和回查，不直接生成事实字段。"}
            fid = self.add_fragment(attachment_id, "paragraph", "[图片OCR候选]\n" + text if text else "[图片／矢量对象，无可用OCR文本]",
                                    heading_path=self.heading_path(), content_json=payload,
                                    locator=f"{block_locator}；{image['media']}", confidence=0.45 if text else 0.2)
            self.raw_only(fid, "图片或嵌入对象图标已登记；OCR候选仅供回查，未直接作为事实入库。嵌入PDF另逐页解析。")

    def process_docx(self, path, attachment_id, ocr_by_key):
        self.section = None
        self.main_section_level = None
        self.stack = []
        self.current_program = self.current_org = self.current_faculty = self.current_student = None
        self.current_level = self.current_unit = self.topic = None
        for block in parse_docx(path, ocr_by_key):
            if block["type"] == "p":
                text = block["text"]
                match = HEADING_RE.match(text)
                if match:
                    level = len(match.group(1))
                    heading = compact(match.group(2))
                    fid = self.add_fragment(attachment_id, "heading", text, heading_level=level,
                                            heading_text=heading, heading_path=" > ".join(x[1] for x in self.stack + [(level, heading, None)]),
                                            content_json={"style": block["style"], "links": block["links"]},
                                            locator=f"Word段落{block['pno']}")
                    self.handle_heading(heading, level, fid)
                else:
                    fid = self.add_fragment(attachment_id, "paragraph", text, heading_path=self.heading_path(),
                                            content_json={"style": block["style"], "links": block["links"]},
                                            locator=f"Word段落{block['pno']}")
                    if text:
                        self.handle_paragraph(text, fid)
                    else:
                        self.raw_only(fid, "仅含图片的段落，图片另建片段。")
                locator = f"Word段落{block['pno']}"
            else:
                self.handle_table(block, attachment_id)
                locator = f"Word表{block['table_index']}"
            self.add_image_fragments(block.get("images") or [], attachment_id, locator)

    def infer_pdf_program(self, name, first_text, embedded=None):
        if "project-list-natural-language-processing" in name:
            return None
        clean = Path(name).stem
        clean = re.sub(r"__oleObject\d+$", "", clean)
        clean = re.sub(r"^.*?大学[-—]?", "", clean)
        clean = re.sub(r"^20\d{2}[-—]?", "", clean)
        clean = re.sub(r"handbook.*$|四年毕业计划[:：]|本科生专业[:：]|培养方案|课程设置|课程大纲|课程安排", "", clean, flags=re.I)
        clean = clean.strip(" -_—:：") or Path(name).stem
        lev = level_of(clean)
        if not lev:
            lev = next((label for pattern, label in LEVEL_WORDS
                        if re.search(pattern, first_text[:1600], re.I)), None)
        lev = lev or self.current_level or "待核验"
        if embedded and embedded.get("embedded_source_path"):
            source_path = embedded["embedded_source_path"]
            if "计算语言学硕士" in source_path:
                clean, lev = "计算语言学", "硕士"
        exact = self.existing["program"].get((norm(clean), lev))
        if exact:
            return exact
        candidates = []
        distinct_track = bool(re.search(r"图灵班|智班|方向|ACM|IEEE|致远|荣誉", clean, re.I))
        if not distinct_track:
            for (n, l), pid in self.existing["program"].items():
                if n and (n in norm(clean) or norm(clean) in n) and (l == lev or lev == "待核验" or l == "待核验"):
                    candidates.append(pid)
        if len(set(candidates)) == 1:
            return candidates[0]
        if re.search(r"handbook|毕业计划|培养方案|课程设置|课程大纲|课程安排|本科生专业|硕士|博士|学士", name, re.I):
            return self.add_program(clean, self.pdf_title_fragment, level=lev)
        return None

    def process_pdf(self, path, attachment_id, embedded=None):
        # PDF是独立附件：不得继承DOCX末尾的学生、教师或平台上下文。
        self.section = "academic"
        self.main_section_level = None
        self.stack = []
        self.current_program = self.current_org = self.current_faculty = self.current_student = None
        self.current_course = None
        self.current_program_level = self.current_org_level = self.current_faculty_level = None
        self.current_level = self.current_unit = self.topic = self.module = None
        self.pdf_topic = None
        doc = fitz.open(path)
        first_text = "\n".join(doc[i].get_text() for i in range(min(2, len(doc))))
        self.pdf_title_fragment = self.add_fragment(attachment_id, "caption", f"PDF附件：{path.name}",
                                                    heading_path=self.heading_path(),
                                                    content_json={"embedded": embedded} if embedded else None,
                                                    locator="PDF文件名与附件元数据")
        self.current_program = self.infer_pdf_program(path.name, first_text, embedded)
        if self.current_program:
            self.link("programs", self.current_program, self.pdf_title_fragment)
        else:
            self.raw_only(self.pdf_title_fragment, "PDF附件元数据；未从文件名可靠推断单一项目。")
        if "project-list-natural-language-processing" in path.name:
            self.process_kcl_pdf(doc, attachment_id)
            return
        self.pdf_topic = None
        for pno, page in enumerate(doc, 1):
            blocks = [compact(b[4]) for b in page.get_text("blocks") if compact(b[4])]
            if not blocks:
                fid = self.add_fragment(attachment_id, "pdf_text", "[空白页]", heading_path=self.heading_path(),
                                        locator=f"PDF第{pno}页", confidence=1.0)
                self.raw_only(fid, "经文本层和页面渲染检查为空白页。")
            page_fids = []
            for bno, text in enumerate(blocks, 1):
                fid = self.add_fragment(attachment_id, "pdf_text", text, heading_path=self.heading_path(),
                                        content_json={"page": pno, "block": bno}, locator=f"PDF第{pno}页文本块{bno}")
                page_fids.append(fid)
                first_line = compact(text.split("\n")[0])
                new_topic = pdf_topic(first_line)
                if new_topic:
                    self.pdf_topic = new_topic
                    self.current_course = None
                course_values = course_values_from_text(text) if len(text.splitlines()) == 1 else None
                if course_values and self.pdf_topic in ("course", "evaluation", "practice"):
                    cid = self.add_course(course_values, fid, raw_row=text, program=self.current_program)
                    if cid:
                        continue
                if self.pdf_topic == "objective" and len(text) > 20:
                    self.add_objective(text, fid, program=self.current_program)
                elif self.pdf_topic == "evaluation" and len(text) > 20:
                    if looks_like_evaluation(text):
                        self.add_evaluation(text, fid, program=self.current_program)
                    elif not self.add_course_description(text, fid):
                        self.raw_only(fid, "PDF修读／评价栏目中的说明或课程文字；未生成无明确评价特征的记录。")
                elif self.pdf_topic == "practice" and len(text) > 20:
                    if re.search(r"评分|评审|分值|得分|满分|\d+\s*分|assessment criteria|grading|marked?|marks?", text, re.I):
                        self.add_evaluation(text, fid, program=self.current_program)
                    else:
                        self.add_practice(text, fid, program=self.current_program)
                elif self.current_program:
                    self.link("programs", self.current_program, fid)
                else:
                    self.raw_only(fid, "PDF正文已按页和文本块保留；未可靠归属到具体业务实体。")
            try:
                tables = page.find_tables().tables
            except Exception:
                tables = []
            for tno, table in enumerate(tables, 1):
                rows = table.extract()
                if rows:
                    self.handle_table({"rows": rows, "table_index": pno * 100 + tno}, attachment_id)
                    start_seq = self.counters[f"frag_{attachment_id}"] - len(rows) + 1
                    for ridx in range(len(rows)):
                        fid = f"FR_{attachment_id}_{start_seq + ridx:07d}"
                        locator = f"PDF第{pno}页表{tno}第{ridx + 1}行"
                        self.con.execute("UPDATE raw_fragments SET locator=? WHERE fragment_id=?", (locator, fid))
                        self.con.execute("UPDATE source_links SET locator=? WHERE fragment_id=?", (locator, fid))
                        self.frag[fid]["locator"] = locator

    def process_kcl_pdf(self, doc, attachment_id):
        for pno, page in enumerate(doc, 1):
            text = page.get_text().strip()
            fid = self.add_fragment(attachment_id, "pdf_text", text or "[空白页]",
                                    heading_path="博士科研项目清单", locator=f"PDF第{pno}页")
            if pno < 3 or pno == len(doc) or not text:
                self.raw_only(fid, "项目清单说明、目录或空白页；完整保留。")
                continue
            lines = [compact(x) for x in text.splitlines() if compact(x)]
            title = lines[0] if lines else f"第{pno}页博士课题"
            supervisor = next((x for x in lines if x.lower().startswith("supervisor:")), None)
            rid = self.add_research(text, fid, "project", heading=title, force=True)
            if rid and supervisor:
                name = supervisor.split(":", 1)[1].strip()
                faculty = self.existing["faculty"].get(norm(name))
                lid = self.next_id("research_project_links")
                self.insert("research_project_links", {
                    "project_link_id": lid, "project_id": rid, "faculty_id": faculty,
                    "organization_id": None if faculty else self.current_org, "program_id": None,
                    "relation_role": "Supervisor／导师", "linked_name_raw": None if faculty or self.current_org else name,
                    "raw_text": supervisor, "review_status": "draft",
                })
                self.link("research_project_links", lid, fid)
                if not faculty and not self.current_org:
                    self.add_issue(fid, "faculty_id", "unmatched_person", "low",
                                   f"项目“{title}”的导师为 {name}，未与现有教师实体强行匹配。",
                                   "依据明确教师主页或师资章节复核关联。", "research_project_links", lid)

    def finalize(self):
        # URLs are metadata candidates, not proof of live official verification.
        url_sources = {}
        fragment_entities = defaultdict(list)
        for row in self.con.execute("""SELECT fragment_id, entity_type, entity_id FROM source_links
                                       WHERE fragment_id LIKE ?""", (f"FR_ATT_{self.uid}_%",)):
            fragment_entities[row[0]].append((row[1], row[2]))
        for fid, f in list(self.frag.items()):
            for url in extract_urls(f["content_text"]):
                if url not in url_sources:
                    sid = self.next_id("sources")
                    host = urlsplit(url).hostname or "链接"
                    self.insert("sources", {
                        "source_id": sid, "university_id": self.uid, "source_type": "other",
                        "source_name": f"{host}（原资料提取链接）", "url": url, "publisher": None,
                        "publication_date": None, "access_date": None, "language": None,
                        "is_official": 0, "verification_status": "unverified",
                        "note": "URL从原资料机械提取；未实际访问，不据此认定官方来源或填写访问日期。",
                        "raw_text": json.dumps({"extracted_from": fid, "url": url}, ensure_ascii=False),
                        "review_status": "draft",
                    })
                    url_sources[url] = sid
                for entity_type, entity_id in fragment_entities.get(fid, []):
                    sid = url_sources[url]
                    key = (entity_type, entity_id, sid, f["attachment_id"], fid, "supporting", f["locator"] or "")
                    if key in self.link_keys:
                        continue
                    self.link_keys.add(key)
                    self.insert("source_links", {
                        "link_id": self.next_id("source_links"), "source_id": sid,
                        "attachment_id": None, "fragment_id": None,
                        "entity_type": entity_type, "entity_id": entity_id, "dimension": DIM[entity_type],
                        "relation_type": "supporting", "locator": f["locator"],
                        "evidence_quote": url, "is_primary": 0,
                        "note": f"从原文片段{fid}（附件{f['attachment_id']}）提取的URL；未实时访问，不作为官方已核验证据。",
                        "created_at": NOW,
                    })
        for fid in self.frag:
            row = self.con.execute("SELECT disposition FROM raw_fragments WHERE fragment_id=?", (fid,)).fetchone()
            if row and row[0] == "unprocessed":
                self.raw_only(fid)
        self.con.execute("UPDATE universities SET data_status='extracted', notes=?, updated_at=? WHERE university_id=?",
                         (f"56校全量原文结构化机器初稿；六维、科研、成果和学生发展按可识别证据入库，未核验字段保持空值。批次 {self.batch_id}。", NOW, self.uid))
        self.con.execute("UPDATE import_batches SET status='validated', finished_at=?, quality_report_path=?, notes=?, updated_at=? WHERE batch_id=?",
                         (NOW, f"quality_reports/schools/{self.uid}_{self.school}_质量报告.md",
                          "全文、表格、PDF页、图片OCR候选及嵌入附件已处理；机器结构化初稿，官方来源仍需逐项核验。", NOW, self.batch_id))
        self.con.execute("UPDATE import_batches SET status='validated', finished_at=?, notes=?, updated_at=? WHERE batch_id=?",
                         (NOW, "附件登记、路径、大小和哈希已复核；全文解析与结构化见对应 BFULL 批次。", NOW, f"BRAW_{self.uid}"))
        self.con.execute("UPDATE attachments SET extraction_status='parsed', updated_at=? WHERE university_id=?",
                         (NOW, self.uid))
        self.con.commit()


BASE_SHA256 = "4907b2e6b651d9c4a6878ae0034e1e994a7bb504a6122e943d9d71a303e7b128"
PERMISSION_NOTE = "2026-11-24用户明确授权：所有文件均有许可，可公开下载。该授权仅改变下载权限，不代表来源已成为官方已核验来源。"
NEW_PREFIXES = {k: v for k, v in PREFIX.items() if k not in ("sources", "source_links", "review_issues")}


def verify_top_attachments(con):
    rows = con.execute("SELECT * FROM attachments ORDER BY university_id, attachment_id").fetchall()
    if len(rows) != 72:
        raise RuntimeError(f"顶层附件应为72份，实际{len(rows)}份。")
    pdf_pages = 0
    for row in rows:
        path = ROOT / row[6]
        if not path.is_file():
            raise FileNotFoundError(f"附件缺失：{row[6]}")
        if path.stat().st_size != row[10] or sha256(path) != row[9]:
            raise RuntimeError(f"附件大小或哈希与登记不符：{row[6]}")
        if path.suffix.lower() == ".pdf":
            with fitz.open(path) as doc:
                pages = len(doc)
            pdf_pages += pages
            con.execute("UPDATE attachments SET page_count=?, updated_at=? WHERE attachment_id=?",
                        (pages, NOW, row[0]))
    if pdf_pages != 162:
        raise RuntimeError(f"顶层PDF总页数应为162，实际{pdf_pages}。")
    return pdf_pages


def register_embedded(con, school_to_uid):
    entries = json.loads(EMBEDDED_MANIFEST.read_text(encoding="utf-8"))
    if len(entries) != 8:
        raise RuntimeError(f"嵌入附件清单应为8份，实际{len(entries)}份。")
    registered = defaultdict(list)
    counters = defaultdict(int)
    for item in entries:
        school = item["school"]
        uid = school_to_uid[school]
        counters[uid] += 1
        suffix = f"E{counters[uid]:02d}"
        attachment_id = f"ATT_{uid}_{suffix}"
        source_id = f"SRC_{uid}_{suffix}"
        path = ROOT / item["local_path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError(f"嵌入附件缺失或哈希变化：{item['local_path']}")
        container = con.execute("SELECT file_hash FROM attachments WHERE university_id=? AND local_path=?",
                                (uid, item["container"])).fetchone()
        if not container or container[0] != item["container_sha256"]:
            raise RuntimeError(f"嵌入附件的DOCX容器未匹配或哈希变化：{item['container']}")
        with fitz.open(path) as doc:
            pages = len(doc)
        if pages != item["pdf_pages"]:
            raise RuntimeError(f"嵌入PDF页数变化：{item['local_path']}")
        raw = {"container": item["container"], "container_sha256": item["container_sha256"],
               "entry": item["entry"], "embedded_original_name": item["embedded_original_name"],
               "sha256": item["sha256"], "pages": pages}
        con.execute("""INSERT INTO sources
                       (source_id,university_id,source_type,source_name,url,publisher,publication_date,access_date,
                        language,is_official,verification_status,note,raw_text,review_status,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (source_id, uid, "other", f"{school}DOCX内嵌附件：{item['embedded_original_name']}",
                     None, None, None, None, None, 0, "unverified",
                     "从用户提供的DOCX OLE对象提取；不是独立官方来源核验结论。", json.dumps(raw, ensure_ascii=False),
                     "draft", NOW, NOW))
        con.execute("""INSERT INTO attachments
                       (attachment_id,batch_id,source_id,university_id,attachment_type,file_name,local_path,official_url,
                        mime_type,file_hash,file_size_bytes,page_count,language,access_date,storage_status,
                        download_permission,extraction_status,note,raw_text,review_status,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (attachment_id, f"BRAW_{uid}", source_id, uid, "curriculum", path.name, item["local_path"], None,
                     "application/pdf", item["sha256"], item["bytes"], pages, None, None, "local_copy_present",
                     "allowed", "registered_only", f"从{item['container']}的{item['entry']}提取。{PERMISSION_NOTE}",
                     json.dumps(raw, ensure_ascii=False), "draft", NOW, NOW))
        registered[uid].append({"attachment_id": attachment_id, "path": path, "metadata": item})
    for uid in {r[0] for r in con.execute("SELECT university_id FROM universities")}:
        batch_id = f"BRAW_{uid}"
        old = con.execute("SELECT input_manifest_json FROM import_batches WHERE batch_id=?", (batch_id,)).fetchone()
        manifest = json.loads(old[0]) if old else []
        known = {x.get("attachment_id") for x in manifest}
        for row in con.execute("SELECT attachment_id,source_id,local_path,file_hash FROM attachments WHERE batch_id=?",
                               (batch_id,)):
            if row[0] not in known:
                manifest.append({"attachment_id": row[0], "source_id": row[1], "path": row[2], "sha256": row[3]})
        con.execute("UPDATE import_batches SET input_manifest_json=?, file_count=?, updated_at=? WHERE batch_id=?",
                    (json.dumps(manifest, ensure_ascii=False), len(manifest), NOW, batch_id))
    if sum(x["metadata"]["pdf_pages"] for values in registered.values() for x in values) != 60:
        raise RuntimeError("嵌入PDF总页数不是60页。")
    return registered


def authorize_downloads(con):
    con.execute("""UPDATE attachments
                   SET download_permission='allowed',
                       note=CASE WHEN note IS NULL OR note='' THEN ? ELSE note || ' ' || ? END,
                       updated_at=?""", (PERMISSION_NOTE, PERMISSION_NOTE, NOW))
    count = con.execute("SELECT count(*) FROM attachments WHERE download_permission='allowed'").fetchone()[0]
    if count != 80:
        raise RuntimeError(f"许可更新后应有80份可下载附件，实际{count}份。")


def load_ocr_map():
    entries = json.loads(OCR_JSON.read_text(encoding="utf-8"))
    return {(x["docx"], x["media"]): x for x in entries}


def process_school(con, uid, school, embedded, ocr_by_key):
    attachments = con.execute("""SELECT attachment_id,attachment_type,local_path FROM attachments
                                 WHERE university_id=? ORDER BY attachment_id""", (uid,)).fetchall()
    docx_rows = [x for x in attachments if x[1] == "raw_docx"]
    if len(docx_rows) != 1:
        raise RuntimeError(f"{school}应有1份主DOCX，实际{len(docx_rows)}份。")
    embedded_by_id = {x["attachment_id"]: x for x in embedded.get(uid, [])}
    manifest = [{"attachment_id": x[0], "path": x[2]} for x in attachments]
    batch_id = f"BFULL_{uid}"
    con.execute("""INSERT INTO import_batches
                   (batch_id,university_id,input_manifest_json,file_count,parser_version,status,started_at,
                    finished_at,quality_report_path,notes,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (batch_id, uid, json.dumps(manifest, ensure_ascii=False), len(manifest), PARSER_VERSION,
                 "started", NOW, None, f"quality_reports/schools/{uid}_{school}_质量报告.md",
                 "56校全量原文结构化机器初稿；处理中。", NOW, NOW))
    con.commit()
    importer = SchoolImporter(con, uid, school)
    try:
        docx = docx_rows[0]
        importer.process_docx(ROOT / docx[2], docx[0], ocr_by_key)
        for row in attachments:
            if row[1] == "raw_docx" or row[0] in embedded_by_id:
                continue
            importer.process_pdf(ROOT / row[2], row[0])
        for item in embedded.get(uid, []):
            importer.process_pdf(item["path"], item["attachment_id"], item["metadata"])
        importer.finalize()
    except Exception:
        con.rollback()
        con.execute("UPDATE import_batches SET status='failed', finished_at=?, notes=?, updated_at=? WHERE batch_id=?",
                    (NOW, "全量解析失败；未替换正式数据库。", NOW, batch_id))
        con.commit()
        raise
    return {"university_id": uid, "school": school,
            "fragments": len(importer.frag), "new_records": {k: len(v) for k, v in importer.new_records.items()},
            "dispositions": dict(con.execute("""SELECT disposition,count(*) FROM raw_fragments
                                                WHERE university_id=? GROUP BY disposition""", (uid,)))}


def validate_v1_preservation(con):
    base = sqlite3.connect(BASE)
    tables = dict(TABLE_PK, universities="university_id", attachments="attachment_id", sources="source_id")
    differences = []
    for table, pk in tables.items():
        cols = {r[1] for r in base.execute(f"PRAGMA table_info({table})")}
        if "raw_text" not in cols:
            continue
        old_rows = base.execute(f"SELECT {pk},raw_text FROM {table}").fetchall()
        for entity_id, raw_text in old_rows:
            row = con.execute(f"SELECT raw_text FROM {table} WHERE {pk}=?", (entity_id,)).fetchone()
            if row is None or row[0] != raw_text:
                differences.append(f"{table}/{entity_id}")
    base.close()
    if differences:
        raise RuntimeError(f"V1原行raw_text或旧ID发生变化：{differences[:10]}")
    return {"checked": True, "differences": 0}


def validate_build(con, selected, full):
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    foreign = con.execute("PRAGMA foreign_key_check").fetchall()
    if integrity != "ok" or foreign:
        raise RuntimeError(f"完整性门禁失败：integrity={integrity}, foreign_keys={foreign[:5]}")
    placeholders = ",".join("?" for _ in selected)
    unprocessed = con.execute(f"SELECT count(*) FROM raw_fragments WHERE university_id IN ({placeholders}) AND disposition='unprocessed'",
                              selected).fetchone()[0]
    if unprocessed:
        raise RuntimeError(f"仍有{unprocessed}条原文片段为unprocessed。")
    missing_evidence = []
    for table, prefix in NEW_PREFIXES.items():
        pk = TABLE_PK[table]
        pattern = f"{prefix}_U___"
        # 新ID中的下划线按LIKE通配符处理不影响前缀语义，但逐校限定结果。
        for row in con.execute(f"""SELECT b.{pk} FROM {table} b
                                   LEFT JOIN source_links s ON s.entity_type=? AND s.entity_id=b.{pk}
                                   WHERE b.{pk} LIKE ? AND s.link_id IS NULL""", (table, pattern)):
            entity_id = row[0]
            if any(entity_id.startswith(f"{prefix}_{uid}_") for uid in selected):
                missing_evidence.append(f"{table}/{entity_id}")
    if missing_evidence:
        raise RuntimeError(f"新业务记录缺少原文证据：{missing_evidence[:10]}")
    suspicious_programs = []
    invalid_courses = []
    for uid in selected:
        for name, in con.execute("SELECT program_name_cn FROM programs WHERE university_id=? AND program_id LIKE 'P_' || university_id || '_%'", (uid,)):
            if generic_heading(name) or re.fullmatch(r"招生专业|初试|复试|进阶\s*\d+", name):
                suspicious_programs.append(f"{uid}/{name}")
        for name, in con.execute("SELECT course_name FROM courses WHERE university_id=? AND course_id LIKE 'C_' || university_id || '_%'", (uid,)):
            if header_matches(header_key(name), COURSE_NAME) or not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", name):
                invalid_courses.append(f"{uid}/{name}")
    if suspicious_programs or invalid_courses:
        raise RuntimeError(f"语义门禁失败：疑似非项目{suspicious_programs[:10]}，无效课程{invalid_courses[:10]}")
    bad_pdf_locators = con.execute("""SELECT count(*) FROM source_links s JOIN attachments a USING(attachment_id)
                                      WHERE a.local_path LIKE '%.pdf' AND s.locator LIKE 'Word表%'""").fetchone()[0]
    if bad_pdf_locators:
        raise RuntimeError(f"仍有{bad_pdf_locators}条PDF表格证据使用Word定位。")
    if con.execute("SELECT count(*) FROM attachments").fetchone()[0] != 80:
        raise RuntimeError("附件总数不是80份。")
    if con.execute("SELECT count(*) FROM attachments WHERE download_permission='allowed'").fetchone()[0] != 80:
        raise RuntimeError("80份附件未全部设为allowed。")
    if con.execute("SELECT coalesce(sum(page_count),0) FROM attachments WHERE local_path LIKE '%.pdf'").fetchone()[0] != 222:
        raise RuntimeError("PDF页数合计不是222页。")
    empty_schools = []
    for uid in selected:
        fragments = con.execute("SELECT count(*) FROM raw_fragments WHERE university_id=?", (uid,)).fetchone()[0]
        if not fragments:
            empty_schools.append(uid)
        status = con.execute("SELECT data_status FROM universities WHERE university_id=?", (uid,)).fetchone()[0]
        if status != "extracted":
            raise RuntimeError(f"{uid}未更新为extracted。")
    if empty_schools:
        raise RuntimeError(f"异常空校：{empty_schools}")
    if full:
        if len(selected) != 56 or con.execute("SELECT count(*) FROM universities WHERE data_status='extracted'").fetchone()[0] != 56:
            raise RuntimeError("全量门禁要求56校均为extracted。")
        if con.execute("SELECT count(*) FROM attachments WHERE extraction_status='parsed'").fetchone()[0] != 80:
            raise RuntimeError("全量门禁要求80份附件均为parsed。")
        if con.execute("SELECT count(*) FROM import_batches WHERE batch_id LIKE 'BFULL_%' AND status='validated'").fetchone()[0] != 56:
            raise RuntimeError("56个全量批次未全部validated。")
    preservation = validate_v1_preservation(con)
    tables = ["universities", "programs", "objectives", "courses", "program_course", "faculty",
              "faculty_organization", "practice", "evaluation", "organizations", "research_projects",
              "research_project_links", "research_outputs", "research_output_links", "student_development",
              "sources", "source_links", "attachments", "raw_fragments", "review_issues", "import_batches"]
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    report = {"integrity_check": integrity, "foreign_key_violations": len(foreign),
              "unprocessed_fragments": unprocessed, "missing_new_record_evidence": 0,
              "bad_pdf_locators": bad_pdf_locators, "v1_preservation": preservation,
              "views": con.execute("SELECT count(*) FROM sqlite_master WHERE type='view'").fetchone()[0],
              "triggers": con.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0],
              "counts": counts}
    if full and (report["views"] != 17 or report["triggers"] != 44):
        raise RuntimeError("V2视图或触发器数量发生变化。")
    return report


def main():
    parser = argparse.ArgumentParser(description="56校DOCX/PDF全量结构化；默认只构建隔离测试库。")
    parser.add_argument("--schools", help="逗号分隔的高校ID，如U013,U005；默认56校。")
    parser.add_argument("--promote", action="store_true", help="全部门禁通过后原子替换正式数据库。")
    args = parser.parse_args()
    if sha256(BASE) != BASE_SHA256:
        raise RuntimeError("全量前备份哈希不匹配，停止构建。")
    if args.promote and sha256(DB) != BASE_SHA256:
        raise RuntimeError("正式库已不是全量前基线，拒绝覆盖；请先核查并另行备份。")
    con0 = sqlite3.connect(BASE)
    all_schools = con0.execute("SELECT university_id,university_name_cn FROM universities ORDER BY university_id").fetchall()
    con0.close()
    selected = args.schools.split(",") if args.schools else [x[0] for x in all_schools]
    school_to_uid = {name: uid for uid, name in all_schools}
    unknown = set(selected) - {x[0] for x in all_schools}
    if unknown:
        raise RuntimeError(f"未知高校ID：{sorted(unknown)}")
    if args.promote and len(selected) != 56:
        raise RuntimeError("只有56校全量运行才允许--promote。")
    for target in (BUILD, OUTPUT_BUILD, PROMOTE_STAGING):
        for suffix in ("", "-wal", "-shm", "-journal"):
            p = Path(str(target) + suffix)
            if p.exists():
                p.unlink()
    shutil.copy2(BASE, BUILD)
    con = sqlite3.connect(BUILD)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA synchronous=FULL")
    try:
        top_pages = verify_top_attachments(con)
        embedded = register_embedded(con, school_to_uid)
        authorize_downloads(con)
        con.commit()
        ocr_by_key = load_ocr_map()
        school_results = []
        for uid, school in all_schools:
            if uid not in selected:
                continue
            print(f"[{uid}] {school} 开始全量解析", flush=True)
            result = process_school(con, uid, school, embedded, ocr_by_key)
            school_results.append(result)
            print(f"[{uid}] {school} 完成：原文{result['fragments']}条，{result['new_records']}", flush=True)
        report = validate_build(con, selected, len(selected) == 56)
        con.commit()
        con.close()
        con = None
        build_sha = sha256(BUILD)
        promoted = False
        if args.promote:
            if sha256(DB) != BASE_SHA256:
                raise RuntimeError("替换前正式库哈希发生变化，已停止原子切换。")
            shutil.copy2(BUILD, PROMOTE_STAGING)
            if sha256(PROMOTE_STAGING) != build_sha:
                raise RuntimeError("写回项目目录的候选库哈希不一致，拒绝替换正式库。")
            candidate = sqlite3.connect(PROMOTE_STAGING)
            if candidate.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or candidate.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("项目目录候选库完整性或外键复核失败。")
            candidate.close()
            os.replace(PROMOTE_STAGING, DB)
            promoted = True
            check = sqlite3.connect(DB)
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or check.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("原子切换后的正式库复核失败。")
            check.close()
        else:
            shutil.copy2(BUILD, OUTPUT_BUILD)
            if sha256(OUTPUT_BUILD) != build_sha:
                raise RuntimeError("隔离测试库写回项目目录后哈希不一致。")
        summary = {"created_at": NOW, "parser_version": PARSER_VERSION, "mode": "full" if len(selected) == 56 else "slice",
                   "selected": selected, "promoted": promoted, "database": str(DB if promoted else OUTPUT_BUILD),
                   "database_sha256": build_sha, "top_pdf_pages": top_pages, "embedded_pdf_pages": 60,
                   "permission_note": PERMISSION_NOTE, "validation": report, "schools": school_results}
        SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"promoted": promoted, "database_sha256": build_sha, "counts": report["counts"]},
                         ensure_ascii=False, indent=2), flush=True)
    except Exception:
        if con:
            con.rollback()
            con.close()
        raise


if __name__ == "__main__":
    main()
