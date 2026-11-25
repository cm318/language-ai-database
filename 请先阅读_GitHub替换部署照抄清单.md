# 世界一流大学“语言＋人工智能”案例数据库
# GitHub 直接替换与 Streamlit 重新部署照抄清单

## 先说明

这个压缩包就是用于替换 GitHub 文件的公开部署包，不是本地研究归档包。

- 不需要输入 Git 命令。
- 不需要新建 GitHub 仓库：使用已有的 `cm318/language-ai-database`。
- 不要上传 ZIP 本身，必须先解压。
- 解压后应直接看到 `app.py`、`requirements.txt`、`README.md`、`data`、`.streamlit` 等。
- 包内没有 `.git`、未压缩数据库、历史备份或测试临时库。
- 公开数据库文件是 `data/language_ai_cases.db.gz`，应用启动时会自动解压并校验完整数据库。

## 一、解压并显示隐藏文件

1. 下载 `语言AI数据库_GitHub直接替换部署包.zip`。
2. 右键 ZIP，选择“全部解压”或“解压到当前文件夹”。
3. 打开解压后的文件夹，确认能看到 `app.py`。
4. Windows 文件资源管理器打开“查看 → 显示 → 隐藏的项目”；macOS 在 Finder 中按 `Command＋Shift＋.`，确保能看到 `.gitignore` 和 `.streamlit`。

## 二、按三批上传到已有 GitHub 仓库

GitHub 网页每次最多上传 100 个文件，所以严格按下面三批操作。每批都直接提交到 `main`。

打开并登录：

https://github.com/cm318/language-ai-database

### 第一批：结构、脚本和验收报告（92 个文件）

1. 在仓库首页点击 **Add file → Upload files**。
2. 从解压文件夹中，把下面三个文件夹一起拖入网页：
   - `schema`
   - `scripts`
   - `quality_reports`
3. 等待全部文件上传完成。
4. Commit message 填：`加入结构方案、维护脚本与验收报告`。
5. 选择 **Commit directly to the main branch**。
6. 点击 **Commit changes**。

### 第二批：80 份已授权附件（80 个文件）

1. 再点击 **Add file → Upload files**。
2. 把下面两个文件夹一起拖入网页：
   - `raw_files`
   - `derived`
3. 等待全部文件上传完成。
4. Commit message 填：`加入80份已授权附件`。
5. 选择 **Commit directly to the main branch**。
6. 点击 **Commit changes**。

### 第三步前：删除两个旧文件

旧仓库中的这两个文件不能保留：

```text
config.toml
data/language_ai_cases.db
```

分别处理：

1. 在 GitHub 仓库中打开旧文件。
2. 点击文件页右上角的垃圾桶图标；如果没有垃圾桶，点击 `…`，选择 **Delete file**。
3. 提交说明分别填写 `移除旧配置文件` 和 `移除旧版未压缩数据库`。
4. 直接提交到 `main`。

如果某个文件本来就不存在，跳过即可。新配置已经在 `.streamlit/config.toml`，新数据库已经改为压缩副本，不要删除这两个新文件。

### 第三批：核心程序和完整压缩数据库（11 个文件）

1. 再点击 **Add file → Upload files**。
2. 选择并上传解压文件夹根目录中的这些文件：
   - `.gitignore`
   - `README.md`
   - `部署说明.md`
   - `请先阅读_GitHub替换部署照抄清单.md`
   - `部署包校验清单.json`
   - `app.py`
   - `requirements.txt`
3. 再把下面两个文件夹一起拖入网页：
   - `.streamlit`
   - `data`
4. 确认上传列表中有：
   - `.streamlit/config.toml`
   - `data/language_ai_cases.db.gz`
   - `data/database_manifest.json`
   - `data/language_ai_cases.xlsx`
5. Commit message 填：`替换为56校V2全量部署版`。
6. 选择 **Commit directly to the main branch**。
7. 点击 **Commit changes`。

如果页面显示的是 **Propose changes** 并自动创建新分支，请继续创建 Pull Request，然后点击 **Merge pull request → Confirm merge**。最终变更必须进入 `main`。

## 三、检查 GitHub 文件是否替换正确

回到仓库首页，确认：

```text
app.py
requirements.txt
README.md
.streamlit/config.toml
data/language_ai_cases.db.gz
data/database_manifest.json
data/language_ai_cases.xlsx
raw_files/
derived/embedded/
quality_reports/schools/
schema/
scripts/
```

同时确认：

- 根目录没有旧的 `config.toml`。
- `data` 中没有 `language_ai_cases.db`，只有 `.db.gz`、清单和 Excel。
- `raw_files` 中有 72 份附件。
- `derived/embedded` 中有 8 份 PDF。
- `quality_reports/schools` 中有 56 份逐校报告。

## 四、重新部署现有 Streamlit 应用

1. 打开 https://share.streamlit.io/。
2. 点击 **Continue with GitHub** 并登录同一个 GitHub 账户。
3. 如果页面要求授权，点击 **Authorize Streamlit**。
4. 在工作区找到已有应用 `language-ai-database`。
5. 检查应用设置：
   - Repository：`cm318/language-ai-database`
   - Branch：`main`
   - Main file path：`app.py`
6. GitHub 的提交通常会触发自动更新。等待几分钟后，如果仍是旧版，点击应用旁边的 `⋮`。
7. 点击 **Reboot**，再次点击 **Reboot** 确认。
8. 等待部署完成；如果页面显示休眠，点击 **Yes, get this app back up!**。

只有工作区里确实没有旧应用时，才选择 **Create app → Yup, I have an app**，并填写上面的 Repository、Branch 和 Main file path。App URL 填 `language-ai-database`。如果提示该地址已被占用，说明旧应用仍然存在，应返回工作区找到旧应用，不要重复创建。

## 五、线上验收

打开：

https://language-ai-database.streamlit.app/

首页六项指标应为：

| 指标 | 数量 |
|---|---:|
| 已登记高校 | 56 |
| 培养项目／路径 | 272 |
| 课程／研究主题 | 2,725 |
| 科研项目 | 186 |
| 科研成果 | 10,091 |
| 证据关系 | 83,321 |

继续检查：

1. 数据库首页、高校详情、科研与学生发展、来源与证据、附件下载五类页面均可打开。
2. 高校详情的 11 个页签可以切换。
3. 附件页显示：附件总数 80、允许下载 80、DOCX 56、PDF 总页数 222。
4. 下载一份 DOCX、一个嵌入 PDF 和同步 Excel，确认文件可以打开。
5. 来源与证据页可以检索原文。
6. 用浏览器无痕窗口再打开一次；再用手机检查一次。

全部通过后，才说明 GitHub 替换和 Streamlit 重新部署都已完成。

## 六、遇到问题先看这里

### 页面提示数据库 SHA-256 不一致

检查 `data` 中是否还残留旧的 `language_ai_cases.db`；有则删除。再确认 `.db.gz` 和 `database_manifest.json` 都来自本包，并在同一次核心文件上传中提交。

### 附件下载提示文件不存在

检查第二批是否完整上传了 `raw_files` 和 `derived`，尤其是 `derived/embedded/北京大学` 与 `derived/embedded/慕尼黑大学`。

### GitHub 提示一次上传文件过多

一定是把三批合并上传了。返回本清单，严格按 92、80、11 个文件分三批操作。

### Streamlit 一直显示旧版

按顺序检查：GitHub 的最后提交是否已进入 `main`；Streamlit 的 Repository、Branch、Main file path 是否正确；是否执行了 Reboot；部署日志是否仍有错误。
