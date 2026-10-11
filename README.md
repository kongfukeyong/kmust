# 资料库

按提供的 Masonry Flow 风格开发的昆明理工大学资料库与 Android 应用。

- 网页：https://news.kongfu.xyz/kust/
- 原始资料下载：https://news.kongfu.xyz/kust/originals.html
- 全部原资料 ZIP：https://news.kongfu.xyz/kust/downloads/kust-original-materials.zip
- IP 入口：http://47.253.193.153/kust/
- Android APK：https://news.kongfu.xyz/kust/downloads/kust-study.apk
- Android 包名：`cn.kust.study`，版本 1.0.1，Android 8.0 及以上。
- 原始仓库：https://github.com/123pyLeo/KUST-
- 来源提交：`cd46fa80e1d557a8d5406b5223c899d75e8ca4be`

## 内容与题目质量

全部 327 个原文件已部署并按 Git blob SHA-1 核验，包含 27 个课程。正常资料列表显示 311 份（排除 15 个临时文件及仓库说明），原始文件仍保留。

子智能体完成 PDF、DOC、DOCX、XLS、PPTX 等题目分离：9,365 道原始候选题，默认练习 9,211 道，其中 2,406 道含原文可关联答案；154 道结构异常题单独隔离。默认题库结构校验 0 错误、0 警示，但不等同于逐题人工核验。39 个文件需 OCR，5 个旧 Word 文件解析失败，均保留原件。公式和图形请以原卷为准。

详细说明见 `题库提取说明.md`，机器报告在 `public/data/`。`questions-all.json` 保留全部候选，`questions-review.json` 保留隔离题，`questions.json` 是默认练习题。

## 源码结构

- `public/`：无需构建的 HTML/CSS/JavaScript 与 JSON 题库。
- `android/`：原生壳源码、Manifest、图标与签名构建脚本。
- `scripts/extract_questions.py`：可复现的源文件提取。
- `scripts/extract_validate.py`：ID、来源关系、选项和边界校验。
- `scripts/quarantine_questions.py`：隔离结构异常题，并保留审计记录。
- `scripts/prepare_assets.py`：校验原文件哈希、生成缩略图。
- `scripts/deploy_nginx.py`：向已检查的 Nginx 配置添加独立 `/kust/` 路径，修改前备份。

`public/files` 在服务器是指向原始仓库副本的链接。源码包不重复内嵌约 317 MB 原始文件；原卷已经部署，可在网页访问。下载固定提交的 ZIP 后，用 Python `zipfile` 解压可正确保留中文文件名。




## 1.0.2 数学公式更新（2026-10-11）

- 83道含[pic]的旧DOC题已恢复299处原始公式/图形，并剔除误混入显示内容的页脚；另有21道DOCX题增加结构化公式或图片。
- 共104道题增强，236个MathML公式、103处图片引用。原9211道题的ID、原文、选项、答案保持不变；新增rich字段用于显示，学习记录继续兼容。
- MathJax 3.2.2与公式图片均自托管，并包含在APK离线资源中。公式图片可点按放大。
- 28项数学解析测试通过；浏览器全部236公式渲染无错误，并验证390px手机布局。APK完成构建及v2/v3签名验证，未进行Android真机安装测试。
- 不是全库公式人工校对：PDF扫描公式、无法唯一定位的DOCX对象仍需查原卷；详见public/data/docx-math-report.json。
- 旧DOC恢复脚本：scripts/enrich_legacy_math.py。需要LibreOffice同一源文件分别导出XHTML（XHTML Writer File）和HTML（HTML (StarWriter)），前者保留MathML，后者提供OLE图形的GIF/PNG预览。转换目录含manifest.json（id/sourcePath），html/<id>.html与web/<id>.html及其图片。运行参数--conversion <目录> --public public。
- DOCX结构解析与增量整合流程见数学解析说明.md。
