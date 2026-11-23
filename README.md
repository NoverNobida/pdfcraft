# PdfCraft 简体中文版

基于 [storytold/pdfcraft](https://github.com/storytold/pdfcraft) 的独立构建。Windows 桌面版和网页端首次运行默认使用简体中文，可以在首选项中切换界面语言。

![PdfCraft 图标](assets/pdfcraft-128.png)

## 下载

在 [Releases](https://github.com/NoverNobida/pdfcraft/releases) 选择所需版本。

| 附件 | 用途 |
| --- | --- |
| `pdfcraft-<版本>-windows-x64.msi` | Windows x64 安装包 |
| `pdfcraft-web-<版本>.zip` | 网页端静态文件及 OCR 模型。解压后将整个目录放到 HTTP 或 HTTPS 站点 |
| `pdfcraft-<版本>-upstream-source.tar.gz` | 对应上游提交的完整原始源码归档 |
| `SHA256SUMS.txt` | 三个附件的 SHA-256 校验值 |

GitHub 同时会自动生成本仓库标签的 `Source code` 链接。上游源码在单独命名的附件中。

Windows 优先使用系统已安装的简体中文字体（首选微软雅黑）。缺少适用字体或字符时，桌面版会使用随包提供的 Noto Sans CJK SC。网页端内置 Noto Sans CJK SC。

程序的启动检查和「帮助 → 检查更新」均访问本仓库的 Release。Windows 安装包未做 Authenticode 签名，发现新版后从 Release 下载 MSI 安装。

## 发布流程

[GitHub Actions](https://github.com/NoverNobida/pdfcraft/actions/workflows/release.yml) 计划在每天北京时间 09:17 查询上游的最新正式 Release，实际触发时间可能因 GitHub Actions 调度而延后，也可以手动运行。遇到多个上游版本时只构建 GitHub 标记为最新的版本。已经发布的标签会跳过，缺失或不兼容的构建输入会报错。

工作流按上游标签解析出提交，在临时目录中应用 [构建补丁](patches/pdfcraft.patch) 并替换应用图标。翻译和字体沿用该上游版本锁定的依赖提交。两端构建成功后，以相同标签发布安装包、网页包和未修改的上游源码。

上游软件及此处的修改与图标采用 MIT 或 Apache-2.0 许可。发行包保留上游许可、字体和 OCR 模型声明。
