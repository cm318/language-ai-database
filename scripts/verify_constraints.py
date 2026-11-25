from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "language_ai_cases.db"
REPORT = ROOT / "quality_reports" / "constraint_tests.json"
TEST_ROOT = ROOT / "tests"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    before_hash = sha256(DB)
    results: list[dict] = []

    # 长时间读写在本机临时目录执行，避免挂载卷 I/O 阻塞；正式库始终以只读方式打开。
    with tempfile.TemporaryDirectory(prefix="constraint_") as tmpdir:
        test_db = Path(tmpdir) / "constraint_test.db"
        source = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con = sqlite3.connect(test_db)
        source.backup(con)
        source.close()
        con.execute("PRAGMA foreign_keys=ON")
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1

        # 仅存在于临时副本中的测试夹具，不进入正式数据库和 Excel。
        con.executemany(
            "INSERT INTO universities(university_id,university_name_cn,country,data_status) VALUES (?,?,?,?)",
            [("QA-U", "约束测试高校（临时副本）", "测试", "not_started")],
        )
        con.executemany(
            "INSERT INTO programs(program_id,university_id,program_kind,is_formal_degree,program_name_cn) VALUES (?,?,?,?,?)",
            [
                ("QA-P1", "QA-U", "degree_program", 1, "约束测试项目一"),
                ("QA-P2", "QA-U", "degree_program", 1, "约束测试项目二"),
            ],
        )
        con.executemany(
            "INSERT INTO courses(course_id,university_id,course_name) VALUES (?,?,?)",
            [
                ("QA-C1", "QA-U", "约束测试课程"),
                ("QA-C-REF", "QA-U", "证据保护测试课程"),
                ("QA-C-ISSUE", "QA-U", "核验事项保护测试课程"),
            ],
        )
        con.execute("INSERT INTO faculty(faculty_id,university_id,name) VALUES ('QA-F1','QA-U','约束测试教师')")
        con.executemany(
            "INSERT INTO organizations(organization_id,university_id,name) VALUES (?,?,?)",
            [("QA-O1", "QA-U", "约束测试平台一"), ("QA-O2", "QA-U", "约束测试平台二")],
        )
        con.execute(
            "INSERT INTO sources(source_id,university_id,source_type,source_name) VALUES ('QA-S1','QA-U','other','约束测试来源')"
        )
        con.execute(
            "INSERT INTO research_projects(project_id,university_id,project_name) VALUES ('QA-RP1','QA-U','约束测试科研项目')"
        )
        con.execute(
            "INSERT INTO research_outputs(output_id,university_id,output_type,title) VALUES ('QA-RO1','QA-U','other','约束测试科研成果')"
        )
        con.execute(
            "INSERT INTO source_links(link_id,source_id,entity_type,entity_id,relation_type) VALUES ('QA-SL-REF','QA-S1','courses','QA-C-REF','supporting')"
        )
        con.execute(
            "INSERT INTO review_issues(issue_id,university_id,entity_type,entity_id,issue_type,severity,description) VALUES ('QA-RI-REF','QA-U','courses','QA-C-ISSUE','constraint_test','low','临时副本约束测试')"
        )
        con.commit()

        def run_case(name: str, category: str, operation, expect: str, message_contains: str | None = None) -> None:
            con.execute("SAVEPOINT qa_case")
            error = None
            try:
                operation()
            except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
                error = str(exc)
            finally:
                con.execute("ROLLBACK TO qa_case")
                con.execute("RELEASE qa_case")
            passed = (expect == "error" and error is not None) or (expect == "success" and error is None)
            if passed and error and message_contains:
                passed = message_contains.lower() in error.lower()
            results.append({
                "name": name,
                "category": category,
                "expected": " rejected" if expect == "error" else "accepted",
                "actual": "rejected" if error else "accepted",
                "database_message": error,
                "passed": passed,
            })

        run_case(
            "文本主键允许 NULL 时必须拒绝", "primary_key",
            lambda: con.execute("INSERT INTO universities(university_id,university_name_cn,country) VALUES (NULL,'空主键测试','测试')"),
            "error", "not null",
        )
        run_case(
            "项目引用不存在高校时必须拒绝", "foreign_key",
            lambda: con.execute("INSERT INTO programs(program_id,university_id,program_name_cn) VALUES ('QA-ORPHAN-P','QA-NO-U','孤外键测试')"),
            "error", "foreign key",
        )
        run_case(
            "新增证据引用不存在业务目标时必须拒绝", "evidence_target",
            lambda: con.execute("INSERT INTO source_links(link_id,source_id,entity_type,entity_id,relation_type) VALUES ('QA-SL-ORPHAN','QA-S1','courses','QA-NO-C','supporting')"),
            "error", "invalid",
        )
        run_case(
            "证据更新为不存在业务目标时必须拒绝", "evidence_target",
            lambda: (
                con.execute("INSERT INTO source_links(link_id,source_id,entity_type,entity_id,relation_type) VALUES ('QA-SL-UPDATE','QA-S1','courses','QA-C1','supporting')"),
                con.execute("UPDATE source_links SET entity_id='QA-NO-C' WHERE link_id='QA-SL-UPDATE'"),
            ),
            "error", "invalid",
        )
        run_case(
            "新增核验事项引用不存在业务目标时必须拒绝", "review_target",
            lambda: con.execute("INSERT INTO review_issues(issue_id,entity_type,entity_id,issue_type,severity,description) VALUES ('QA-RI-ORPHAN','courses','QA-NO-C','constraint_test','low','孤目标测试')"),
            "error", "invalid",
        )
        run_case(
            "证据缺少来源、附件和原文片段时必须拒绝", "evidence_carrier",
            lambda: con.execute("INSERT INTO source_links(link_id,entity_type,entity_id,relation_type) VALUES ('QA-SL-NO-CARRIER','courses','QA-C1','supporting')"),
            "error", "check constraint",
        )
        run_case(
            "被证据引用的记录不能删除", "referenced_delete",
            lambda: con.execute("DELETE FROM courses WHERE course_id='QA-C-REF'"),
            "error", "referenced by evidence",
        )
        run_case(
            "被证据引用的记录不能修改主键", "referenced_primary_key_update",
            lambda: con.execute("UPDATE courses SET course_id='QA-C-REF-NEW' WHERE course_id='QA-C-REF'"),
            "error", "referenced primary key",
        )
        run_case(
            "被核验事项引用的记录不能删除", "referenced_delete",
            lambda: con.execute("DELETE FROM courses WHERE course_id='QA-C-ISSUE'"),
            "error", "referenced by evidence",
        )
        run_case(
            "被核验事项引用的记录不能修改主键", "referenced_primary_key_update",
            lambda: con.execute("UPDATE courses SET course_id='QA-C-ISSUE-NEW' WHERE course_id='QA-C-ISSUE'"),
            "error", "referenced primary key",
        )

        for table, prefix, parent_field, parent_id, id_field in [
            ("research_project_links", "QA-RPL", "project_id", "QA-RP1", "project_link_id"),
            ("research_output_links", "QA-ROL", "output_id", "QA-RO1", "output_link_id"),
        ]:
            run_case(
                f"{table} 同时关联两个目标时必须拒绝", "research_link_cardinality",
                lambda table=table, prefix=prefix, parent_field=parent_field, parent_id=parent_id, id_field=id_field: con.execute(
                    f"INSERT INTO {table}({id_field},{parent_field},faculty_id,organization_id) VALUES (?,?,?,?)",
                    (prefix + "-TWO", parent_id, "QA-F1", "QA-O1"),
                ),
                "error", "check constraint",
            )
            run_case(
                f"{table} 无关联目标且未保留原名时必须拒绝", "research_link_raw_name",
                lambda table=table, prefix=prefix, parent_field=parent_field, parent_id=parent_id, id_field=id_field: con.execute(
                    f"INSERT INTO {table}({id_field},{parent_field}) VALUES (?,?)",
                    (prefix + "-NO-NAME", parent_id),
                ),
                "error", "check constraint",
            )
            run_case(
                f"{table} 无关联目标但保留待核验原名时允许", "research_link_raw_name",
                lambda table=table, prefix=prefix, parent_field=parent_field, parent_id=parent_id, id_field=id_field: con.execute(
                    f"INSERT INTO {table}({id_field},{parent_field},linked_name_raw) VALUES (?,?,?)",
                    (prefix + "-RAW", parent_id, "原文待核验名称"),
                ),
                "success",
            )
            run_case(
                f"{table} 仅关联一个目标时允许", "research_link_cardinality",
                lambda table=table, prefix=prefix, parent_field=parent_field, parent_id=parent_id, id_field=id_field: con.execute(
                    f"INSERT INTO {table}({id_field},{parent_field},faculty_id) VALUES (?,?,?)",
                    (prefix + "-ONE", parent_id, "QA-F1"),
                ),
                "success",
            )

        run_case(
            "scope_type=program 时缺少项目外键必须拒绝", "student_scope",
            lambda: con.execute("INSERT INTO student_development(development_id,university_id,scope_type,record_type,subject_type) VALUES ('QA-SD-NO-P','QA-U','program','student_research','group')"),
            "error", "check constraint",
        )
        run_case(
            "scope_type=university 时不强行关联项目", "student_scope",
            lambda: con.execute("INSERT INTO student_development(development_id,university_id,scope_type,record_type,subject_type) VALUES ('QA-SD-U','QA-U','university','student_research','group')"),
            "success",
        )

        run_case(
            "规范化字段相同的项目—课程关系必须去重", "program_course_dedup",
            lambda: (
                con.execute("INSERT INTO program_course(program_course_id,program_id,course_id) VALUES ('QA-PC1','QA-P1','QA-C1')"),
                con.execute("INSERT INTO program_course(program_course_id,program_id,course_id) VALUES ('QA-PC2','QA-P1','QA-C1')"),
            ),
            "error", "unique constraint",
        )

        def positive_program_course() -> None:
            con.execute("INSERT INTO program_course(program_course_id,program_id,course_id) VALUES ('QA-PC-P1','QA-P1','QA-C1')")
            con.execute("INSERT INTO program_course(program_course_id,program_id,course_id) VALUES ('QA-PC-P2','QA-P2','QA-C1')")
            count = con.execute("SELECT count(*) FROM program_course WHERE course_id='QA-C1'").fetchone()[0]
            assert count == 2, count

        run_case("同一课程可正向关联两个不同项目", "program_course_many_to_many", positive_program_course, "success")

        def positive_faculty_organizations() -> None:
            con.execute("INSERT INTO faculty_organization(faculty_organization_id,faculty_id,organization_id,role_title) VALUES ('QA-FO1','QA-F1','QA-O1','成员')")
            con.execute("INSERT INTO faculty_organization(faculty_organization_id,faculty_id,organization_id,role_title) VALUES ('QA-FO2','QA-F1','QA-O2','成员')")
            assert con.execute("SELECT count(*) FROM faculty WHERE faculty_id='QA-F1'").fetchone()[0] == 1
            assert con.execute("SELECT count(*) FROM faculty_organization WHERE faculty_id='QA-F1'").fetchone()[0] == 2

        run_case("同一教师可关联两个平台且不重复教师实体", "faculty_organization_many_to_many", positive_faculty_organizations, "success")
        run_case(
            "完全相同的教师—平台关系必须去重", "faculty_organization_dedup",
            lambda: (
                con.execute("INSERT INTO faculty_organization(faculty_organization_id,faculty_id,organization_id,role_title) VALUES ('QA-FO-DUP1','QA-F1','QA-O1','成员')"),
                con.execute("INSERT INTO faculty_organization(faculty_organization_id,faculty_id,organization_id,role_title) VALUES ('QA-FO-DUP2','QA-F1','QA-O1','成员')"),
            ),
            "error", "unique constraint",
        )
        run_case(
            "非学位科研训练路径不得标为正式学位", "program_kind",
            lambda: con.execute("INSERT INTO programs(program_id,university_id,program_kind,is_formal_degree,program_name_cn) VALUES ('QA-P-NON-DEGREE','QA-U','research_training',1,'错误学位标记测试')"),
            "error", "check constraint",
        )

        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = len(con.execute("PRAGMA foreign_key_check").fetchall())
        con.close()

    after_hash = sha256(DB)
    passed = all(item["passed"] for item in results) and integrity == "ok" and foreign_key_errors == 0 and before_hash == after_hash
    report = {
        "test_time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "scope": "全部变更仅作用于临时 SQLite 测试副本；临时副本已删除。",
        "production_db_sha256_before": before_hash,
        "production_db_sha256_after": after_hash,
        "production_db_unchanged": before_hash == after_hash,
        "test_copy_integrity_check": integrity,
        "test_copy_foreign_key_errors": foreign_key_errors,
        "test_count": len(results),
        "passed_count": sum(item["passed"] for item in results),
        "failed_count": sum(not item["passed"] for item in results),
        "status": "pass" if passed else "fail",
        "results": results,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False, indent=2))
    if not passed:
        for item in results:
            if not item["passed"]:
                print("FAILED:", json.dumps(item, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
