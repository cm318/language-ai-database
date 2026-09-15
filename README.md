# 世界一流大学“语言+人工智能”复合型人才培养模式案例数据库

## 专家验收部署版
本系统围绕培养目标、课程体系、师资配置、实践环节、评价机制、组织架构六个维度，对高校“语言+人工智能”复合型人才培养案例进行结构化整理，提供高校检索、跨校比较、数据驾驶舱、高校详情与来源追溯等功能。

当前在线数据包已纳入巴黎-萨克雷大学、宾夕法尼亚大学、东京大学、南京大学4所高校的结构化案例数据。各项统计由数据库实时生成，后续更新数据库后可自动同步。

## GitHub + Streamlit Community Cloud 部署
1. 新建 GitHub 仓库。
2. 将本文件夹中的内容上传到仓库根目录，保留 `data/` 目录；`.streamlit/config.toml` 为界面配置文件，可一并上传。
3. 登录 Streamlit Community Cloud 并连接 GitHub。
4. 选择该仓库，Branch 选择 `main`。
5. Main file path 填写 `app.py`。
6. 点击 Deploy。

## 主要文件
- `app.py`：网页应用入口
- `data/language_ai_cases.db`：SQLite结构化数据库
- `data/language_ai_cases.xlsx`：结构化数据工作簿
- `requirements.txt`：Python依赖
- `.streamlit/config.toml`：界面配置

## 数据说明
数据库依据已采集的高校公开资料进行结构化整理。不同高校公开资料的详略程度存在差异，因此记录数量仅表示当前数据库的结构化覆盖情况，不作为高校办学水平或培养质量评价依据。对于现有资料中未明确提供的信息，不作主观推断或补录。
