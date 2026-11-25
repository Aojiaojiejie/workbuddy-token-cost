# 安全政策

## 支持的版本

| 版本 | 支持状态 |
|---|---|
| 5.0.x | 接收安全修复 |
| < 5.0 | 不再维护，请升级 |

## 报告漏洞

请通过仓库的 **Security → Report a vulnerability**（GitHub Security Advisories）私下提交，
不要开公开 Issue，也不要在讨论区贴利用细节。

报告中请包含：

- 受影响版本与操作系统；
- 复现步骤或最小样例；
- 影响判断（读取了哪些数据、是否需要本地权限）；
- 如可能，附修复建议。

维护者会在 7 天内确认收到，并在修复发布后于 `CHANGELOG.md` 记录。若 14 天内未回复，
可以再发一次提醒。

## 适用范围

**在范围内**

- 源码、打包配置、安装/卸载脚本中的漏洞；
- 凭据泄露、命令注入、路径穿越、任意文件写入/删除；
- 发布二进制与源码不一致、校验和绕过；
- 安装器提权或误删用户数据。

**不在范围内**

- 费用估算与官方账单的差异（计价口径见 README，属于产品行为）；
- WorkBuddy 客户端、DeepSeek 官网本身的漏洞；
- 需要先取得本机管理员权限或物理访问的攻击场景；
- 依赖上游组件的新披露漏洞（请同时反馈给上游，本项目会跟进升级）。

## 已知边界

- 程序只读 `~/.workbuddy`，不写入、不上传；无网络监听、无遥测。
- 发布二进制未做代码签名，SmartScreen 可能提示；请用 `SHA256SUMS.txt` 校验来源。
- 导出的 CSV/JSON 含会话标题，分享前请自行脱敏。
- 详细审计结论见 [docs/SECURITY-AUDIT.md](docs/SECURITY-AUDIT.md)。

## 依赖安全

发布前维护者会执行：

```powershell
python -m pip_audit -r requirements.txt
python -m pip_audit -r requirements-dev.txt
```

建议启用 Dependabot 自动跟进依赖更新。
