# 世界一流大学“语言+人工智能”复合型人才培养模式案例数据库

## 专家验收版
本版本已结构化纳入4所示范高校：巴黎-萨克雷大学、宾夕法尼亚大学、东京大学、南京大学。系统提供：首页成果门户、高校级联检索、高校比较、六维分析框架、数据驾驶舱、高校二级详情页、来源追溯。

## 本地运行
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub + Streamlit Community Cloud 一键部署
1. 在 GitHub 新建仓库，例如 `language-ai-case-database`。
2. 将本文件夹中的所有内容上传到仓库根目录，务必保留 `data/` 与 `.streamlit/`。
3. 登录 Streamlit Community Cloud，选择 **Create app**。
4. 选择刚才的 GitHub 仓库和分支，Main file path 填 `app.py`。
5. 点击 Deploy。系统会自动安装 `requirements.txt` 并读取 `data/language_ai_cases.db`。
6. 部署成功后得到 `https://xxxx.streamlit.app` 公网地址，可提供给专家访问。

## 建议提交给专家的成果
- 公网演示地址（部署后填写）
- 本完整包 ZIP
- `data/language_ai_cases.xlsx`（便于专家查看结构化数据）
- `data/language_ai_cases.db`（数据库原始文件）
- 网页截图/PDF（建议正式提交前截取）
- 项目结项报告中的“数据库建设与使用说明”

## 数据口径说明
当前4所高校是用于专家验收版功能展示的已结构化案例。不同学校原始材料详略程度不同；系统不把“记录数量”解释为培养质量高低。东京大学当前材料主要聚焦 Miyao Group，因此对原材料没有明确提供的课程和评价信息不作推断补录。
