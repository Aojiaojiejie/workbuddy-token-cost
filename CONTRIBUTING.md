# 贡献指南

感谢愿意花时间改进这个项目。提交之前，请先读一遍以下约定，能省掉一轮来回。

## 行为准则

- 讨论对事不对人；不接受人身攻击、歧视性表达或骚扰。
- 不提交他人的隐私数据、内部文档、真实会话日志或截图。
- 维护者有权关闭不符合上述原则的 Issue / PR。

## 环境准备

```powershell
git clone <your-fork-url>
cd WorkBuddyTokenCost

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

要求 Python 3.10+。GUI 依赖 `PySide6-Essentials`；`Pillow`、`PyInstaller`、`pytest`、
`pyflakes` 只在开发/构建时需要。

## 代码结构

| 文件 | 职责 | 修改注意 |
|---|---|---|
| `token_cost.py` | 数据采集、价格解析、聚合、报表、导出 | 保持纯标准库；GUI 与 CLI 共用，改口径要同步测试 |
| `gui_app.py` | PySide6 界面、图表绘制、后台扫描线程 | 所有耗时操作放 `Scanner` 线程；UI 只在主线程更新 |
| `installer/*.ps1` | 安装/卸载 | 只用 ASCII 字符，兼容 Windows PowerShell 5.1；破坏性操作必须有路径护栏 |
| `scripts/*.py` | 图标与演示数据 | 不依赖本机绝对路径，字体需有回退 |
| `tests/*.py` | 单元测试 | 不读取真实 `~/.workbuddy`，全部用临时目录构造 |

## 本地运行

```powershell
python gui_app.py --offline                  # 不联网取价，启动最快
python gui_app.py --root demo-data --offline # 用合成数据，避免暴露真实标题
python token_cost.py --once --no-pause
```

生成合成数据：

```powershell
python scripts/make_demo_data.py --force
```

## 测试与静态检查

```powershell
python -m pytest -q
python -m pyflakes token_cost.py gui_app.py scripts tests
python -m compileall -q token_cost.py gui_app.py scripts
```

提交前请确保：

- 新增/修改的逻辑有对应测试；
- 不引入未使用的 import、变量、函数；
- 不把真实数据写入测试夹具或截图。

## 注释规范

只写“为什么”，不写“是什么”。允许且鼓励的注释：

- 非显然的约束（例如 ICO 必须用 DIB 条目、SQLite URI 只接受绝对路径）；
- Workaround 及其上游原因；
- 魔数与正则的解释；
- 公共 API / 模块边界；
- `TODO` / `FIXME`（需说明触发条件）；
- 复杂状态流转。

不需要的注释：每个 getter/setter、逐行解释代码在做什么、与实现重复的 docstring、
注释掉的旧代码（直接删，Git 里有历史）。

## 提交信息

使用 Conventional Commits：

```text
feat(gui): add per-task hourly chart
fix(cli): resolve relative --root path
docs: add installer guide
test: cover cache-hit fallback
chore(deps): bump PySide6-Essentials to 6.12.0
```

一个提交只做一件事；格式化与逻辑修改分开。

## Pull Request 清单

- [ ] `python -m pytest -q` 通过
- [ ] `python -m pyflakes ...` 无输出
- [ ] 新增行为有测试或明确说明为何无法测试
- [ ] 没有提交 `dist/`、`build*/`、`__pycache__`、`.workbuddy/`、导出文件
- [ ] 截图使用 `demo-data/` 合成数据，未出现真实会话标题
- [ ] 更新了 `CHANGELOG.md`（用户可见的变更）
- [ ] 涉及界面时，附最小尺寸（1120×700）与常规尺寸截图
- [ ] 涉及安装器时，实际跑过安装 → 卸载 → 残留检查

## 版本与发布

- `token_cost.VERSION` 是唯一版本来源；`pyproject.toml`、`version_info.txt`、
  `CHANGELOG.md` 需同步。
- 维护者打 `v<version>` 标签后由 Release 工作流构建并上传产物。

## 安全问题

不要开公开 Issue。按 [SECURITY.md](SECURITY.md) 的方式私下报告。
