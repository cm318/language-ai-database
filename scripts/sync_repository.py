from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = ROOT.parent / "language_ai_repo"
REPORTS = ROOT / "quality_reports"
SYNC_REPORT = REPORTS / "repository_sync.json"
DB = ROOT / "data" / "language_ai_cases.db"

ROOT_FILES = [
    ".gitignore",
    ".streamlit/config.toml",
    "README.md",
    "部署说明.md",
    "app.py",
    "requirements.txt",
    "data/language_ai_cases.db.gz",
    "data/database_manifest.json",
    "data/language_ai_cases.xlsx",
]

QUALITY_FILES = [
    "80份附件完整性核验报告.md",
    "全量结构化验收报告.md",
    "阶段总体验收报告.md",
    "browser_regression.json",
    "constraint_tests.json",
    "database_bootstrap_test.json",
    "deployment_database.json",
    "deployment_status.json",
    "excel_recalc_result.json",
    "excel_sqlite_consistency.json",
    "excel_verify.json",
    "excel_verify_tool_raw.json",
    "final_acceptance_checks.json",
    "final_legacy_comparison.json",
    "full_attachment_verification.json",
    "full_import_summary.json",
    "full_quality_summary.json",
    "online_precheck.json",
    "repository_bootstrap_test.json",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not value or "\\" in value:
        raise ValueError(f"不安全的仓库相对路径：{value!r}")
    return path.as_posix()


def copy_verified(source: Path, target: Path) -> bool:
    """显式流式复制，避免挂载卷 sendfile 兼容问题；返回是否发生变化。"""
    if target.is_file() and target.stat().st_size == source.stat().st_size and sha(target) == sha(source):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".sync-part")
    try:
        with source.open("rb") as src, temporary.open("wb") as dst:
            for chunk in iter(lambda: src.read(4 * 1024 * 1024), b""):
                dst.write(chunk)
        if temporary.stat().st_size != source.stat().st_size or sha(temporary) != sha(source):
            raise IOError(f"复制后哈希不一致：{source}")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def collect_payload() -> tuple[dict[str, Path], list[dict]]:
    acceptance = json.loads((REPORTS / "final_acceptance_checks.json").read_text(encoding="utf-8"))
    if acceptance.get("status") != "pass":
        raise RuntimeError("最终总验收未通过，停止同步公开仓库")
    quality = json.loads((REPORTS / "full_quality_summary.json").read_text(encoding="utf-8"))
    if quality.get("status") != "pass" or quality.get("school_reports") != 56:
        raise RuntimeError("56 校逐校质量报告未完整生成，停止同步")

    files: dict[str, Path] = {}
    for value in ROOT_FILES:
        rel = safe_relative(value)
        source = ROOT / rel
        if not source.is_file():
            raise FileNotFoundError(f"缺少部署文件：{rel}")
        files[rel] = source

    for folder in ("schema", "scripts"):
        for source in sorted((ROOT / folder).glob("*")):
            if source.is_file() and source.suffix in {".py", ".sql", ".md"}:
                files[safe_relative(source.relative_to(ROOT).as_posix())] = source

    for name in QUALITY_FILES:
        source = REPORTS / name
        if not source.is_file():
            raise FileNotFoundError(f"缺少最终质量证据：quality_reports/{name}")
        files[f"quality_reports/{name}"] = source

    school_reports = sorted((REPORTS / "schools").glob("U*_质量报告.md"))
    if len(school_reports) != 56:
        raise RuntimeError(f"逐校报告应为 56 份，实际 {len(school_reports)} 份")
    school_ids = set()
    for source in school_reports:
        school_ids.add(source.name[:4])
        files[safe_relative(source.relative_to(ROOT).as_posix())] = source
    if school_ids != {f"U{i:03d}" for i in range(1, 57)}:
        raise RuntimeError("逐校报告编号不是连续的 U001—U056")

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(row) for row in con.execute(
        """SELECT attachment_id,local_path,file_size_bytes,file_hash,
                  extraction_status,download_permission
           FROM attachments ORDER BY attachment_id"""
    )]
    con.close()
    if len(rows) != 80:
        raise RuntimeError(f"登记附件应为 80 份，实际 {len(rows)} 份")
    attachment_paths = set()
    for row in rows:
        rel = safe_relative(row["local_path"])
        if rel in attachment_paths:
            raise RuntimeError(f"附件路径重复：{rel}")
        attachment_paths.add(rel)
        if row["download_permission"] != "allowed" or row["extraction_status"] != "parsed":
            raise RuntimeError(f"附件许可或解析状态不合格：{row['attachment_id']}")
        source = ROOT / rel
        if not source.is_file():
            raise FileNotFoundError(f"登记附件不存在：{rel}")
        if source.stat().st_size != row["file_size_bytes"] or sha(source) != row["file_hash"]:
            raise RuntimeError(f"附件字节数或 SHA-256 不一致：{rel}")
        files[rel] = source

    top_level = [p for p in attachment_paths if p.startswith("raw_files/")]
    embedded = [p for p in attachment_paths if p.startswith("derived/embedded/")]
    if len(top_level) != 72 or len(embedded) != 8:
        raise RuntimeError(f"附件范围错误：顶层 {len(top_level)}，嵌入 {len(embedded)}")
    if any(p.parent.name not in {"北京大学", "慕尼黑大学"} for p in map(Path, embedded)):
        raise RuntimeError("嵌入附件只能来自规范中文子目录")

    manifest = json.loads((ROOT / "data/database_manifest.json").read_text(encoding="utf-8"))
    archive = ROOT / "data/language_ai_cases.db.gz"
    if sha(DB) != manifest["sha256"] or DB.stat().st_size != manifest["bytes"]:
        raise RuntimeError("正式 SQLite 与部署清单不一致")
    if sha(archive) != manifest["compressed_sha256"] or archive.stat().st_size != manifest["compressed_bytes"]:
        raise RuntimeError("压缩 SQLite 与部署清单不一致")

    entries = [
        {"path": rel, "bytes": source.stat().st_size, "sha256": sha(source)}
        for rel, source in sorted(files.items())
    ]
    return files, entries


def main() -> None:
    parser = argparse.ArgumentParser(description="将正式 V2 全量部署文件同步到专用 GitHub 克隆")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--allow-dirty", action="store_true", help="允许专用克隆已有未提交改动；源文件仍会覆盖同名文件")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / ".git").is_dir():
        raise RuntimeError(f"目标不是 Git 克隆：{repo}")
    if not args.allow_dirty and git(repo, "status", "--porcelain"):
        raise RuntimeError("专用克隆存在未提交改动；先核查，或明确使用 --allow-dirty")

    files, entries = collect_payload()
    report = {
        "status": "pass",
        "generated_at": utc_now(),
        "source_root": str(ROOT),
        "target_repository": "https://github.com/cm318/language-ai-database",
        "branch": "main",
        "payload_file_count_excluding_this_report": len(entries),
        "repository_file_count_including_this_report": len(entries) + 1,
        "payload_total_bytes_excluding_this_report": sum(x["bytes"] for x in entries),
        "registered_attachment_count": 80,
        "top_level_attachment_count": 72,
        "embedded_attachment_count": 8,
        "uncompressed_database_included": False,
        "content_reduced": False,
        "files": entries,
        "notes": [
            "本报告自身不自哈希；其余公开仓库文件均逐文件记录字节数和 SHA-256。",
            "仅同步数据库登记的 80 份正式附件；早期乱码 OLE 重复文件、测试库、备份和原始 ZIP 均排除。",
            "同步与本地提交不等于已推送 GitHub，也不等于 Streamlit Cloud 已更新。",
        ],
    }
    SYNC_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    files[SYNC_REPORT.relative_to(ROOT).as_posix()] = SYNC_REPORT
    expected = set(files)

    # 专用克隆是正式部署镜像：仅清理不在本次明确清单中的旧文件，绝不触碰 .git。
    for target in sorted(repo.rglob("*"), reverse=True):
        if not target.is_file() or ".git" in target.relative_to(repo).parts:
            continue
        rel = target.relative_to(repo).as_posix()
        if rel not in expected:
            target.unlink()
    for directory in sorted((p for p in repo.rglob("*") if p.is_dir()), reverse=True):
        if ".git" in directory.relative_to(repo).parts:
            continue
        try:
            directory.rmdir()
        except OSError:
            pass

    changed = []
    for rel, source in sorted(files.items()):
        if copy_verified(source, repo / rel):
            changed.append(rel)

    actual = {
        p.relative_to(repo).as_posix()
        for p in repo.rglob("*") if p.is_file() and ".git" not in p.relative_to(repo).parts
    }
    if actual != expected:
        raise RuntimeError(f"仓库文件集合不一致：缺少 {sorted(expected - actual)}，多出 {sorted(actual - expected)}")
    for rel, source in files.items():
        target = repo / rel
        if target.stat().st_size >= 100 * 1024 * 1024:
            raise RuntimeError(f"文件达到或超过 GitHub 100 MiB 限制：{rel}")
        if target.stat().st_size != source.stat().st_size or sha(target) != sha(source):
            raise RuntimeError(f"仓库副本哈希复核失败：{rel}")
    forbidden = [rel for rel in actual if rel == "data/language_ai_cases.db" or rel.endswith((".building.db", ".build.db", ".promoting.db"))]
    if forbidden:
        raise RuntimeError(f"公开仓库含禁止文件：{forbidden}")

    result = {
        "status": "pass",
        "repository": str(repo),
        "file_count": len(actual),
        "changed_file_count": len(changed),
        "attachment_count": 80,
        "uncompressed_database_included": False,
        "all_files_below_github_100_mib": True,
        "hash_verification": "pass",
        "sync_report_sha256": sha(SYNC_REPORT),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
