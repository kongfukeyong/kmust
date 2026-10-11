# 昆工拾题

这是一个昆明理工大学资料库的自建客户端与网页，使用 AI 进行题目分离和整理，基于 https://github.com/123pyLeo/KUST- 开发。

采用 Masonry Flow 风格，提供网页版与 Android 应用。
- 网页：https://news.kongfu.xyz/kust/
- 原始资料下载：https://news.kongfu.xyz/kust/originals.html
- 全部原资料 ZIP：https://news.kongfu.xyz/kust/downloads/kust-original-materials.zip
- IP 入口：http://47.253.193.153/kust/
- Android APK：https://news.kongfu.xyz/kust/downloads/kust-study.apk
- Android 包名：`cn.kust.study`，版本 1.0.1，Android 8.0 及以上。
- 原始仓库：https://github.com/123pyLeo/KUST-
- 来源提交：`cd46fa80e1d557a8d5406b5223c899d75e8ca4be`

## 已实现

独立原始资料下载区，支持单个原文件、27门课程ZIP和完整原资料ZIP（327个文件，约241.2 MiB），均从服务器下载；手机单列、平板双列、桌面三/四列瀑布流；真实原卷缩略图；课程与类型筛选；全文关键词搜索；原文件下载；逐题查看、答案展开；收藏、待复习与已掌握记录；学习记录 JSON 导出。

APK 使用原生 Android WebView 外壳，联网访问服务器最新版；连接失败或首屏超时后切换到随包离线题库。原文件需联网打开。仅申请联网权限，没有账号系统或分析埋点。手机浏览器和 APK 的学习记录各自保存在设备中；在线页面与离线页面亦使用不同存储空间，不自动同步。卸载会清除本地学习记录，导出功能可留存 JSON 备份。

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

## 服务器部署位置

- 活跃版本：`/opt/kust-study/current` → `/opt/kust-study/releases/v1`
- 原始文件：`/opt/kust-study/source-utf8/KUST--main`
- Python 工具环境：`/opt/kust-study/build/venv`
- APK 签名：`/opt/kust-study/signing`（仅服务器 root 可读，不包含在源码或公开下载中）
- Nginx 修改前备份：`/opt/kust-study/build/*.bak`

站点通过 Nginx 静态服务，不依赖临时进程；修改只增加两个既有站点的 `/kust/` 路由。后续发布可建立新版本目录并切换 `current` 符号链接。回滚时恢复对应 Nginx 备份并先运行 `nginx -t`。

本地预览：

```sh
python -m http.server 8876 --directory public
```

Android 构建需要 Java 17、Android API 35 平台包和 Build Tools 35。`android/build.sh` 使用服务器已有 SDK 默认路径，`ANDROID_SDK_ROOT` 可覆盖 SDK 根目录。保留签名目录以便后续 APK 覆盖更新；不要公开签名文件。

## 验证范围

已验证源文件完整性、全量资源链接、题库结构、网页加载和部分手机交互、390px 手机单列布局、APK v2/v3 签名及 Manifest。未在实体 Android 手机上安装测试。


## 1.0.2 数学公式更新（2026-10-11）

- 83道含[pic]的旧DOC题已恢复299处原始公式/图形，并剔除误混入显示内容的页脚；另有21道DOCX题增加结构化公式或图片。
- 共104道题增强，236个MathML公式、103处图片引用。原9211道题的ID、原文、选项、答案保持不变；新增rich字段用于显示，学习记录继续兼容。
- MathJax 3.2.2与公式图片均自托管，并包含在APK离线资源中。公式图片可点按放大。
- 28项数学解析测试通过；浏览器全部236公式渲染无错误，并验证390px手机布局。APK完成构建及v2/v3签名验证，未进行Android真机安装测试。
- 不是全库公式人工校对：PDF扫描公式、无法唯一定位的DOCX对象仍需查原卷；详见public/data/docx-math-report.json。
- 旧DOC恢复脚本：scripts/enrich_legacy_math.py。需要LibreOffice同一源文件分别导出XHTML（XHTML Writer File）和HTML（HTML (StarWriter)），前者保留MathML，后者提供OLE图形的GIF/PNG预览。转换目录含manifest.json（id/sourcePath），html/<id>.html与web/<id>.html及其图片。运行参数--conversion <目录> --public public。
- DOCX结构解析与增量整合流程见数学解析说明.md。


## 1.0.3 课程自定义排序（2026-10-11）

课程栏新增“调整顺序”，支持置顶、上移、下移、恢复默认和保存。排序保存在当前浏览器或APK的本地存储；资料、练习、收藏共用同一顺序。“全部课程”固定在首位，新课程自动追加到末尾。关闭或取消不会保存草稿。

已验证479×918手机布局、上下移动、置顶、刷新持久化、取消、恢复默认、跨页面排序；APK签名和离线静态资源经过校验，未进行Android真机安装测试。


## 1.0.4 PDF 字形与题目说明（2026-10-11）

- 自托管 Noto Sans Math 数学字库（SIL OFL，许可随 fonts/OFL.txt 提供），APK 离线资源一并打包。
- PDF Symbol 私用码与二维公式布局通过原PDF内嵌字形渲染恢复；可靠题号边界裁整题，边界不可靠显示原页并标出题号。216 DPI、无损WebP，不猜测缺失公式。
- 用户指出的《第一章 质点运动学含答案》第1页第2题已逐项对照原页，修正为A/B/C/D四个MathML选项，不新增答案，保留题目ID和原提取记录。
- 题目说明统一为“由 AI 分离”；图片查看器支持100%至400%放大，可滚动阅读。
- scripts/pdf_question_regions.py有13项边界测试；scripts/restore_pdf_glyphs.py可重新生成修复数据。原始资料下载仍直接由服务器提供。
