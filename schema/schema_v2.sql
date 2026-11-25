-- 世界一流大学“语言+人工智能”复合型人才培养模式研究
-- 数据库 V2：21 表、约束、索引、证据触发器、统计与 V1 兼容视图
-- 生成日期：2026-11-24；执行前请备份。

PRAGMA foreign_keys = ON;

CREATE TABLE universities (
    university_id TEXT NOT NULL PRIMARY KEY,
    university_name_cn TEXT NOT NULL,
    university_name_en TEXT,
    name_aliases TEXT,
    country TEXT NOT NULL,
    region TEXT,
    university_type TEXT,
    ranking_info TEXT,
    official_website TEXT,
    collection_year INTEGER,
    data_status TEXT NOT NULL DEFAULT 'not_started'
        CHECK (data_status IN ('not_started','extracted','partial','reviewed')),
    completeness TEXT,
    notes TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (official_website IS NULL OR length(trim(official_website)) > 0)
);

CREATE TABLE sources (
    source_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_type TEXT NOT NULL
        CHECK (source_type IN ('official_web','official_pdf','handbook','catalog','compilation','other')),
    source_name TEXT NOT NULL,
    url TEXT,
    publisher TEXT,
    publication_date TEXT,
    access_date TEXT,
    language TEXT,
    is_official INTEGER NOT NULL DEFAULT 0 CHECK (is_official IN (0,1)),
    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified','verified','unreachable','needs_review')),
    note TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (url IS NULL OR length(trim(url)) > 0),
    CHECK (source_type <> 'compilation' OR is_official = 0)
);

CREATE TABLE organizations (
    organization_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    parent_organization_id TEXT REFERENCES organizations(organization_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    parent_org_text TEXT,
    name TEXT NOT NULL,
    name_en TEXT,
    org_type TEXT,
    research_directions TEXT,
    ai_related TEXT NOT NULL DEFAULT 'unknown' CHECK (ai_related IN ('yes','no','unknown')),
    language_related TEXT NOT NULL DEFAULT 'unknown' CHECK (language_related IN ('yes','no','unknown')),
    interdisciplinary TEXT NOT NULL DEFAULT 'unknown' CHECK (interdisciplinary IN ('yes','no','unknown')),
    description TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE programs (
    program_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    parent_program_id TEXT REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    host_organization_id TEXT REFERENCES organizations(organization_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    program_kind TEXT NOT NULL DEFAULT 'other'
        CHECK (program_kind IN ('degree_program','specialization','stage','research_training','research_group','fellowship','short_program','other')),
    is_formal_degree INTEGER NOT NULL DEFAULT 0 CHECK (is_formal_degree IN (0,1)),
    level TEXT,
    level_raw TEXT,
    program_name_cn TEXT NOT NULL,
    program_name_en TEXT,
    degree TEXT,
    host_unit_text TEXT,
    duration TEXT,
    language_of_instruction TEXT,
    entry_level TEXT,
    admission_summary TEXT,
    positioning TEXT,
    program_size TEXT,
    sequence_no INTEGER,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (parent_program_id IS NULL OR parent_program_id <> program_id),
    CHECK (program_kind NOT IN ('research_training','research_group','short_program') OR is_formal_degree = 0)
);

CREATE TABLE objectives (
    objective_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    program_id TEXT REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    scope_type TEXT NOT NULL
        CHECK (scope_type IN ('program','university','cross_program','pending_review')),
    dimension TEXT,
    description TEXT NOT NULL,
    sequence_no INTEGER,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((scope_type = 'program' AND program_id IS NOT NULL) OR scope_type <> 'program')
);

CREATE TABLE courses (
    course_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    course_code TEXT,
    course_name TEXT NOT NULL,
    course_name_raw TEXT,
    course_name_en TEXT,
    course_name_zh TEXT,
    language TEXT,
    description TEXT,
    ai_tag TEXT NOT NULL DEFAULT 'unknown' CHECK (ai_tag IN ('yes','no','unknown')),
    language_tag TEXT NOT NULL DEFAULT 'unknown' CHECK (language_tag IN ('yes','no','unknown')),
    practice_tag TEXT NOT NULL DEFAULT 'unknown' CHECK (practice_tag IN ('yes','no','unknown')),
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE program_course (
    program_course_id TEXT NOT NULL PRIMARY KEY,
    program_id TEXT NOT NULL REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    course_id TEXT NOT NULL REFERENCES courses(course_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    module TEXT,
    stage TEXT,
    semester TEXT,
    academic_year TEXT,
    required_elective TEXT,
    credits REAL,
    credit_system TEXT,
    lecture_hours TEXT,
    directed_study_hours TEXT,
    practical_hours TEXT,
    relation_note TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (credits IS NULL OR credits >= 0)
);

CREATE TABLE faculty (
    faculty_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    name TEXT NOT NULL,
    name_raw TEXT,
    primary_unit_text TEXT,
    title TEXT,
    research_direction TEXT,
    homepage_url TEXT,
    orcid TEXT,
    biography TEXT,
    ai_tag TEXT NOT NULL DEFAULT 'unknown' CHECK (ai_tag IN ('yes','no','unknown')),
    language_tag TEXT NOT NULL DEFAULT 'unknown' CHECK (language_tag IN ('yes','no','unknown')),
    interdisciplinary_tag TEXT NOT NULL DEFAULT 'unknown' CHECK (interdisciplinary_tag IN ('yes','no','unknown')),
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE faculty_organization (
    faculty_organization_id TEXT NOT NULL PRIMARY KEY,
    faculty_id TEXT NOT NULL REFERENCES faculty(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    organization_id TEXT NOT NULL REFERENCES organizations(organization_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    role_title TEXT,
    unit_text TEXT,
    is_primary INTEGER CHECK (is_primary IS NULL OR is_primary IN (0,1)),
    start_date TEXT,
    end_date TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE practice (
    practice_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    program_id TEXT REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    scope_type TEXT NOT NULL
        CHECK (scope_type IN ('program','university','cross_program','pending_review')),
    practice_type TEXT,
    name TEXT NOT NULL,
    duration TEXT,
    credits REAL,
    credit_system TEXT,
    content TEXT,
    assessment TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (credits IS NULL OR credits >= 0),
    CHECK ((scope_type = 'program' AND program_id IS NOT NULL) OR scope_type <> 'program')
);

CREATE TABLE evaluation (
    evaluation_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    program_id TEXT REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    scope_type TEXT NOT NULL
        CHECK (scope_type IN ('program','university','cross_program','pending_review')),
    evaluation_type TEXT,
    method TEXT,
    criteria TEXT,
    weight TEXT,
    output TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((scope_type = 'program' AND program_id IS NOT NULL) OR scope_type <> 'program')
);

CREATE TABLE research_projects (
    project_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    project_name TEXT NOT NULL,
    project_name_en TEXT,
    project_type TEXT,
    funder TEXT,
    grant_number TEXT,
    start_date TEXT,
    end_date TEXT,
    status TEXT,
    funding_amount TEXT,
    description TEXT,
    evaluation_result TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE research_outputs (
    output_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    output_type TEXT NOT NULL DEFAULT 'other'
        CHECK (output_type IN ('paper','dataset','software','model','book','patent','software_copyright','talk','award','other')),
    title TEXT NOT NULL,
    authors_text TEXT,
    publication_date TEXT,
    publication_year INTEGER,
    venue TEXT,
    volume_issue_pages TEXT,
    doi TEXT,
    url TEXT,
    version TEXT,
    license TEXT,
    description TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (publication_year IS NULL OR publication_year BETWEEN 1000 AND 9999)
);

CREATE TABLE student_development (
    development_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    program_id TEXT REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    scope_type TEXT NOT NULL
        CHECK (scope_type IN ('program','university','cross_program','pending_review')),
    organization_id TEXT REFERENCES organizations(organization_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    faculty_id TEXT REFERENCES faculty(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    record_type TEXT NOT NULL
        CHECK (record_type IN ('student_research','project_output','competition','further_study','employment','alumni','group_development')),
    subject_type TEXT NOT NULL CHECK (subject_type IN ('individual','group','cohort')),
    person_name_public TEXT,
    student_status TEXT,
    degree_level TEXT,
    study_period TEXT,
    content TEXT,
    achievement TEXT,
    destination_type TEXT,
    destination_text TEXT,
    destination_organization TEXT,
    destination_role TEXT,
    event_year INTEGER,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((scope_type = 'program' AND program_id IS NOT NULL) OR scope_type <> 'program'),
    CHECK (event_year IS NULL OR event_year BETWEEN 1000 AND 9999)
);

CREATE TABLE import_batches (
    batch_id TEXT NOT NULL PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    input_manifest_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(input_manifest_json)),
    file_count INTEGER NOT NULL DEFAULT 0 CHECK (file_count >= 0),
    parser_version TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('started','parsed','imported','validated','failed','rolled_back')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    quality_report_path TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE attachments (
    attachment_id TEXT NOT NULL PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_id TEXT REFERENCES sources(source_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    attachment_type TEXT NOT NULL
        CHECK (attachment_type IN ('raw_docx','official_pdf','handbook','curriculum','other')),
    file_name TEXT NOT NULL,
    local_path TEXT,
    official_url TEXT,
    mime_type TEXT,
    file_hash TEXT,
    file_size_bytes INTEGER,
    page_count INTEGER,
    language TEXT,
    access_date TEXT,
    storage_status TEXT NOT NULL
        CHECK (storage_status IN ('local_copy_present','official_link_only','unavailable')),
    download_permission TEXT NOT NULL DEFAULT 'unknown'
        CHECK (download_permission IN ('allowed','official_link_only','unknown')),
    extraction_status TEXT NOT NULL DEFAULT 'registered_only',
    note TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (file_hash IS NULL OR length(file_hash) = 64),
    CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    CHECK (page_count IS NULL OR page_count >= 0)
);

CREATE TABLE raw_fragments (
    fragment_id TEXT NOT NULL PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source_id TEXT REFERENCES sources(source_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    attachment_id TEXT NOT NULL REFERENCES attachments(attachment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    university_id TEXT NOT NULL REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    parent_fragment_id TEXT REFERENCES raw_fragments(fragment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    sequence_no INTEGER NOT NULL,
    content_type TEXT NOT NULL
        CHECK (content_type IN ('heading','paragraph','table_row','caption','pdf_text')),
    heading_level INTEGER,
    heading_text TEXT,
    heading_path TEXT,
    level_hint TEXT,
    program_hint TEXT,
    content_text TEXT NOT NULL,
    content_json TEXT CHECK (content_json IS NULL OR json_valid(content_json)),
    table_index INTEGER,
    row_index INTEGER,
    locator TEXT,
    parse_confidence REAL CHECK (parse_confidence IS NULL OR parse_confidence BETWEEN 0 AND 1),
    disposition TEXT NOT NULL DEFAULT 'unprocessed'
        CHECK (disposition IN ('mapped','raw_only','issue_created','unprocessed')),
    disposition_note TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (attachment_id, sequence_no)
);

CREATE TABLE research_project_links (
    project_link_id TEXT NOT NULL PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES research_projects(project_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    faculty_id TEXT REFERENCES faculty(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    organization_id TEXT REFERENCES organizations(organization_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    program_id TEXT REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    relation_role TEXT,
    linked_name_raw TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((faculty_id IS NOT NULL) + (organization_id IS NOT NULL) + (program_id IS NOT NULL) <= 1),
    CHECK ((faculty_id IS NOT NULL) + (organization_id IS NOT NULL) + (program_id IS NOT NULL) = 1
           OR (linked_name_raw IS NOT NULL AND length(trim(linked_name_raw)) > 0))
);

CREATE TABLE research_output_links (
    output_link_id TEXT NOT NULL PRIMARY KEY,
    output_id TEXT NOT NULL REFERENCES research_outputs(output_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    faculty_id TEXT REFERENCES faculty(faculty_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    organization_id TEXT REFERENCES organizations(organization_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    program_id TEXT REFERENCES programs(program_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    relation_role TEXT,
    author_order INTEGER,
    linked_name_raw TEXT,
    raw_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft','pending_review','verified','conflict')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((faculty_id IS NOT NULL) + (organization_id IS NOT NULL) + (program_id IS NOT NULL) <= 1),
    CHECK ((faculty_id IS NOT NULL) + (organization_id IS NOT NULL) + (program_id IS NOT NULL) = 1
           OR (linked_name_raw IS NOT NULL AND length(trim(linked_name_raw)) > 0))
);

CREATE TABLE source_links (
    link_id TEXT NOT NULL PRIMARY KEY,
    source_id TEXT REFERENCES sources(source_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    attachment_id TEXT REFERENCES attachments(attachment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    fragment_id TEXT REFERENCES raw_fragments(fragment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    dimension TEXT CHECK (dimension IS NULL OR dimension IN
        ('培养目标','课程体系','师资配置','实践环节','评价机制','科研平台与相关机构',
         'research_projects','research_outputs','student_development','university_overview','program_overview')),
    relation_type TEXT NOT NULL
        CHECK (relation_type IN ('compiled_origin','official_verification','supporting','attachment','translation')),
    locator TEXT,
    evidence_quote TEXT,
    is_primary INTEGER CHECK (is_primary IS NULL OR is_primary IN (0,1)),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (source_id IS NOT NULL OR attachment_id IS NOT NULL OR fragment_id IS NOT NULL)
);

CREATE TABLE review_issues (
    issue_id TEXT NOT NULL PRIMARY KEY,
    batch_id TEXT REFERENCES import_batches(batch_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    university_id TEXT REFERENCES universities(university_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    entity_type TEXT,
    entity_id TEXT,
    fragment_id TEXT REFERENCES raw_fragments(fragment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    field_name TEXT,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('high','medium','low')),
    description TEXT NOT NULL,
    suggested_action TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','in_review','resolved','accepted','rejected')),
    resolution_note TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    resolved_at TEXT,
    CHECK ((entity_type IS NULL AND entity_id IS NULL) OR (entity_type IS NOT NULL AND entity_id IS NOT NULL)),
    CHECK (status NOT IN ('resolved','accepted','rejected') OR
           (resolution_note IS NOT NULL AND length(trim(resolution_note)) > 0))
);

CREATE UNIQUE INDEX ux_universities_name_cn ON universities(university_name_cn);
CREATE INDEX idx_universities_status ON universities(data_status, review_status);
CREATE INDEX idx_sources_university ON sources(university_id, verification_status);
CREATE INDEX idx_sources_url ON sources(url);
CREATE INDEX idx_organizations_university ON organizations(university_id, review_status);
CREATE INDEX idx_organizations_parent ON organizations(parent_organization_id);
CREATE INDEX idx_programs_university ON programs(university_id, parent_program_id, program_kind, level);
CREATE INDEX idx_programs_host_org ON programs(host_organization_id);
CREATE INDEX idx_objectives_program ON objectives(program_id, university_id, review_status);
CREATE INDEX idx_courses_university ON courses(university_id, review_status);
CREATE INDEX idx_courses_code ON courses(university_id, course_code);
CREATE INDEX idx_courses_names ON courses(university_id, course_name_en, course_name_zh);
CREATE INDEX idx_program_course_program ON program_course(program_id);
CREATE INDEX idx_program_course_course ON program_course(course_id);
CREATE UNIQUE INDEX ux_program_course_dedup ON program_course(
    program_id, course_id, coalesce(stage,''), coalesce(semester,''),
    coalesce(academic_year,''), coalesce(module,''), coalesce(required_elective,'')
);
CREATE INDEX idx_faculty_university ON faculty(university_id, review_status);
CREATE INDEX idx_faculty_homepage ON faculty(homepage_url);
CREATE INDEX idx_faculty_orcid ON faculty(orcid);
CREATE INDEX idx_faculty_organization_faculty ON faculty_organization(faculty_id);
CREATE INDEX idx_faculty_organization_org ON faculty_organization(organization_id);
CREATE UNIQUE INDEX ux_faculty_organization_dedup ON faculty_organization(
    faculty_id, organization_id, coalesce(role_title,''), coalesce(start_date,'')
);
CREATE INDEX idx_practice_program ON practice(program_id, university_id, review_status);
CREATE INDEX idx_evaluation_program ON evaluation(program_id, university_id, review_status);
CREATE INDEX idx_research_projects_university ON research_projects(university_id, review_status);
CREATE INDEX idx_research_outputs_university ON research_outputs(university_id, review_status);
CREATE UNIQUE INDEX ux_research_outputs_doi ON research_outputs(university_id, doi) WHERE doi IS NOT NULL;
CREATE INDEX idx_student_development_university ON student_development(university_id, review_status);
CREATE INDEX idx_student_development_program ON student_development(program_id);
CREATE INDEX idx_import_batches_university ON import_batches(university_id, status);
CREATE INDEX idx_attachments_university ON attachments(university_id, batch_id);
CREATE INDEX idx_attachments_hash ON attachments(file_hash);
CREATE INDEX idx_raw_fragments_attachment ON raw_fragments(attachment_id, sequence_no);
CREATE INDEX idx_raw_fragments_parent ON raw_fragments(parent_fragment_id);
CREATE INDEX idx_raw_fragments_disposition ON raw_fragments(university_id, disposition);
CREATE INDEX idx_research_project_links_project ON research_project_links(project_id);
CREATE INDEX idx_research_project_links_faculty ON research_project_links(faculty_id);
CREATE INDEX idx_research_project_links_org ON research_project_links(organization_id);
CREATE INDEX idx_research_output_links_output ON research_output_links(output_id);
CREATE INDEX idx_research_output_links_faculty ON research_output_links(faculty_id);
CREATE INDEX idx_source_links_target ON source_links(entity_type, entity_id);
CREATE INDEX idx_source_links_source ON source_links(source_id);
CREATE INDEX idx_source_links_attachment ON source_links(attachment_id);
CREATE INDEX idx_source_links_fragment ON source_links(fragment_id);
CREATE UNIQUE INDEX ux_source_links_dedup ON source_links(
    entity_type, entity_id, coalesce(source_id,''), coalesce(attachment_id,''),
    coalesce(fragment_id,''), relation_type, coalesce(locator,'')
);
CREATE INDEX idx_review_issues_university ON review_issues(university_id, status, severity);
CREATE INDEX idx_review_issues_target ON review_issues(entity_type, entity_id);
CREATE INDEX idx_review_issues_fragment ON review_issues(fragment_id);

CREATE VIEW v_university_dimension_counts AS
SELECT u.university_id, u.university_name_cn, u.data_status,
    (SELECT count(*) FROM programs p WHERE p.university_id=u.university_id) AS program_count,
    (SELECT count(*) FROM objectives x WHERE x.university_id=u.university_id) AS objectives_count,
    (SELECT count(*) FROM courses x WHERE x.university_id=u.university_id) AS courses_count,
    (SELECT count(*) FROM faculty x WHERE x.university_id=u.university_id) AS faculty_count,
    (SELECT count(*) FROM practice x WHERE x.university_id=u.university_id) AS practice_count,
    (SELECT count(*) FROM evaluation x WHERE x.university_id=u.university_id) AS evaluation_count,
    (SELECT count(*) FROM organizations x WHERE x.university_id=u.university_id) AS organizations_count,
    (SELECT count(*) FROM research_projects x WHERE x.university_id=u.university_id) AS research_projects_count,
    (SELECT count(*) FROM research_outputs x WHERE x.university_id=u.university_id) AS research_outputs_count,
    (SELECT count(*) FROM student_development x WHERE x.university_id=u.university_id) AS student_development_count,
    (SELECT count(*) FROM attachments x WHERE x.university_id=u.university_id) AS attachment_count
FROM universities u;

CREATE VIEW v_business_records AS
SELECT 'programs' AS entity_type, program_id AS entity_id, university_id, review_status FROM programs
UNION ALL SELECT 'objectives', objective_id, university_id, review_status FROM objectives
UNION ALL SELECT 'courses', course_id, university_id, review_status FROM courses
UNION ALL SELECT 'faculty', faculty_id, university_id, review_status FROM faculty
UNION ALL SELECT 'practice', practice_id, university_id, review_status FROM practice
UNION ALL SELECT 'evaluation', evaluation_id, university_id, review_status FROM evaluation
UNION ALL SELECT 'organizations', organization_id, university_id, review_status FROM organizations
UNION ALL SELECT 'research_projects', project_id, university_id, review_status FROM research_projects
UNION ALL SELECT 'research_outputs', output_id, university_id, review_status FROM research_outputs
UNION ALL SELECT 'student_development', development_id, university_id, review_status FROM student_development;

CREATE VIEW v_source_traceability AS
WITH b AS (
    SELECT university_id, count(*) AS business_records,
           sum(CASE WHEN review_status='verified' THEN 1 ELSE 0 END) AS verified_records
    FROM v_business_records GROUP BY university_id
), e AS (
    SELECT br.university_id,
        count(DISTINCT br.entity_type || ':' || br.entity_id) AS evidence_records,
        count(DISTINCT CASE WHEN sl.relation_type='compiled_origin' THEN br.entity_type || ':' || br.entity_id END) AS compiled_origin_records,
        count(DISTINCT CASE WHEN sl.relation_type='official_verification' AND s.is_official=1 AND s.verification_status='verified'
                            THEN br.entity_type || ':' || br.entity_id END) AS official_verified_records
    FROM v_business_records br
    JOIN source_links sl ON sl.entity_type=br.entity_type AND sl.entity_id=br.entity_id
    LEFT JOIN sources s ON s.source_id=sl.source_id
    GROUP BY br.university_id
)
SELECT u.university_id, u.university_name_cn,
    coalesce(b.business_records,0) AS business_records,
    coalesce(b.verified_records,0) AS verified_records,
    coalesce(e.evidence_records,0) AS evidence_records,
    coalesce(e.compiled_origin_records,0) AS compiled_origin_records,
    coalesce(e.official_verified_records,0) AS official_verified_records,
    CASE WHEN coalesce(b.business_records,0)=0 THEN 0.0
         ELSE round(100.0*coalesce(e.evidence_records,0)/b.business_records,2) END AS evidence_coverage_percent,
    CASE WHEN coalesce(b.business_records,0)=0 THEN 0.0
         ELSE round(100.0*coalesce(e.official_verified_records,0)/b.business_records,2) END AS official_verified_percent
FROM universities u
LEFT JOIN b ON b.university_id=u.university_id
LEFT JOIN e ON e.university_id=u.university_id;

CREATE VIEW v_university_quality AS
SELECT c.university_id, c.university_name_cn, c.data_status,
    c.program_count,
    ((c.objectives_count>0)+(c.courses_count>0)+(c.faculty_count>0)+
     (c.practice_count>0)+(c.evaluation_count>0)+(c.organizations_count>0)) AS dimension_coverage_count,
    round(100.0*((c.objectives_count>0)+(c.courses_count>0)+(c.faculty_count>0)+
     (c.practice_count>0)+(c.evaluation_count>0)+(c.organizations_count>0))/6.0,2) AS dimension_coverage_percent,
    t.business_records, t.verified_records, t.evidence_records,
    t.evidence_coverage_percent, t.official_verified_percent,
    (SELECT count(*) FROM review_issues ri WHERE ri.university_id=c.university_id AND ri.status IN ('open','in_review')) AS open_issue_count,
    (SELECT count(*) FROM raw_fragments rf WHERE rf.university_id=c.university_id AND rf.disposition='unprocessed') AS unprocessed_fragment_count,
    CASE
        WHEN c.data_status='not_started' THEN 'not_started'
        WHEN t.evidence_records < t.business_records THEN 'needs_evidence'
        WHEN t.verified_records < t.business_records THEN 'pending_review'
        WHEN (SELECT count(*) FROM review_issues ri WHERE ri.university_id=c.university_id AND ri.status IN ('open','in_review'))>0 THEN 'pending_review'
        WHEN (SELECT count(*) FROM raw_fragments rf WHERE rf.university_id=c.university_id AND rf.disposition='unprocessed')>0 THEN 'pending_review'
        ELSE 'reviewed'
    END AS quality_status
FROM v_university_dimension_counts c
JOIN v_source_traceability t ON t.university_id=c.university_id;

CREATE VIEW v_pending_review AS
SELECT university_id, severity, issue_type, status, count(*) AS issue_count
FROM review_issues
GROUP BY university_id, severity, issue_type, status;

CREATE VIEW v_duplicate_candidates AS
SELECT issue_id, university_id, entity_type, entity_id, field_name,
       description, suggested_action, status, resolution_note, created_at, resolved_at
FROM review_issues WHERE issue_type='duplicate_candidate';

CREATE VIEW v_raw_fragment_disposition_issues AS
SELECT rf.fragment_id, rf.university_id, rf.attachment_id, rf.disposition,
       CASE
           WHEN rf.disposition='unprocessed' THEN '原文片段尚未处理'
           WHEN rf.disposition='mapped' AND NOT EXISTS (
               SELECT 1 FROM source_links sl WHERE sl.fragment_id=rf.fragment_id)
               THEN '已映射片段缺少业务证据关系'
           WHEN rf.disposition='issue_created' AND NOT EXISTS (
               SELECT 1 FROM review_issues ri WHERE ri.fragment_id=rf.fragment_id)
               THEN '待核验片段缺少核验事项'
       END AS problem
FROM raw_fragments rf
WHERE rf.disposition='unprocessed'
   OR (rf.disposition='mapped' AND NOT EXISTS (SELECT 1 FROM source_links sl WHERE sl.fragment_id=rf.fragment_id))
   OR (rf.disposition='issue_created' AND NOT EXISTS (SELECT 1 FROM review_issues ri WHERE ri.fragment_id=rf.fragment_id));

CREATE VIEW v_legacy_universities AS
SELECT university_id, university_name_cn, university_name_en, country, region,
    university_type, ranking_info,
    CASE WHEN json_valid(raw_text) AND json_extract(raw_text,'$.official_website') IS NOT NULL
         THEN json_extract(raw_text,'$.official_website') ELSE official_website END AS official_website,
    collection_year,
    CASE data_status WHEN 'not_started' THEN '未开始' WHEN 'extracted' THEN '已结构化'
         WHEN 'partial' THEN '部分结构化' WHEN 'reviewed' THEN '已核验' END AS data_status,
    completeness,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.source_id') END AS source_id
FROM universities WHERE data_status<>'not_started';

CREATE VIEW v_legacy_programs AS
SELECT program_id, university_id, level, program_name_cn, program_name_en,
    CASE WHEN json_valid(raw_text) AND json_extract(raw_text,'$.degree') IS NOT NULL
         THEN json_extract(raw_text,'$.degree') ELSE degree END AS degree,
    duration, language_of_instruction, entry_level, admission_summary, positioning, program_size,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.source_id') END AS source_id
FROM programs;

CREATE VIEW v_legacy_objectives AS
SELECT objective_id, program_id, dimension, description,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.source_id') END AS source_id
FROM objectives;

CREATE VIEW v_legacy_courses AS
SELECT c.course_id, c.university_id,
    COALESCE((SELECT pc.program_id FROM program_course pc WHERE pc.course_id=c.course_id ORDER BY pc.program_course_id LIMIT 1),
             CASE WHEN json_valid(c.raw_text) THEN json_extract(c.raw_text,'$.program_id') END) AS program_id,
    c.course_name,
    (SELECT pc.module FROM program_course pc WHERE pc.course_id=c.course_id ORDER BY pc.program_course_id LIMIT 1) AS module,
    (SELECT pc.semester FROM program_course pc WHERE pc.course_id=c.course_id ORDER BY pc.program_course_id LIMIT 1) AS semester,
    (SELECT pc.credits FROM program_course pc WHERE pc.course_id=c.course_id ORDER BY pc.program_course_id LIMIT 1) AS ects,
    (SELECT pc.lecture_hours FROM program_course pc WHERE pc.course_id=c.course_id ORDER BY pc.program_course_id LIMIT 1) AS lecture_hours,
    (SELECT pc.directed_study_hours FROM program_course pc WHERE pc.course_id=c.course_id ORDER BY pc.program_course_id LIMIT 1) AS directed_study_hours,
    (SELECT pc.practical_hours FROM program_course pc WHERE pc.course_id=c.course_id ORDER BY pc.program_course_id LIMIT 1) AS practical_hours,
    CASE WHEN json_valid(c.raw_text) AND json_extract(c.raw_text,'$.ai_tag') IS NOT NULL THEN json_extract(c.raw_text,'$.ai_tag')
         ELSE CASE c.ai_tag WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END END AS ai_tag,
    CASE WHEN json_valid(c.raw_text) AND json_extract(c.raw_text,'$.language_tag') IS NOT NULL THEN json_extract(c.raw_text,'$.language_tag')
         ELSE CASE c.language_tag WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END END AS language_tag,
    CASE WHEN json_valid(c.raw_text) AND json_extract(c.raw_text,'$.practice_tag') IS NOT NULL THEN json_extract(c.raw_text,'$.practice_tag')
         ELSE CASE c.practice_tag WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END END AS practice_tag,
    CASE WHEN json_valid(c.raw_text) THEN json_extract(c.raw_text,'$.source_id') END AS source_id
FROM courses c;

CREATE VIEW v_legacy_faculty AS
SELECT faculty_id, university_id, name, primary_unit_text AS organization, title, research_direction,
    CASE ai_tag WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END AS ai_tag,
    CASE language_tag WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END AS language_tag,
    CASE interdisciplinary_tag WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END AS interdisciplinary_tag,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.source_id') END AS source_id
FROM faculty;

CREATE VIEW v_legacy_practice AS
SELECT practice_id, university_id, program_id, practice_type, name, duration, credits, content, assessment,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.source_id') END AS source_id
FROM practice;

CREATE VIEW v_legacy_evaluation AS
SELECT evaluation_id, university_id, program_id, evaluation_type, method, criteria, weight, output,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.source_id') END AS source_id
FROM evaluation;

CREATE VIEW v_legacy_organizations AS
SELECT organization_id, university_id, name, org_type, parent_org_text AS parent_org,
    CASE ai_related WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END AS ai_related,
    CASE language_related WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END AS language_related,
    CASE interdisciplinary WHEN 'yes' THEN '是' WHEN 'no' THEN '否' ELSE '待核验' END AS interdisciplinary,
    description,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.source_id') END AS source_id
FROM organizations;

CREATE VIEW v_legacy_sources AS
SELECT source_id, university_id,
    CASE WHEN json_valid(raw_text) AND json_extract(raw_text,'$.source_type') IS NOT NULL
         THEN json_extract(raw_text,'$.source_type') ELSE source_type END AS source_type,
    source_name,
    CASE WHEN json_valid(raw_text) AND json_extract(raw_text,'$.url') IS NOT NULL
         THEN json_extract(raw_text,'$.url') ELSE url END AS url,
    CASE WHEN json_valid(raw_text) AND json_extract(raw_text,'$.access_date') IS NOT NULL
         THEN json_extract(raw_text,'$.access_date') ELSE access_date END AS access_date,
    CASE WHEN json_valid(raw_text) THEN json_extract(raw_text,'$.mapped_dimensions') END AS mapped_dimensions,
    CASE WHEN json_valid(raw_text) AND json_extract(raw_text,'$.note') IS NOT NULL
         THEN json_extract(raw_text,'$.note') ELSE note END AS note
FROM sources
WHERE json_valid(raw_text) AND json_extract(raw_text,'$.mapped_dimensions') IS NOT NULL;

CREATE VIEW v_export_counts AS
SELECT 'universities' AS table_name, count(*) AS record_count FROM universities
UNION ALL SELECT 'programs', count(*) FROM programs
UNION ALL SELECT 'objectives', count(*) FROM objectives
UNION ALL SELECT 'courses', count(*) FROM courses
UNION ALL SELECT 'faculty', count(*) FROM faculty
UNION ALL SELECT 'practice', count(*) FROM practice
UNION ALL SELECT 'evaluation', count(*) FROM evaluation
UNION ALL SELECT 'organizations', count(*) FROM organizations
UNION ALL SELECT 'sources', count(*) FROM sources
UNION ALL SELECT 'program_course', count(*) FROM program_course
UNION ALL SELECT 'faculty_organization', count(*) FROM faculty_organization
UNION ALL SELECT 'research_projects', count(*) FROM research_projects
UNION ALL SELECT 'research_project_links', count(*) FROM research_project_links
UNION ALL SELECT 'research_outputs', count(*) FROM research_outputs
UNION ALL SELECT 'research_output_links', count(*) FROM research_output_links
UNION ALL SELECT 'student_development', count(*) FROM student_development
UNION ALL SELECT 'attachments', count(*) FROM attachments
UNION ALL SELECT 'raw_fragments', count(*) FROM raw_fragments
UNION ALL SELECT 'source_links', count(*) FROM source_links
UNION ALL SELECT 'review_issues', count(*) FROM review_issues
UNION ALL SELECT 'import_batches', count(*) FROM import_batches;

-- Generic evidence targets: validate known table names and existing primary keys.

CREATE TRIGGER trg_source_links_target_insert
BEFORE INSERT ON source_links
FOR EACH ROW
WHEN NEW.entity_type IS NOT NULL AND (
    NEW.entity_type NOT IN ('universities', 'programs', 'objectives', 'courses', 'faculty', 'practice', 'evaluation', 'organizations', 'sources', 'program_course', 'faculty_organization', 'research_projects', 'research_project_links', 'research_outputs', 'research_output_links', 'student_development', 'attachments', 'raw_fragments', 'import_batches')
    OR (NEW.entity_type='universities' AND NOT EXISTS (SELECT 1 FROM universities t WHERE t.university_id=NEW.entity_id))
    OR (NEW.entity_type='programs' AND NOT EXISTS (SELECT 1 FROM programs t WHERE t.program_id=NEW.entity_id))
    OR (NEW.entity_type='objectives' AND NOT EXISTS (SELECT 1 FROM objectives t WHERE t.objective_id=NEW.entity_id))
    OR (NEW.entity_type='courses' AND NOT EXISTS (SELECT 1 FROM courses t WHERE t.course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty' AND NOT EXISTS (SELECT 1 FROM faculty t WHERE t.faculty_id=NEW.entity_id))
    OR (NEW.entity_type='practice' AND NOT EXISTS (SELECT 1 FROM practice t WHERE t.practice_id=NEW.entity_id))
    OR (NEW.entity_type='evaluation' AND NOT EXISTS (SELECT 1 FROM evaluation t WHERE t.evaluation_id=NEW.entity_id))
    OR (NEW.entity_type='organizations' AND NOT EXISTS (SELECT 1 FROM organizations t WHERE t.organization_id=NEW.entity_id))
    OR (NEW.entity_type='sources' AND NOT EXISTS (SELECT 1 FROM sources t WHERE t.source_id=NEW.entity_id))
    OR (NEW.entity_type='program_course' AND NOT EXISTS (SELECT 1 FROM program_course t WHERE t.program_course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty_organization' AND NOT EXISTS (SELECT 1 FROM faculty_organization t WHERE t.faculty_organization_id=NEW.entity_id))
    OR (NEW.entity_type='research_projects' AND NOT EXISTS (SELECT 1 FROM research_projects t WHERE t.project_id=NEW.entity_id))
    OR (NEW.entity_type='research_project_links' AND NOT EXISTS (SELECT 1 FROM research_project_links t WHERE t.project_link_id=NEW.entity_id))
    OR (NEW.entity_type='research_outputs' AND NOT EXISTS (SELECT 1 FROM research_outputs t WHERE t.output_id=NEW.entity_id))
    OR (NEW.entity_type='research_output_links' AND NOT EXISTS (SELECT 1 FROM research_output_links t WHERE t.output_link_id=NEW.entity_id))
    OR (NEW.entity_type='student_development' AND NOT EXISTS (SELECT 1 FROM student_development t WHERE t.development_id=NEW.entity_id))
    OR (NEW.entity_type='attachments' AND NOT EXISTS (SELECT 1 FROM attachments t WHERE t.attachment_id=NEW.entity_id))
    OR (NEW.entity_type='raw_fragments' AND NOT EXISTS (SELECT 1 FROM raw_fragments t WHERE t.fragment_id=NEW.entity_id))
    OR (NEW.entity_type='import_batches' AND NOT EXISTS (SELECT 1 FROM import_batches t WHERE t.batch_id=NEW.entity_id))
)
BEGIN
SELECT RAISE(ABORT, 'source_links: target table or record is invalid');
END;


CREATE TRIGGER trg_source_links_target_update
BEFORE UPDATE ON source_links
FOR EACH ROW
WHEN NEW.entity_type IS NOT NULL AND (
    NEW.entity_type NOT IN ('universities', 'programs', 'objectives', 'courses', 'faculty', 'practice', 'evaluation', 'organizations', 'sources', 'program_course', 'faculty_organization', 'research_projects', 'research_project_links', 'research_outputs', 'research_output_links', 'student_development', 'attachments', 'raw_fragments', 'import_batches')
    OR (NEW.entity_type='universities' AND NOT EXISTS (SELECT 1 FROM universities t WHERE t.university_id=NEW.entity_id))
    OR (NEW.entity_type='programs' AND NOT EXISTS (SELECT 1 FROM programs t WHERE t.program_id=NEW.entity_id))
    OR (NEW.entity_type='objectives' AND NOT EXISTS (SELECT 1 FROM objectives t WHERE t.objective_id=NEW.entity_id))
    OR (NEW.entity_type='courses' AND NOT EXISTS (SELECT 1 FROM courses t WHERE t.course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty' AND NOT EXISTS (SELECT 1 FROM faculty t WHERE t.faculty_id=NEW.entity_id))
    OR (NEW.entity_type='practice' AND NOT EXISTS (SELECT 1 FROM practice t WHERE t.practice_id=NEW.entity_id))
    OR (NEW.entity_type='evaluation' AND NOT EXISTS (SELECT 1 FROM evaluation t WHERE t.evaluation_id=NEW.entity_id))
    OR (NEW.entity_type='organizations' AND NOT EXISTS (SELECT 1 FROM organizations t WHERE t.organization_id=NEW.entity_id))
    OR (NEW.entity_type='sources' AND NOT EXISTS (SELECT 1 FROM sources t WHERE t.source_id=NEW.entity_id))
    OR (NEW.entity_type='program_course' AND NOT EXISTS (SELECT 1 FROM program_course t WHERE t.program_course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty_organization' AND NOT EXISTS (SELECT 1 FROM faculty_organization t WHERE t.faculty_organization_id=NEW.entity_id))
    OR (NEW.entity_type='research_projects' AND NOT EXISTS (SELECT 1 FROM research_projects t WHERE t.project_id=NEW.entity_id))
    OR (NEW.entity_type='research_project_links' AND NOT EXISTS (SELECT 1 FROM research_project_links t WHERE t.project_link_id=NEW.entity_id))
    OR (NEW.entity_type='research_outputs' AND NOT EXISTS (SELECT 1 FROM research_outputs t WHERE t.output_id=NEW.entity_id))
    OR (NEW.entity_type='research_output_links' AND NOT EXISTS (SELECT 1 FROM research_output_links t WHERE t.output_link_id=NEW.entity_id))
    OR (NEW.entity_type='student_development' AND NOT EXISTS (SELECT 1 FROM student_development t WHERE t.development_id=NEW.entity_id))
    OR (NEW.entity_type='attachments' AND NOT EXISTS (SELECT 1 FROM attachments t WHERE t.attachment_id=NEW.entity_id))
    OR (NEW.entity_type='raw_fragments' AND NOT EXISTS (SELECT 1 FROM raw_fragments t WHERE t.fragment_id=NEW.entity_id))
    OR (NEW.entity_type='import_batches' AND NOT EXISTS (SELECT 1 FROM import_batches t WHERE t.batch_id=NEW.entity_id))
)
BEGIN
SELECT RAISE(ABORT, 'source_links: target table or record is invalid');
END;


CREATE TRIGGER trg_review_issues_target_insert
BEFORE INSERT ON review_issues
FOR EACH ROW
WHEN NEW.entity_type IS NOT NULL AND (
    NEW.entity_type NOT IN ('universities', 'programs', 'objectives', 'courses', 'faculty', 'practice', 'evaluation', 'organizations', 'sources', 'program_course', 'faculty_organization', 'research_projects', 'research_project_links', 'research_outputs', 'research_output_links', 'student_development', 'attachments', 'raw_fragments', 'import_batches')
    OR (NEW.entity_type='universities' AND NOT EXISTS (SELECT 1 FROM universities t WHERE t.university_id=NEW.entity_id))
    OR (NEW.entity_type='programs' AND NOT EXISTS (SELECT 1 FROM programs t WHERE t.program_id=NEW.entity_id))
    OR (NEW.entity_type='objectives' AND NOT EXISTS (SELECT 1 FROM objectives t WHERE t.objective_id=NEW.entity_id))
    OR (NEW.entity_type='courses' AND NOT EXISTS (SELECT 1 FROM courses t WHERE t.course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty' AND NOT EXISTS (SELECT 1 FROM faculty t WHERE t.faculty_id=NEW.entity_id))
    OR (NEW.entity_type='practice' AND NOT EXISTS (SELECT 1 FROM practice t WHERE t.practice_id=NEW.entity_id))
    OR (NEW.entity_type='evaluation' AND NOT EXISTS (SELECT 1 FROM evaluation t WHERE t.evaluation_id=NEW.entity_id))
    OR (NEW.entity_type='organizations' AND NOT EXISTS (SELECT 1 FROM organizations t WHERE t.organization_id=NEW.entity_id))
    OR (NEW.entity_type='sources' AND NOT EXISTS (SELECT 1 FROM sources t WHERE t.source_id=NEW.entity_id))
    OR (NEW.entity_type='program_course' AND NOT EXISTS (SELECT 1 FROM program_course t WHERE t.program_course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty_organization' AND NOT EXISTS (SELECT 1 FROM faculty_organization t WHERE t.faculty_organization_id=NEW.entity_id))
    OR (NEW.entity_type='research_projects' AND NOT EXISTS (SELECT 1 FROM research_projects t WHERE t.project_id=NEW.entity_id))
    OR (NEW.entity_type='research_project_links' AND NOT EXISTS (SELECT 1 FROM research_project_links t WHERE t.project_link_id=NEW.entity_id))
    OR (NEW.entity_type='research_outputs' AND NOT EXISTS (SELECT 1 FROM research_outputs t WHERE t.output_id=NEW.entity_id))
    OR (NEW.entity_type='research_output_links' AND NOT EXISTS (SELECT 1 FROM research_output_links t WHERE t.output_link_id=NEW.entity_id))
    OR (NEW.entity_type='student_development' AND NOT EXISTS (SELECT 1 FROM student_development t WHERE t.development_id=NEW.entity_id))
    OR (NEW.entity_type='attachments' AND NOT EXISTS (SELECT 1 FROM attachments t WHERE t.attachment_id=NEW.entity_id))
    OR (NEW.entity_type='raw_fragments' AND NOT EXISTS (SELECT 1 FROM raw_fragments t WHERE t.fragment_id=NEW.entity_id))
    OR (NEW.entity_type='import_batches' AND NOT EXISTS (SELECT 1 FROM import_batches t WHERE t.batch_id=NEW.entity_id))
)
BEGIN
SELECT RAISE(ABORT, 'review_issues: target table or record is invalid');
END;


CREATE TRIGGER trg_review_issues_target_update
BEFORE UPDATE ON review_issues
FOR EACH ROW
WHEN NEW.entity_type IS NOT NULL AND (
    NEW.entity_type NOT IN ('universities', 'programs', 'objectives', 'courses', 'faculty', 'practice', 'evaluation', 'organizations', 'sources', 'program_course', 'faculty_organization', 'research_projects', 'research_project_links', 'research_outputs', 'research_output_links', 'student_development', 'attachments', 'raw_fragments', 'import_batches')
    OR (NEW.entity_type='universities' AND NOT EXISTS (SELECT 1 FROM universities t WHERE t.university_id=NEW.entity_id))
    OR (NEW.entity_type='programs' AND NOT EXISTS (SELECT 1 FROM programs t WHERE t.program_id=NEW.entity_id))
    OR (NEW.entity_type='objectives' AND NOT EXISTS (SELECT 1 FROM objectives t WHERE t.objective_id=NEW.entity_id))
    OR (NEW.entity_type='courses' AND NOT EXISTS (SELECT 1 FROM courses t WHERE t.course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty' AND NOT EXISTS (SELECT 1 FROM faculty t WHERE t.faculty_id=NEW.entity_id))
    OR (NEW.entity_type='practice' AND NOT EXISTS (SELECT 1 FROM practice t WHERE t.practice_id=NEW.entity_id))
    OR (NEW.entity_type='evaluation' AND NOT EXISTS (SELECT 1 FROM evaluation t WHERE t.evaluation_id=NEW.entity_id))
    OR (NEW.entity_type='organizations' AND NOT EXISTS (SELECT 1 FROM organizations t WHERE t.organization_id=NEW.entity_id))
    OR (NEW.entity_type='sources' AND NOT EXISTS (SELECT 1 FROM sources t WHERE t.source_id=NEW.entity_id))
    OR (NEW.entity_type='program_course' AND NOT EXISTS (SELECT 1 FROM program_course t WHERE t.program_course_id=NEW.entity_id))
    OR (NEW.entity_type='faculty_organization' AND NOT EXISTS (SELECT 1 FROM faculty_organization t WHERE t.faculty_organization_id=NEW.entity_id))
    OR (NEW.entity_type='research_projects' AND NOT EXISTS (SELECT 1 FROM research_projects t WHERE t.project_id=NEW.entity_id))
    OR (NEW.entity_type='research_project_links' AND NOT EXISTS (SELECT 1 FROM research_project_links t WHERE t.project_link_id=NEW.entity_id))
    OR (NEW.entity_type='research_outputs' AND NOT EXISTS (SELECT 1 FROM research_outputs t WHERE t.output_id=NEW.entity_id))
    OR (NEW.entity_type='research_output_links' AND NOT EXISTS (SELECT 1 FROM research_output_links t WHERE t.output_link_id=NEW.entity_id))
    OR (NEW.entity_type='student_development' AND NOT EXISTS (SELECT 1 FROM student_development t WHERE t.development_id=NEW.entity_id))
    OR (NEW.entity_type='attachments' AND NOT EXISTS (SELECT 1 FROM attachments t WHERE t.attachment_id=NEW.entity_id))
    OR (NEW.entity_type='raw_fragments' AND NOT EXISTS (SELECT 1 FROM raw_fragments t WHERE t.fragment_id=NEW.entity_id))
    OR (NEW.entity_type='import_batches' AND NOT EXISTS (SELECT 1 FROM import_batches t WHERE t.batch_id=NEW.entity_id))
)
BEGIN
SELECT RAISE(ABORT, 'review_issues: target table or record is invalid');
END;


CREATE TRIGGER trg_universities_evidence_delete
BEFORE DELETE ON universities
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='universities' AND sl.entity_id=OLD.university_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='universities' AND ri.entity_id=OLD.university_id)
BEGIN
SELECT RAISE(ABORT, 'universities: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_universities_evidence_pk_update
BEFORE UPDATE OF university_id ON universities
FOR EACH ROW
WHEN NEW.university_id<>OLD.university_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='universities' AND sl.entity_id=OLD.university_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='universities' AND ri.entity_id=OLD.university_id)
)
BEGIN
SELECT RAISE(ABORT, 'universities: referenced primary key cannot change');
END;


CREATE TRIGGER trg_programs_evidence_delete
BEFORE DELETE ON programs
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='programs' AND sl.entity_id=OLD.program_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='programs' AND ri.entity_id=OLD.program_id)
BEGIN
SELECT RAISE(ABORT, 'programs: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_programs_evidence_pk_update
BEFORE UPDATE OF program_id ON programs
FOR EACH ROW
WHEN NEW.program_id<>OLD.program_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='programs' AND sl.entity_id=OLD.program_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='programs' AND ri.entity_id=OLD.program_id)
)
BEGIN
SELECT RAISE(ABORT, 'programs: referenced primary key cannot change');
END;


CREATE TRIGGER trg_objectives_evidence_delete
BEFORE DELETE ON objectives
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='objectives' AND sl.entity_id=OLD.objective_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='objectives' AND ri.entity_id=OLD.objective_id)
BEGIN
SELECT RAISE(ABORT, 'objectives: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_objectives_evidence_pk_update
BEFORE UPDATE OF objective_id ON objectives
FOR EACH ROW
WHEN NEW.objective_id<>OLD.objective_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='objectives' AND sl.entity_id=OLD.objective_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='objectives' AND ri.entity_id=OLD.objective_id)
)
BEGIN
SELECT RAISE(ABORT, 'objectives: referenced primary key cannot change');
END;


CREATE TRIGGER trg_courses_evidence_delete
BEFORE DELETE ON courses
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='courses' AND sl.entity_id=OLD.course_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='courses' AND ri.entity_id=OLD.course_id)
BEGIN
SELECT RAISE(ABORT, 'courses: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_courses_evidence_pk_update
BEFORE UPDATE OF course_id ON courses
FOR EACH ROW
WHEN NEW.course_id<>OLD.course_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='courses' AND sl.entity_id=OLD.course_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='courses' AND ri.entity_id=OLD.course_id)
)
BEGIN
SELECT RAISE(ABORT, 'courses: referenced primary key cannot change');
END;


CREATE TRIGGER trg_faculty_evidence_delete
BEFORE DELETE ON faculty
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='faculty' AND sl.entity_id=OLD.faculty_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='faculty' AND ri.entity_id=OLD.faculty_id)
BEGIN
SELECT RAISE(ABORT, 'faculty: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_faculty_evidence_pk_update
BEFORE UPDATE OF faculty_id ON faculty
FOR EACH ROW
WHEN NEW.faculty_id<>OLD.faculty_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='faculty' AND sl.entity_id=OLD.faculty_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='faculty' AND ri.entity_id=OLD.faculty_id)
)
BEGIN
SELECT RAISE(ABORT, 'faculty: referenced primary key cannot change');
END;


CREATE TRIGGER trg_practice_evidence_delete
BEFORE DELETE ON practice
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='practice' AND sl.entity_id=OLD.practice_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='practice' AND ri.entity_id=OLD.practice_id)
BEGIN
SELECT RAISE(ABORT, 'practice: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_practice_evidence_pk_update
BEFORE UPDATE OF practice_id ON practice
FOR EACH ROW
WHEN NEW.practice_id<>OLD.practice_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='practice' AND sl.entity_id=OLD.practice_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='practice' AND ri.entity_id=OLD.practice_id)
)
BEGIN
SELECT RAISE(ABORT, 'practice: referenced primary key cannot change');
END;


CREATE TRIGGER trg_evaluation_evidence_delete
BEFORE DELETE ON evaluation
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='evaluation' AND sl.entity_id=OLD.evaluation_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='evaluation' AND ri.entity_id=OLD.evaluation_id)
BEGIN
SELECT RAISE(ABORT, 'evaluation: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_evaluation_evidence_pk_update
BEFORE UPDATE OF evaluation_id ON evaluation
FOR EACH ROW
WHEN NEW.evaluation_id<>OLD.evaluation_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='evaluation' AND sl.entity_id=OLD.evaluation_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='evaluation' AND ri.entity_id=OLD.evaluation_id)
)
BEGIN
SELECT RAISE(ABORT, 'evaluation: referenced primary key cannot change');
END;


CREATE TRIGGER trg_organizations_evidence_delete
BEFORE DELETE ON organizations
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='organizations' AND sl.entity_id=OLD.organization_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='organizations' AND ri.entity_id=OLD.organization_id)
BEGIN
SELECT RAISE(ABORT, 'organizations: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_organizations_evidence_pk_update
BEFORE UPDATE OF organization_id ON organizations
FOR EACH ROW
WHEN NEW.organization_id<>OLD.organization_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='organizations' AND sl.entity_id=OLD.organization_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='organizations' AND ri.entity_id=OLD.organization_id)
)
BEGIN
SELECT RAISE(ABORT, 'organizations: referenced primary key cannot change');
END;


CREATE TRIGGER trg_sources_evidence_delete
BEFORE DELETE ON sources
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='sources' AND sl.entity_id=OLD.source_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='sources' AND ri.entity_id=OLD.source_id)
BEGIN
SELECT RAISE(ABORT, 'sources: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_sources_evidence_pk_update
BEFORE UPDATE OF source_id ON sources
FOR EACH ROW
WHEN NEW.source_id<>OLD.source_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='sources' AND sl.entity_id=OLD.source_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='sources' AND ri.entity_id=OLD.source_id)
)
BEGIN
SELECT RAISE(ABORT, 'sources: referenced primary key cannot change');
END;


CREATE TRIGGER trg_program_course_evidence_delete
BEFORE DELETE ON program_course
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='program_course' AND sl.entity_id=OLD.program_course_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='program_course' AND ri.entity_id=OLD.program_course_id)
BEGIN
SELECT RAISE(ABORT, 'program_course: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_program_course_evidence_pk_update
BEFORE UPDATE OF program_course_id ON program_course
FOR EACH ROW
WHEN NEW.program_course_id<>OLD.program_course_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='program_course' AND sl.entity_id=OLD.program_course_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='program_course' AND ri.entity_id=OLD.program_course_id)
)
BEGIN
SELECT RAISE(ABORT, 'program_course: referenced primary key cannot change');
END;


CREATE TRIGGER trg_faculty_organization_evidence_delete
BEFORE DELETE ON faculty_organization
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='faculty_organization' AND sl.entity_id=OLD.faculty_organization_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='faculty_organization' AND ri.entity_id=OLD.faculty_organization_id)
BEGIN
SELECT RAISE(ABORT, 'faculty_organization: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_faculty_organization_evidence_pk_update
BEFORE UPDATE OF faculty_organization_id ON faculty_organization
FOR EACH ROW
WHEN NEW.faculty_organization_id<>OLD.faculty_organization_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='faculty_organization' AND sl.entity_id=OLD.faculty_organization_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='faculty_organization' AND ri.entity_id=OLD.faculty_organization_id)
)
BEGIN
SELECT RAISE(ABORT, 'faculty_organization: referenced primary key cannot change');
END;


CREATE TRIGGER trg_research_projects_evidence_delete
BEFORE DELETE ON research_projects
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_projects' AND sl.entity_id=OLD.project_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_projects' AND ri.entity_id=OLD.project_id)
BEGIN
SELECT RAISE(ABORT, 'research_projects: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_research_projects_evidence_pk_update
BEFORE UPDATE OF project_id ON research_projects
FOR EACH ROW
WHEN NEW.project_id<>OLD.project_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_projects' AND sl.entity_id=OLD.project_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_projects' AND ri.entity_id=OLD.project_id)
)
BEGIN
SELECT RAISE(ABORT, 'research_projects: referenced primary key cannot change');
END;


CREATE TRIGGER trg_research_project_links_evidence_delete
BEFORE DELETE ON research_project_links
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_project_links' AND sl.entity_id=OLD.project_link_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_project_links' AND ri.entity_id=OLD.project_link_id)
BEGIN
SELECT RAISE(ABORT, 'research_project_links: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_research_project_links_evidence_pk_update
BEFORE UPDATE OF project_link_id ON research_project_links
FOR EACH ROW
WHEN NEW.project_link_id<>OLD.project_link_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_project_links' AND sl.entity_id=OLD.project_link_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_project_links' AND ri.entity_id=OLD.project_link_id)
)
BEGIN
SELECT RAISE(ABORT, 'research_project_links: referenced primary key cannot change');
END;


CREATE TRIGGER trg_research_outputs_evidence_delete
BEFORE DELETE ON research_outputs
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_outputs' AND sl.entity_id=OLD.output_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_outputs' AND ri.entity_id=OLD.output_id)
BEGIN
SELECT RAISE(ABORT, 'research_outputs: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_research_outputs_evidence_pk_update
BEFORE UPDATE OF output_id ON research_outputs
FOR EACH ROW
WHEN NEW.output_id<>OLD.output_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_outputs' AND sl.entity_id=OLD.output_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_outputs' AND ri.entity_id=OLD.output_id)
)
BEGIN
SELECT RAISE(ABORT, 'research_outputs: referenced primary key cannot change');
END;


CREATE TRIGGER trg_research_output_links_evidence_delete
BEFORE DELETE ON research_output_links
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_output_links' AND sl.entity_id=OLD.output_link_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_output_links' AND ri.entity_id=OLD.output_link_id)
BEGIN
SELECT RAISE(ABORT, 'research_output_links: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_research_output_links_evidence_pk_update
BEFORE UPDATE OF output_link_id ON research_output_links
FOR EACH ROW
WHEN NEW.output_link_id<>OLD.output_link_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='research_output_links' AND sl.entity_id=OLD.output_link_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='research_output_links' AND ri.entity_id=OLD.output_link_id)
)
BEGIN
SELECT RAISE(ABORT, 'research_output_links: referenced primary key cannot change');
END;


CREATE TRIGGER trg_student_development_evidence_delete
BEFORE DELETE ON student_development
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='student_development' AND sl.entity_id=OLD.development_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='student_development' AND ri.entity_id=OLD.development_id)
BEGIN
SELECT RAISE(ABORT, 'student_development: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_student_development_evidence_pk_update
BEFORE UPDATE OF development_id ON student_development
FOR EACH ROW
WHEN NEW.development_id<>OLD.development_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='student_development' AND sl.entity_id=OLD.development_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='student_development' AND ri.entity_id=OLD.development_id)
)
BEGIN
SELECT RAISE(ABORT, 'student_development: referenced primary key cannot change');
END;


CREATE TRIGGER trg_attachments_evidence_delete
BEFORE DELETE ON attachments
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='attachments' AND sl.entity_id=OLD.attachment_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='attachments' AND ri.entity_id=OLD.attachment_id)
BEGIN
SELECT RAISE(ABORT, 'attachments: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_attachments_evidence_pk_update
BEFORE UPDATE OF attachment_id ON attachments
FOR EACH ROW
WHEN NEW.attachment_id<>OLD.attachment_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='attachments' AND sl.entity_id=OLD.attachment_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='attachments' AND ri.entity_id=OLD.attachment_id)
)
BEGIN
SELECT RAISE(ABORT, 'attachments: referenced primary key cannot change');
END;


CREATE TRIGGER trg_raw_fragments_evidence_delete
BEFORE DELETE ON raw_fragments
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='raw_fragments' AND sl.entity_id=OLD.fragment_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='raw_fragments' AND ri.entity_id=OLD.fragment_id)
BEGIN
SELECT RAISE(ABORT, 'raw_fragments: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_raw_fragments_evidence_pk_update
BEFORE UPDATE OF fragment_id ON raw_fragments
FOR EACH ROW
WHEN NEW.fragment_id<>OLD.fragment_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='raw_fragments' AND sl.entity_id=OLD.fragment_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='raw_fragments' AND ri.entity_id=OLD.fragment_id)
)
BEGIN
SELECT RAISE(ABORT, 'raw_fragments: referenced primary key cannot change');
END;


CREATE TRIGGER trg_import_batches_evidence_delete
BEFORE DELETE ON import_batches
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='import_batches' AND sl.entity_id=OLD.batch_id)
  OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='import_batches' AND ri.entity_id=OLD.batch_id)
BEGIN
SELECT RAISE(ABORT, 'import_batches: record is referenced by evidence or review issues');
END;

CREATE TRIGGER trg_import_batches_evidence_pk_update
BEFORE UPDATE OF batch_id ON import_batches
FOR EACH ROW
WHEN NEW.batch_id<>OLD.batch_id AND (
    EXISTS (SELECT 1 FROM source_links sl WHERE sl.entity_type='import_batches' AND sl.entity_id=OLD.batch_id)
    OR EXISTS (SELECT 1 FROM review_issues ri WHERE ri.entity_type='import_batches' AND ri.entity_id=OLD.batch_id)
)
BEGIN
SELECT RAISE(ABORT, 'import_batches: referenced primary key cannot change');
END;


CREATE TRIGGER trg_source_links_fragment_consistency_insert
BEFORE INSERT ON source_links
FOR EACH ROW
WHEN NEW.fragment_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM raw_fragments rf WHERE rf.fragment_id=NEW.fragment_id
      AND ((NEW.attachment_id IS NOT NULL AND rf.attachment_id<>NEW.attachment_id)
        OR (NEW.source_id IS NOT NULL AND rf.source_id IS NOT NULL AND rf.source_id<>NEW.source_id))
)
BEGIN
SELECT RAISE(ABORT, 'source_links: fragment, attachment and source are inconsistent');
END;


CREATE TRIGGER trg_source_links_fragment_consistency_update
BEFORE UPDATE ON source_links
FOR EACH ROW
WHEN NEW.fragment_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM raw_fragments rf WHERE rf.fragment_id=NEW.fragment_id
      AND ((NEW.attachment_id IS NOT NULL AND rf.attachment_id<>NEW.attachment_id)
        OR (NEW.source_id IS NOT NULL AND rf.source_id IS NOT NULL AND rf.source_id<>NEW.source_id))
)
BEGIN
SELECT RAISE(ABORT, 'source_links: fragment, attachment and source are inconsistent');
END;

