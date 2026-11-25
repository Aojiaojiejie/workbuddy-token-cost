# 安装与卸载说明

本项目的安装器是**按用户安装**的 PowerShell 脚本，不需要管理员权限，也不写入
`Program Files` 或系统级注册表。适用环境：

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10 1809+ / Windows 11，x64 |
| PowerShell | 5.1（系统自带）或更高 |
| 权限 | 普通用户；不请求 UAC 提权 |
| 依赖 | 预编译包无需 Python；源码运行需 Python 3.10+ |

## 一、安装

### 1.1 从 Release 包安装（推荐）

```text
WorkBuddyTokenCost-5.0.1-win64.zip
├── WorkBuddyTokenCost.exe
├── WorkBuddyTokenCost_CLI.exe
├── LICENSE
├── README.md
├── INSTALL.md
├── SHA256SUMS.txt
└── installer\
    ├── install.cmd
    ├── install.ps1
    ├── uninstall.cmd
    └── uninstall.ps1
```

解压后双击 `installer\install.cmd`，按提示完成安装。安装器会：

1. 若发现程序正在运行，询问是否关闭（静默模式下自动关闭）。
2. 复制程序与卸载器到 `%LOCALAPPDATA%\Programs\WorkBuddyTokenCost`。
3. 创建桌面快捷方式与开始菜单项（GUI + CLI）。
4. 在「设置 → 应用 → 已安装的应用」注册卸载入口。
5. 可选把安装目录加入当前用户 `PATH`。

### 1.2 从仓库源码安装

先构建，再安装：

```powershell
python -m pip install -r requirements-dev.txt
.\build.cmd
.\installer\install.cmd
```

安装器会依次在脚本目录、`..\dist`、`..` 查找 `WorkBuddyTokenCost.exe`；
也可以显式指定：

```powershell
.\installer\install.ps1 -SourceDir .\dist
```

### 1.3 静默安装（批量部署）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\installer\install.ps1 -Silent -AddToPath
```

### 1.4 参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `-SourceDir` | 路径 | 自动探测 | 包含两个 exe 的目录 |
| `-InstallDir` | 路径 | `%LOCALAPPDATA%\Programs\WorkBuddyTokenCost` | 安装目录；禁止系统目录与磁盘根目录 |
| `-AddToPath` | 开关 | 关 | 将安装目录追加到当前用户 `PATH`，新终端生效 |
| `-NoShortcuts` | 开关 | 关 | 不创建桌面/开始菜单快捷方式（便携或 CI 用） |
| `-Silent` | 开关 | 关 | 不交互；自动关闭正在运行的实例 |

安装器会在 `-SourceDir` 中发现 `SHA256SUMS.txt` 时逐个校验文件哈希，不匹配则拒绝安装。

### 1.5 安装足迹

| 类别 | 位置 |
|---|---|
| 程序文件 | `%LOCALAPPDATA%\Programs\WorkBuddyTokenCost\` |
| 桌面快捷方式 | `%USERPROFILE%\Desktop\WorkBuddy Token Cost.lnk` |
| 开始菜单 | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\WorkBuddyTokenCost\` |
| 卸载注册项 | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\WorkBuddyTokenCost` |
| PATH（可选） | 当前用户 `Path` 环境变量追加一项 |
| 运行日志 | `%TEMP%\WorkBuddyTokenCost_gui_error.log`（仅 GUI 崩溃时生成） |

不安装服务、驱动、计划任务，不修改系统级环境变量，不触碰 `~/.workbuddy` 数据。

## 二、卸载

### 2.1 常规卸载

「设置 → 应用 → 已安装的应用 → WorkBuddy Token Cost → 卸载」。

### 2.2 脚本卸载

```powershell
# 交互式（会二次确认）
.\installer\uninstall.cmd

# 静默
powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\uninstall.ps1 -Silent
```

安装目录内保留了一份 `uninstall.ps1`，即使原始压缩包已删除也能卸载：

```powershell
& "$env:LOCALAPPDATA\Programs\WorkBuddyTokenCost\uninstall.ps1"
```

### 2.3 安全护栏

卸载器只删除满足以下任一条件的目录：

- 目录内存在安装器写入的标记文件 `.workbuddy-token-cost`；或
- 目录名恰为 `WorkBuddyTokenCost`。

同时拒绝磁盘根目录、`%SystemRoot%`、`%ProgramFiles%`、`%LOCALAPPDATA%`、
`%APPDATA%`、`%USERPROFILE%` 等受保护路径，避免手误 `-InstallDir` 造成误删。

## 三、常见问题

**双击 `install.cmd` 一闪而过 / 提示脚本被策略禁止**

`.cmd` 已使用 `-ExecutionPolicy Bypass` 启动 PowerShell。若仍被组策略拦截，请让管理员
检查 `MachinePolicy` 下的执行策略；不要全局改为 `Unrestricted`。

**Windows 提示「已保护你的电脑」**

发布包未做代码签名，SmartScreen 会拦截。确认来源与 `SHA256SUMS.txt` 后，选择
「更多信息 → 仍要运行」。正式分发建议使用代码签名证书。

**杀毒软件误报**

PyInstaller 单文件程序容易被启发式引擎误判。本项目已关闭 UPX 压缩以降低误报率；
如仍被拦截，请将文件哈希提交给厂商，或从源码运行。

**提示找不到 `WorkBuddyTokenCost.exe`**

说明当前目录没有构建产物。先运行 `.\build.ps1`，或从 Release 包解压后安装，
也可以用 `-SourceDir` 指向 exe 所在目录。

**可以装到 `Program Files` 吗？**

不建议。安装器按用户设计，写入 `Program Files` 需要管理员权限，且卸载注册项写在
`HKCU`，会造成不一致。多用户机器请让每位用户各自安装。

**卸载后 `PATH` 里还有残留？**

只有在安装时使用了 `-AddToPath` 才会写入；卸载器会移除完全匹配的条目。若曾手工添加
过其它路径，需要自行清理。
