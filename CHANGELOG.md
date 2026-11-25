# Changelog

本文件格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [5.0.1] - 2026-11-25

开源前的整理与加固版本。功能与 5.0.0 一致，不改变计价口径。

### Added

- `installer/`：按用户安装的 PowerShell 安装/卸载程序，含快捷方式、卸载注册项、
  可选 PATH、SHA256 校验与路径安全护栏。
- `tests/`：23 项单元测试，覆盖记录解析、峰谷判定、聚合、导出与资源路径。
- `docs/AUDIT.md`、`docs/SECURITY-AUDIT.md`、`docs/REPOSITORY.md`、`docs/INSTALL.md`。
- `scripts/make_demo_data.py`：生成合成数据，用于截图与手工测试。
- `pyproject.toml`、`requirements*.txt`、`.gitignore`、`.gitattributes`、CI/Release 工作流。
- `build.cmd`：绕过执行策略的构建包装，双击即可。
- Windows 版本资源（`version_info.txt`），资源管理器可显示文件版本。

### Changed

- 版本号改为单一来源：GUI 直接读取 `token_cost.VERSION`。
- 图标与预览图移入 `assets/`，打包配置同步更新。
- `build.ps1` 统一构建、校验和与 Release zip。
- 关闭 UPX 压缩，降低杀毒软件误报概率。

### Fixed

- 相对路径 `--root demo-data` 时 SQLite URI 构造失败（`as_uri()` 不接受相对路径），
  导致会话标题回退到 jsonl；现在统一 `resolve()`。
- 定价页请求增加状态码、Content-Type 与 4 MiB 响应上限校验；UA 改为标识应用自身。
- 删除未使用的方法与赋值：`ElidedLabel.fullText`、`Segmented.value`、重复的
  `empty_text` 赋值；`pause_btn` 补上 `setCheckable(True)`，暂停状态可见。
- 删除 `icon_concepts.py` 中未使用的 `math` 导入。
- 图标脚本不再硬编码 `C:/Windows/Fonts/...`，增加跨平台字体回退。
- 移除指向 `dist/` 的 `watch.cmd`，替换为可用的 `scripts/run-dev.cmd`。

### Security

- 仓库不再包含带真实会话标题的截图；文档截图由合成数据生成。
- `.workbuddy/`、`assets/design/`、`dist/`、`build*/` 等加入忽略清单。
- 依赖审计：PySide6-Essentials 6.12.0 及其 13 个构建期依赖未发现已知漏洞。

## [5.0.0] - 2026-11-13

### Added

- 深色数据看板：4 张 KPI 卡、可切换指标的柱状/面积图、任务明细表。
- 点击任务行打开独立图表窗口（今天按小时、历史按天）。
- 时间维度（今天/近 7 天/近 30 天/全部）、模型范围、峰谷模式、标题搜索。
- CSV / JSON 导出，JSON 含每日与当天分时聚合。

### Changed

- 数据层新增 `today`、`hourly_total`、`hourly_by_session` 桶；日桶补齐命中/峰谷字段。
- 界面不再依赖第三方图表库，图表由 QPainter 自绘。

## [4.0.0] - 2026-11-13

### Added

- 首个 Qt6 图形界面版本，替代命令行窗口作为默认交互方式。
- 后台线程扫描、实时刷新、置顶、暂停、导出菜单。

## [3.0.0] - 2026-11-12

### Changed

- 命令行版默认进入实时刷新模式，`--once` 保留一次性报表。

## [2.0.0] - 2026-11-12

### Added

- 应用图标与打包配置；GUI/CLI 双可执行文件。

## [1.0.0] - 2026-11-12

### Added

- 首个版本：扫描 `~/.workbuddy` 会话日志，按 DeepSeek 峰谷价统计 token 费用。
