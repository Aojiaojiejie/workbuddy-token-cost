# 死引用与冗余注释审计

- 审计对象：`token_cost.py`、`gui_app.py`、`scripts/*.py`、两份 `.spec`、`scripts/run-dev.cmd`
- 审计版本：5.0.1（整理前为 5.0.0）
- 审计日期：2026-11-25
- 方法：`pyflakes 4.1.0` 静态检查 → AST 符号引用计数 → 人工追踪调用链 →
  `compileall` + 导入测试 → 23 项 pytest → 实际运行 CLI/GUI 复核

## 一、结论摘要

| 类别 | 数量 | 状态 |
|---|---|---|
| 未使用的 import | 1 | 已删除 |
| 从未调用的方法 | 2 | 已删除 |
| 无效/重复赋值 | 2 | 已删除或修正 |
| 断链的路径引用 | 4 | 已重写或修正 |
| 重复定义（易漂移） | 2 | 已合并为单一来源 |
| 过时/失效注释 | 2 | 已重写 |
| 实际运行缺陷（相对路径） | 1 | 已修复 |
| 注释掉的旧代码 / TODO / FIXME | 0 | 无需处理 |

静态检查最终结果：`python -m pyflakes token_cost.py gui_app.py scripts tests` 无输出；
`python -m compileall` 通过；`python -m pytest` 23 项全通过。

## 二、未使用与死代码

| ID | 位置（修复前） | 问题 | 判定依据 | 处置 |
|---|---|---|---|---|
| D1 | `scripts/icon_concepts.py:11` | `import math` 未使用 | pyflakes F401 | 删除 |
| D2 | `gui_app.py:340-341` | `ElidedLabel.fullText()` 从未被调用 | 全仓库仅 1 处引用（定义本身） | 删除；`setText` 已覆盖写入需求 |
| D3 | `gui_app.py:472-477` | `Segmented.value()` 从未被调用；外部只用 `set_value` 与 `changed` 信号 | 全仓库 0 处 `.value()` 调用 | 删除 |
| D4 | `gui_app.py:1443` | `redraw_table()` 末尾重复设置 `table.empty_text`，与 `_build_table_card()` 中的值完全相同 | 同一常量两处赋值 | 删除末尾重复行 |

## 三、无效行为与运行缺陷

| ID | 位置（修复前） | 问题 | 证据 | 处置 |
|---|---|---|---|---|
| D5 | `gui_app.py:1214` | `pause_btn.setChecked(paused)` 是空操作：按钮未设为 checkable，状态不会显示 | QSS 已定义 `QPushButton#toggle:checked` 样式，说明原意是可切换按钮 | 补 `setCheckable(True)`，暂停时显示橙色选中态 |
| D6 | `token_cost.py:117` | `--root` 传相对路径时，`Path.as_uri()` 抛 `ValueError: relative path can't be expressed as a file URI`，`workbuddy.db` 读取失败，标题静默回退到 jsonl | 实跑 `python token_cost.py --root demo-data ...` 复现 | `load_session_meta()` 内 `resolve()`；`main()` 与 `gui_app._make_ctx()` 同步归一化 |

## 四、断链的路径与资源引用

| ID | 位置（修复前） | 问题 | 处置 |
|---|---|---|---|
| D7 | `watch.cmd:4` | 指向 `%~dp0dist\WorkBuddyTokenCost.exe`；`dist/` 是构建产物，克隆后不存在；脚本名为 watch 却启动 GUI | 重写为 `scripts/run-dev.cmd`，从源码启动 GUI |
| D8 | `WorkBuddyTokenCost.spec:7,38` | `datas=[('app_icon.ico','.')]`、`icon=['app_icon.ico']` 在图标移入 `assets/` 后断链 | 改为 `assets/app_icon.ico`，datas 目标目录 `assets` |
| D9 | `scripts/make_icon.py:23-25` | 输出目录用 `__file__` 所在目录；字体硬编码 `C:/Windows/Fonts/msyhbd.ttc` | 输出改为仓库 `assets/`；字体按 Windows/macOS/Linux 候选探测，失败回退 Pillow 内置字体 |
| D10 | `scripts/icon_concepts.py:17-20` | 同上，且输出到已被移除的 `concepts/` | 输出改为 `assets/design/concepts/`；同样使用字体回退 |

## 五、重复定义与可维护性

| ID | 位置（修复前） | 问题 | 处置 |
|---|---|---|---|
| D11 | `gui_app.py:38` 与 `token_cost.py:36` | 两处各自维护 `VERSION`，升级时容易只改一处 | GUI 改为 `VERSION = core.VERSION`，单一来源 |
| D12 | `gui_app.py:1176-1178` 与 `gui_app.py:1332-1333` | 指标 → 颜色/图表样式的映射写了两遍 | 提取 `METRIC_STYLE` 常量，两处共用 |

## 六、注释审计

| 位置 | 注释内容 | 判定 | 处置 |
|---|---|---|---|
| `scripts/make_icon.py:3-11` | 描述“方案 1 × 方案 6 结合版”，但候选方案与编号说明已不在仓库 | 过时、上下文缺失 | 重写为对当前图形的直接描述，去掉方案编号 |
| `token_cost.py:40` | “官网 2026-09-10 12:00 生效的价格” | 时点型表述易过期 | 改为“内置兜底价（快照 2026-09-10）”，明确其性质 |
| `token_cost.py:244,247` | 日桶/小时桶的字段结构 | 非显然的数据契约 | 保留 |
| `make_icon.py:133` | ICONDIRENTRY 的 planes/bitCount 必须与 DIB 头一致 | 非显然约束，避免踩坑 | 保留 |
| `gui_app.py:336` | `# noqa: N802 (Qt 命名)` | 说明为何违反命名规范 | 保留 |
| `gui_app.py:518` | `# noqa: E731` | lambda 赋值是有意为之 | 保留 |
| 全仓库 | 注释掉的旧代码 | 0 处 | 无需处理 |
| 全仓库 | `TODO` / `FIXME` / `XXX` / `HACK` | 0 处 | 无需处理 |

## 七、保留的重复（已评估，暂不合并）

| 项 | 原因 |
|---|---|
| `MainWindow._range_label()` 与 `DetailWindow._range_label()` | 两个窗口各自持有 `range_key`，方法仅 3 行；抽公共函数收益低于耦合成本 |
| `token_cost.fmt_num()` 与 `gui_app.fmt_tokens()` | 前者用于等宽控制台（1 位小数），后者用于界面（2 位小数），精度口径不同，不能直接合并 |
| `MODEL_SHORT` 与 `FLASH_MODELS` | 前者是展示短名映射，后者是计费白名单，职责不同 |

## 八、依赖使用情况

| 包 | 使用位置 | 归类 | 说明 |
|---|---|---|---|
| 标准库（argparse/sqlite3/urllib/csv/json 等） | `token_cost.py` | 运行时 | 核心不依赖任何第三方库，便于打包与审计 |
| `PySide6-Essentials` | `gui_app.py` | 运行时 | 只用到 QtCore/QtGui/QtWidgets，Essentials 已覆盖 |
| `PySide6`（元包）、`PySide6-Addons`、`PySide6-WebEngine`、`PySide6-Pdf` | 无 | **未使用** | 本机环境因安装元包而存在；代码未导入，requirements 不声明，避免多拉约 200 MB |
| `Pillow` | `scripts/make_icon.py`、`icon_concepts.py` | 开发 | 仅生成图标，不进入运行时 |
| `PyInstaller` | `build.ps1`、两份 spec | 构建 | 仅打包使用 |
| `pytest`、`pyflakes` | `tests/`、CI | 开发 | 仅测试与静态检查 |

`pyflakes` 对全部源码、脚本、测试的检查结果为 0 个未使用 import / 未使用变量。
运行时依赖收敛到 `PySide6-Essentials==6.12.0`，核心逻辑保持纯标准库。

## 九、剩余风险

1. **定价页结构耦合**：`fetch_prices()` 依赖 `rowspan="6">价格` 与固定 `<td>` 结构，
   官网改版会解析失败。现有保护：结构校验（6 行、1:2 关系、正数递增）+ 异常回落内置价表，
   不会崩溃，但会静默使用旧价。建议官网调价时同步更新 `FALLBACK_PRICES` 与 `CHANGELOG`。
2. **PySide6 动态属性**：Qt 槽函数、`paintEvent` 等由框架调用，静态引用计数偏低，已人工排除，
   未误删。
3. **未覆盖 UI 交互的自动化测试**：`tests/` 覆盖数据层与资源路径；界面交互依赖
   `--shot` 截图与人工核对，后续可补充 `pytest-qt`。
