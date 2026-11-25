# 仓库文件分类与版本控制边界

## 一、分类原则

1. **可复现**：只要不依赖个人环境就能重新生成的文件，一律不提交（构建产物、缓存、导出）。
2. **可审计**：源码、构建配置、安装脚本、测试、文档必须提交，且能解释每一处变更。
3. **隐私优先**：含真实会话标题、个人路径、工作记忆的文件永不提交，即使“只是一张截图”。
4. **二进制最小化**：仓库只保留图标等必要小体积二进制；exe/zip 通过 Release 分发。

## 二、纳入版本控制

| 类别 | 路径 | 说明 |
|---|---|---|
| 核心源码 | `token_cost.py` | 采集、计价、聚合、报表、导出 |
| 界面源码 | `gui_app.py` | PySide6 看板与任务详情窗口 |
| 构建配置 | `WorkBuddyTokenCost.spec`、`WorkBuddyTokenCost_CLI.spec`、`version_info.txt` | PyInstaller 双目标与 Windows 版本资源 |
| 构建入口 | `build.ps1`、`build.cmd` | 测试 → 构建 → 校验和 → Release zip；cmd 负责绕过执行策略 |
| 包管理 | `pyproject.toml`、`requirements.txt`、`requirements-dev.txt` | 运行/开发依赖 |
| 安装器 | `installer/install.ps1`、`uninstall.ps1`、`*.cmd` | 按用户安装与卸载 |
| 工具脚本 | `scripts/make_icon.py`、`icon_concepts.py`、`make_demo_data.py`、`run-dev.cmd` | 图标、合成数据、开发启动 |
| 测试 | `tests/test_core.py`、`tests/test_gui_assets.py` | 数据层与资源路径 |
| 文档 | `README.md`、`CONTRIBUTING.md`、`SECURITY.md`、`CHANGELOG.md`、`docs/**` | 使用、贡献、安全、审计 |
| 许可证 | `LICENSE` | MIT |
| 资产 | `assets/app_icon.ico`、`app_icon_preview.png`、`icon_preview_sizes.png` | 体积小、构建必需 |
| 文档截图 | `docs/images/dashboard.png`、`task-detail.png` | **合成数据**截图 |
| CI/CD | `.github/workflows/ci.yml`、`release.yml` | 测试与发布 |
| 仓库配置 | `.gitignore`、`.gitattributes` | 忽略规则与换行规范 |

## 三、明确忽略

| 路径/模式 | 类型 | 忽略原因 |
|---|---|---|
| `.workbuddy/` | 本地记忆 | 含个人工作日志、路径、用户名；与代码无关 |
| `assets/design/` | 设计迭代 | 含候选图标与**原始真实截图**；仅本地保留 |
| `dist/` | 构建产物 | 40 MB 级 exe、zip、校验和；由 Release 提供 |
| `build/`、`build_cli/`、`build_gui/` | 中间产物 | PyInstaller 缓存，可重建 |
| `__pycache__/`、`*.pyc` | 字节码 | 可重建 |
| `.venv/`、`venv/` | 虚拟环境 | 平台相关 |
| `.pytest_cache/`、`.ruff_cache/`、`.mypy_cache/` | 工具缓存 | 可重建 |
| `demo-data/` | 合成测试数据 | 可由 `scripts/make_demo_data.py` 重建 |
| `token_cost_*.csv`、`token_cost_*.json`、`exports/` | 应用导出 | 可能含真实会话标题 |
| `*.log`、`*.tmp` | 日志/临时文件 | 运行时产物 |
| `.env`、`.env.*`、`*.pem`、`*.key` | 凭据 | 永不入库 |
| `.vscode/`、`.idea/`、`Thumbs.db`、`Desktop.ini`、`.DS_Store` | 编辑器/系统 | 个人偏好 |

## 四、为什么这些文件不入库

**`dist/` 与 `build*/`**：二进制不可审阅、体积大、每次构建哈希不同；放入 Git 会让仓库
迅速膨胀，也无法保证与源码一致。发布时由 CI 构建并附 `SHA256SUMS.txt`。

**`assets/design/`**：图标候选与原始截图属于过程资产。原始截图包含真实会话标题，
一旦进入 Git 历史，即使后续删除也会留在对象库与 fork 中，因此整目录忽略。

**`demo-data/`**：合成数据用于截图和手工测试，随机种子固定即可复现，不需要占用仓库体积。

**导出文件**：CSV/JSON 含会话标题与费用明细，属于用户数据，不应由仓库托管。

## 五、分支、提交与发布约定

- 分支：`main` 保持可发布；功能分支 `feat/<topic>`，修复分支 `fix/<topic>`。
- 提交信息：Conventional Commits，例如 `fix(cli): resolve relative --root path`。
- 版本：语义化版本；`token_cost.VERSION` 为唯一来源，`pyproject.toml` 与
  `version_info.txt` 同步更新。
- 发布：打 `v<version>` 标签触发 Release 工作流，产物包含两个 exe、`LICENSE`、
  `README.md`、安装器与 `SHA256SUMS.txt`。
- 发布前检查：
  1. `python -m pytest -q` 全绿；
  2. `python -m pyflakes ...` 无输出；
  3. `python -m pip_audit -r requirements.txt` 无已知漏洞；
  4. 用合成数据重新截图，确认无真实标题；
  5. `git status --ignored` 确认没有私人文件被跟踪。

## 六、提交前自检命令

```powershell
git status --short
git status --ignored --short | Select-String "workbuddy|design|dist|demo-data"
git ls-files | Select-String "\.exe$|\.zip$|\.csv$|\.jsonl$"
```

最后一条应无输出；若有，说明构建产物或个人数据被误加入索引。
