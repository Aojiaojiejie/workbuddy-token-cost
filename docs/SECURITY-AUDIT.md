# 安全审计报告

- 项目：WorkBuddy Token 费用看板（`token_cost.py` / `gui_app.py` / `installer/`）
- 版本：5.0.1
- 审计日期：2026-11-25
- 审计范围：仓库源码、打包配置、安装/卸载脚本、文档与图片资产、依赖清单
- 不在范围：WorkBuddy 客户端本身、DeepSeek 官网、用户本机操作系统加固

## 一、结论

未发现硬编码凭据、后门、命令注入或越权写入。共识别 11 项风险：高 2 项、中 3 项、低 6 项；
另有 4 项信息性观察。高/中风险均已修复；低风险中 2 项已处理，4 项需发布者持续关注
（代码签名、Actions 固定 SHA、导出脱敏、远程价格内容）。依赖审计未发现已知漏洞。

| 等级 | 数量 | 已处理 | 需持续处理 |
|---|---|---|---|
| 高 | 2 | 2 | 0 |
| 中 | 3 | 3 | 0 |
| 低 | 6 | 2 | 4 |
| 信息 | 4 | — | — |

## 二、资产与信任边界

| 资产 | 位置 | 敏感度 | 访问方式 |
|---|---|---|---|
| 会话用量日志 | `~/.workbuddy/projects/*/*.jsonl` | 中（含标题、时间、模型、token） | 只读 |
| 会话元数据 | `~/.workbuddy/workbuddy.db` | 中（标题、模型、状态） | SQLite `mode=ro` |
| 活跃窗口 ID | `~/.workbuddy/sessions/*.json` | 低 | 只读 |
| 官网价格页 | `https://api-docs.deepseek.com/...` | 低 | 出站 HTTPS GET |
| 导出文件 | 用户指定路径 | 中（含标题） | 用户主动触发写入 |
| 安装目录 | `%LOCALAPPDATA%\Programs\WorkBuddyTokenCost` | 低 | 安装器写入 |

信任边界：程序以当前用户身份运行，不监听端口、不安装服务/驱动、不请求提权；
所有外部输入只有“本地日志文件”和“官网 HTML”两类。

## 三、发现明细

### SEC-01（高，已修复）仓库截图包含真实会话标题

- 证据：整理前的 `gui_preview.png` 可见真实任务标题，其中包含用户名片段与内部项目
  交接信息，另有可推断个人工作内容的标题。
- 影响：一旦推送到公开仓库，历史记录与镜像难以彻底清除。
- 处置：原始截图移至 `assets/design/private/` 并由 `.gitignore` 排除；仓库内
  `docs/images/dashboard.png`、`task-detail.png` 改用 `scripts/make_demo_data.py`
  生成的合成数据重新拍摄。

### SEC-02（高，已修复）本地记忆目录可能被误提交

- 证据：`.workbuddy/memory/*.md` 记录了个人工作日志、桌面文件路径、交付历史与用户名；
  原仓库没有 `.gitignore`，`git add .` 会把整个目录纳入版本控制。
- 影响：个人信息与内部工作内容泄露。
- 处置：`.gitignore` 排除 `.workbuddy/`、`assets/design/`、`dist/`、`build*/`、
  `demo-data/`、导出文件与日志；`docs/REPOSITORY.md` 明确跟踪边界。

### SEC-03（中，已修复）定价页响应缺少大小与类型限制

- 证据：原实现 `urlopen(...).read()` 一次性读入全部响应，只依赖 urllib 对 4xx/5xx 抛错，
  未显式校验状态码、`Content-Type`，也没有响应大小上限。
- 处置：`fetch_prices()` 增加 HTTP 200 校验、`text/html|text/plain` 白名单、
  4 MiB 读取上限（多读 1 字节用于判断超限）；仍保留原有结构与价格合理性校验。

### SEC-04（中，已修复）可执行文件使用 UPX 压缩且无版本资源

- 证据：两份 spec 均为 `upx=True`，且未写入 `version` 资源。
- 影响：UPX 压缩的 PyInstaller 单文件更容易被启发式引擎误报；缺少版本信息不利于
  溯源与完整性核对。
- 处置：`upx=False`；新增 `version_info.txt` 并写入两个 exe 的版本资源。

### SEC-05（中，已修复）安装器未校验发布包完整性

- 证据：原安装流程只做复制，没有哈希校验。
- 处置：`install.ps1` 在源目录存在 `SHA256SUMS.txt` 时逐文件校验 SHA256，
  不匹配即中止；`build.ps1` 在 `dist/` 生成校验和；Release 工作流随包上传。

### SEC-06（低，持续）导出文件包含会话标题

- 说明：CSV/JSON 导出会写入标题，可能含敏感信息。写入路径由用户在文件对话框中
  主动选择，程序不做自动上传。CSV 未对 `= + - @` 开头的单元格做公式前缀转义，
  打开来源不明的导出文件时建议先用文本编辑器查看。
- 建议：分享前脱敏；后续可增加 `--redact-titles` 选项（当前版本未实现）。

### SEC-07（低，持续）`--root` 可指向任意目录

- 说明：这是调试与多环境需求；程序只按固定模式读取 `projects/*/*.jsonl` 与
  `workbuddy.db`，不执行其中内容，也不写回。风险仅限于本机用户读取自己本就有权限的文件。

### SEC-08（低，已缓解）崩溃日志写入 `%TEMP%`

- 说明：仅 GUI 未捕获异常时写入 `WorkBuddyTokenCost_gui_error.log`，内容为 traceback，
  可能含本地路径，不含 token 或凭据；卸载器会删除该文件。

### SEC-09（低，持续）远程 HTML 影响价格展示

- 说明：价格由正则解析官网表格，恶意或错误内容可能让展示价格失真，但不会导致代码执行。
  现有校验（6 行结构、正数、递增、闲时:高峰 = 1:2）与回落机制限制了影响面。
- 建议：对价格精度敏感的场景使用 `--offline` 并人工核对内置价表。

### SEC-10（低，已修复）静默安装会结束运行中的实例

- 说明：`-Silent` 下安装器直接结束 `WorkBuddyTokenCost*` 进程，避免文件占用。
  程序不持久化界面状态，无数据丢失；交互模式会先询问。已在 `docs/INSTALL.md` 说明。

### SEC-11（低，持续）GitHub Actions 使用标签引用

- 说明：工作流使用 `actions/checkout@v4`、`actions/setup-python@v5` 等官方 action，
  以主版本标签引用。对高保障场景建议固定到 commit SHA，并开启 Dependabot。

### SEC-12（信息）依赖漏洞审计

- 命令：`python -m pip_audit -r requirements.txt` 与 `requirements-dev.txt`
- 结果：14 个包（含传递依赖），0 个已知漏洞。
  关键版本：`PySide6-Essentials 6.12.0`、`shiboken6 6.12.0`、`Pillow 13.0.0`、
  `PyInstaller 6.22.3`、`pytest 9.2.0`、`pyflakes 4.1.0`。
- 注意：漏洞库有时效性，发布前应重新执行。

### SEC-13（信息）凭据与个人信息扫描

- 规则：通用 `api_key/secret/password/token/bearer` 赋值、`sk-*`、`ghp_*`、`AKIA*`、
  PEM 私钥头、个人路径（`C:\Users\...`、`D:\桌面`、`/Users/...`、用户名）。
- 结果：源码、配置、脚本、文档中 0 命中。

### SEC-14（信息）无网络监听与遥测

- 程序只发起一次出站 HTTPS 请求（定价页），无 socket 监听、无上报、无账号体系。
- TLS 使用 Python 默认证书校验，未关闭 `verify`、未使用自定义不安全的 SSLContext。

### SEC-15（信息）SQLite 与命令执行面

- 数据库以 `file:...?mode=ro` 只读打开，SQL 为固定语句，无用户输入拼接。
- 唯一的 shell 调用是 `os.system("cls")`，参数为常量，无注入面。

## 四、修复清单（按优先级）

| 优先级 | 动作 | 状态 |
|---|---|---|
| P0 | 移除含真实标题的截图，改用合成数据截图 | 完成 |
| P0 | 忽略 `.workbuddy/`、`assets/design/`、构建产物与导出文件 | 完成 |
| P1 | 定价页请求加状态码/类型/大小限制 | 完成 |
| P1 | 关闭 UPX、写入版本资源 | 完成 |
| P1 | 安装器校验 SHA256、增加路径护栏 | 完成 |
| P2 | 为 Release 二进制做代码签名（需证书） | 待发布者执行 |
| P2 | 固定 GitHub Actions 到 SHA，启用 Dependabot | 建议 |
| P3 | 导出支持标题脱敏 | 后续版本 |

## 五、残余风险

1. **未签名二进制**：SmartScreen 会提示，用户需自行判断来源；签名后可控。
2. **官网改版**：价格解析失败会回落到内置价表，费用可能短期失真，但不影响安全性。
3. **依赖漏洞时效性**：本次审计为 2026-11-25 的快照，发布前需重跑 `pip-audit`。
4. **本地数据敏感性**：工具本身不泄露数据，但截图、导出文件、Issue 附件可能泄露；
   贡献指南已明确禁止提交真实会话内容。

## 六、复现命令

```powershell
python -m pyflakes token_cost.py gui_app.py scripts tests
python -m pytest -q

python -m pip install pip-audit
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt

# 凭据扫描可用 gitleaks / trufflehog：
# gitleaks detect --source . --no-git
```

## 七、披露政策

安全问题请通过仓库 **Security → Report a vulnerability** 私下提交，不要开公开 Issue。
维护者会在 7 天内确认，并在修复后于 `CHANGELOG.md` 记录（不公开利用细节）。
