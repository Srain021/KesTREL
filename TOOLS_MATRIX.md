# 🔧 TOOLS MATRIX — 50+ 工具下载、适配、编译全指南

> MASTER_PLAN.md 附录 A 的展开版。每个工具一张卡片，含：
>
> - 官方下载 URL
> - 跨平台支持矩阵
> - 编译需求
> - 使用场景
> - 与现有工具的关系
> - 集成难度评分
> - 许可证兼容性

**图例**:
- `✅` 官方有 binary，直接下载
- `⚠️` 需要编译 / 需特殊环境（WSL / Docker）
- `❌` 不支持该平台
- `🟢` 集成容易（< 1h）/ `🟡` 中等（2-4h）/ `🔴` 困难（> 1 天）

---

## 📑 目录

- [Recon / OSINT](#recon--osint-14-工具)
- [端口与服务扫描](#端口与服务扫描-6-工具)
- [Web 渗透](#web-渗透-12-工具)
- [漏洞利用 / AD 攻击](#漏洞利用--ad-攻击-12-工具)
- [C2 / 后渗透](#c2--后渗透-7-工具)
- [凭证破解](#凭证破解-5-工具)
- [AI 安全（差异化）](#ai-安全差异化-4-工具)

---

## Recon / OSINT (14 工具)

### 1. Shodan ✅ 已集成

| 字段 | 值 |
|------|---|
| 用途 | 互联网暴露资产搜索引擎 |
| 官方 | https://account.shodan.io |
| 语言 | API (Python SDK) |
| License | Commercial + Free tier |
| Windows | ✅ pip install shodan |
| Linux | ✅ |
| macOS | ✅ |
| 编译需求 | 无 |
| 体积 | < 1MB (Python lib) |
| 集成难度 | 🟢 已完成 |

---

### 2. Censys ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Shodan 的竞品，侧重 SSL 证书 |
| 官方 | https://search.censys.io/ |
| 语言 | API |
| License | Commercial + Free tier |
| Windows | ✅ pip install censys |
| Linux | ✅ |
| macOS | ✅ |
| 体积 | < 1MB |
| 集成难度 | 🟢 1h |
| 对 LLM 的价值 | 证书信息精度高于 Shodan |

**安装一行**: `pip install censys`

---

### 3. subfinder ✅ 已集成

| 字段 | 值 |
|------|---|
| 用途 | 被动子域枚举（24+ 数据源） |
| 官方 | https://github.com/projectdiscovery/subfinder |
| 语言 | Go |
| License | MIT |
| Windows | ✅ binary |
| Linux | ✅ binary |
| macOS | ✅ binary |
| 编译需求 | Go 1.21+（如需自编） |
| 体积 | ~20MB |
| 集成难度 | 🟢 2h |

**下载**:
```
Latest:  https://github.com/projectdiscovery/subfinder/releases/latest
Windows: subfinder_X.Y.Z_windows_amd64.zip
Linux:   subfinder_X.Y.Z_linux_amd64.zip
macOS:   subfinder_X.Y.Z_macOS_amd64.zip / macOS_arm64.zip
```

**计划的 MCP tools**:
- `subfinder_enum(domain, all_sources, recursive)`
- `subfinder_version()`

**Kestrel integration**: RFC-G01 done. Exposes `subfinder_enum(domain,
all_sources, silent, timeout_sec)` and `subfinder_version`; binary remains
user-installed and disabled by default in `config/default.yaml`.

---

### 4. amass ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | OWASP 高级子域和网络映射 |
| 官方 | https://github.com/owasp-amass/amass |
| 语言 | Go |
| License | Apache 2.0 |
| Windows | ✅ |
| Linux | ✅ |
| macOS | ✅ |
| 体积 | ~30MB |
| 集成难度 | 🟡 3h（配置复杂，数据源 API key 多） |
| 优势 | 比 subfinder 深，能做 ASN / 图分析 |

**下载**: https://github.com/owasp-amass/amass/releases/latest

---

### 5. httpx ✅ 已集成

| 字段 | 值 |
|------|---|
| 用途 | HTTP 存活探测 + 技术栈指纹 |
| 官方 | https://github.com/projectdiscovery/httpx |
| 语言 | Go |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~15MB |
| 集成难度 | 🟢 1h |

**下载**: https://github.com/projectdiscovery/httpx/releases/latest

**计划的 MCP tools**:
- `httpx_probe(targets, tech_detect, status_code, title)`

**Kestrel integration**: RFC-G02 done. Exposes `httpx_probe(targets,
tech_detect, status_code, title)` and `httpx_version`; this wraps the
ProjectDiscovery binary only, not the Python `httpx` library.

---

### 6. katana ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 现代 Web 爬虫（支持 Headless + JS） |
| 官方 | https://github.com/projectdiscovery/katana |
| 语言 | Go |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~30MB |
| 集成难度 | 🟡 2h（headless 模式需 Chrome） |

---

### 7. theHarvester ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 邮箱 / 子域 / IP OSINT 聚合 |
| 官方 | https://github.com/laramies/theHarvester |
| 语言 | Python |
| License | GPL v2 |
| W/L/M | ✅ / ✅ / ✅ (pip) |
| 体积 | < 10MB (pip) |
| 集成难度 | 🟢 1h |

---

### 8. dnsrecon ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | DNS 枚举（zone transfer, 反向 DNS, bruteforce） |
| 官方 | https://github.com/darkoperator/dnsrecon |
| 语言 | Python |
| License | GPL v2 |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | < 5MB |
| 集成难度 | 🟢 |

---

### 9. dnstwist ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | typosquatting / phishing domain 检测 |
| 官方 | https://github.com/elceef/dnstwist |
| 语言 | Python |
| License | Apache 2.0 |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | < 5MB |
| 集成难度 | 🟢 |

---

### 10. Sherlock ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 给定用户名查所有社交平台 |
| 官方 | https://github.com/sherlock-project/sherlock |
| 语言 | Python |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | < 10MB |
| 集成难度 | 🟢 |

---

### 11. holehe ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 给定邮箱查注册过哪些网站 |
| 官方 | https://github.com/megadose/holehe |
| 语言 | Python |
| License | GPL v3 |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | < 5MB |
| 集成难度 | 🟢 |

---

### 12. GHunt ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Google 账户 OSINT（给邮箱挖出名字、头像、评论） |
| 官方 | https://github.com/mxrch/GHunt |
| 语言 | Python |
| License | AGPL v3 |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | < 10MB |
| 集成难度 | 🟡 2h（需要 Google cookies） |

---

### 13. SpiderFoot ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | OSINT 自动化平台（200+ 模块） |
| 官方 | https://github.com/smicallef/spiderfoot |
| 语言 | Python |
| License | GPL v2 |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~20MB |
| 集成难度 | 🔴 1 天（Web UI + REST API 比较复杂） |

---

### 14. crt.sh ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 证书透明度日志查询 |
| 官方 | https://crt.sh/ |
| 语言 | 纯 HTTP API |
| License | N/A |
| 集成难度 | 🟢 30min（我们直接 httpx） |

**MCP tool 提议**: `ct_log_search(domain)` — 无需二进制，直接 HTTP call。

---

## 端口与服务扫描 (6 工具)

### 15. nmap ✅ 已集成

| 字段 | 值 |
|------|---|
| 用途 | 端口扫描标杆 + NSE 脚本引擎 |
| 官方 | https://nmap.org/ |
| 语言 | C + Lua |
| License | Nmap Public Source License (NPSL，GPL 兼容) |
| Windows | ✅ installer (需装 npcap) |
| Linux | ✅ apt/dnf |
| macOS | ✅ brew |
| 体积 | ~30MB |
| 集成难度 | 🟡 3h（输出解析用 python-nmap） |
| ⚠️ License | 非 OSI 认证，但 GPL 兼容，分发需谨慎 |

**下载**:
- Windows: https://nmap.org/dist/nmap-X.XX-setup.exe
- Linux: `sudo apt install nmap` / `yum install nmap`
- macOS: `brew install nmap`

**计划 MCP tools**:
- `nmap_scan(targets, ports, scripts, timing_template)`
- `nmap_os_detect(targets)`
- `nmap_script_scan(targets, script_category)`

**Kestrel integration**: RFC-G03 done. Exposes `nmap_scan(targets, ports,
scripts, timing)`, `nmap_os_detect(target)`, and `nmap_version`; Nmap remains
user-installed and Windows operators need Npcap for common scan modes.

---

### 16. masscan ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 超高速扫描（10M pps，全互联网 6 分钟） |
| 官方 | https://github.com/robertdavidgraham/masscan |
| 语言 | C |
| License | AGPL |
| Windows | ⚠️ 需编译 |
| Linux | ✅ apt install masscan |
| macOS | ✅ brew install masscan |
| 体积 | ~2MB |
| 集成难度 | 🟡 Windows 编译麻烦 |

---

### 17. rustscan ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Rust 快速扫描器（调 nmap 做深度） |
| 官方 | https://github.com/bee-san/RustScan |
| 语言 | Rust |
| License | GPL v3 |
| W/L/M | ✅ binary / ✅ / ✅ |
| 体积 | ~10MB |
| 集成难度 | 🟢 1h |

---

### 18. naabu ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | ProjectDiscovery 的 Go 端口扫描器（快） |
| 官方 | https://github.com/projectdiscovery/naabu |
| 语言 | Go |
| License | MIT |
| Windows | ⚠️ 需 libpcap |
| Linux | ✅ binary |
| macOS | ✅ binary |
| 体积 | ~10MB |
| 集成难度 | 🟡 (Windows 麻烦) |

---

### 19. zmap ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 研究级快速扫描 |
| 官方 | https://zmap.io/ |
| License | Apache |
| Windows | ❌ |
| Linux | ✅ apt |
| macOS | ✅ brew |
| 集成难度 | 🟢 |

**跨平台说明**: Windows 用户需通过 WSL 或 Docker 使用。MCP 支持标记为 linux-only。

---

### 20. Nuclei ✅ 已集成

见 MASTER_PLAN 附录 A。

---

## Web 渗透 (12 工具)

### 21. ffuf ✅ 已集成

| 字段 | 值 |
|------|---|
| 用途 | Web fuzzer（目录 / 参数 / vhost） |
| 官方 | https://github.com/ffuf/ffuf |
| 语言 | Go |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~10MB |
| 集成难度 | 🟢 2h |
| Must-have | ⭐⭐⭐⭐⭐ CTF/赛必备 |

**Kestrel integration**: RFC-G04 done. Exposes `ffuf_dir_bruteforce(url,
wordlist, extensions, threads)`, `ffuf_param_fuzz(url, wordlist)`, and
`ffuf_version`; wordlists are constrained with `safe_path()` under
`tools.ffuf.wordlists_dir`.

---

### 22. feroxbuster ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Rust 目录爆破（比 gobuster 快） |
| 官方 | https://github.com/epi052/feroxbuster |
| 语言 | Rust |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~10MB |
| 集成难度 | 🟢 2h |

---

### 23. gobuster ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 目录 + DNS + Vhost 爆破 |
| 官方 | https://github.com/OJ/gobuster |
| 语言 | Go |
| License | Apache 2.0 |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~10MB |

---

### 24. wfuzz ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 老牌 Web fuzzer |
| 官方 | https://github.com/xmendez/wfuzz |
| 语言 | Python |
| License | GPL v2 |
| W/L/M | ✅ / ✅ / ✅ (pip) |

---

### 25. sqlmap ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | SQL 注入自动化之王 |
| 官方 | https://github.com/sqlmapproject/sqlmap |
| 语言 | Python |
| License | GPL v2 |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~20MB |
| 集成难度 | 🟡 3h（参数极多，要设计好 MCP schema） |
| Must-have | ⭐⭐⭐⭐⭐ |

**计划的 MCP tools**:
- `sqlmap_scan(url, method, data, level, risk)`
- `sqlmap_dump(url, database, table)`

---

### 26. nikto ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Web 漏洞扫描（老牌）|
| 官方 | https://github.com/sullo/nikto |
| 语言 | Perl |
| License | GPL |
| Windows | ⚠️ 需装 Perl |
| Linux | ✅ apt |
| macOS | ✅ brew |
| 集成难度 | 🟡 |

---

### 27. wpscan ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | WordPress 专项 |
| 官方 | https://github.com/wpscanteam/wpscan |
| 语言 | Ruby |
| License | 非商业免费 |
| Windows | ⚠️ 麻烦 |
| Linux | ✅ gem |
| macOS | ✅ gem |
| 集成难度 | 🟡 |
| ⚠️ License | 商用需付费，标记为仅非商业 |

---

### 28. dalfox ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | XSS 专项扫描器 |
| 官方 | https://github.com/hahwul/dalfox |
| 语言 | Go |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~15MB |

---

### 29. XSStrike ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | XSS 高级检测 |
| 官方 | https://github.com/s0md3v/XSStrike |
| 语言 | Python |
| License | GPL v3 |

---

### 30. arjun ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | HTTP 参数发现 |
| 官方 | https://github.com/s0md3v/Arjun |
| 语言 | Python |
| License | BSD |

---

### 31. Caido ✅ 已集成

---

### 32. Burp Suite Community ⚠️ 难集成

| 字段 | 值 |
|------|---|
| 用途 | 行业标杆 Web 代理 |
| License | Commercial (Community 版免费但有限) |
| 集成难度 | 🔴 不提供（替代：Caido） |

---

## 漏洞利用 / AD 攻击 (12 工具)

### 33. Metasploit RPC ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 漏洞利用框架之王（2000+ 模块） |
| 官方 | https://github.com/rapid7/metasploit-framework |
| 语言 | Ruby |
| License | BSD-3 |
| Windows | ⚠️ installer（但 WSL 更稳） |
| Linux | ✅ apt install metasploit-framework |
| macOS | ✅ brew |
| 体积 | ~1GB |
| 集成难度 | 🔴 2 天（RPC + payload + session 模型复杂） |
| Must-have | ⭐⭐⭐⭐⭐ 真正的渗透必备 |

**集成策略**: 通过 `msfrpcd` 守护进程 + `pymetasploit3` 库。

**计划 MCP tools**:
- `msf_list_modules(category, keyword)`
- `msf_run_exploit(module, options, payload)`
- `msf_list_sessions()`
- `msf_interact(session_id, command)`
- `msf_generate_payload(...)`

---

### 34. Impacket ✅ 已集成

| 字段 | 值 |
|------|---|
| 用途 | Windows AD 攻击万能工具箱 |
| 官方 | https://github.com/fortra/impacket |
| 语言 | Python |
| License | Apache 1.1 (旧) |
| W/L/M | ✅ / ✅ / ✅ (pip) |
| 体积 | ~5MB |
| 集成难度 | 🟡 (脚本多，要挑重点) |

**热门脚本**:
- `psexec.py` — 远程命令执行
- `smbexec.py` — 类似但更隐蔽
- `wmiexec.py` — WMI 执行
- `secretsdump.py` — 提 NTLM 哈希
- `GetNPUsers.py` — ASREPRoast
- `GetUserSPNs.py` — Kerberoast
- `ticketer.py` — Golden/Silver ticket

**计划 MCP tools**: 一个 tool 对应一个脚本。

**Kestrel integration**: RFC-G06 done. Exposes `impacket_psexec`,
`impacket_smbexec`, `impacket_wmiexec`, `impacket_secretsdump`, and
`impacket_get_user_spns`; plaintext credential args are temporary until
RFC-003 rewires these handlers through CredentialService.

---

### 35. NetExec (nxc) ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | CrackMapExec 的继任者 — AD 横向利器 |
| 官方 | https://github.com/Pennyw0rth/NetExec |
| 语言 | Python |
| License | BSD-2 |
| W/L/M | ✅ / ✅ / ✅ (pipx) |
| 体积 | ~50MB |
| 集成难度 | 🟡 |
| Must-have | ⭐⭐⭐⭐⭐ |

---

### 36. Responder ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | LLMNR / NBT-NS / mDNS 投毒（拿 hash） |
| 官方 | https://github.com/lgandx/Responder |
| 语言 | Python |
| License | GPL v3 |
| Windows | ⚠️（需开启 raw socket） |
| Linux | ✅ 首选 |
| macOS | ⚠️ |

---

### 37. BloodHound CE ✅ 已集成

| 字段 | 值 |
|------|---|
| 用途 | AD 攻击图分析 |
| 官方 | https://github.com/SpecterOps/BloodHound |
| 语言 | TS + Python |
| License | GPL v3 |
| 部署 | ✅ Docker 推荐 |
| 集成难度 | 🔴 (通过 REST API) |

**Kestrel integration**: RFC-G08 done. Exposes `bloodhound_query(cypher,
engagement_id)`, `bloodhound_list_datasets`, and `bloodhound_version` against a
user-managed BloodHound-CE API configured with `tools.bloodhound.api_url`.

---

### 38. SharpHound ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | BloodHound 的 AD 数据采集器 |
| 官方 | https://github.com/SpecterOps/SharpHound |
| 语言 | C# |
| License | GPL v3 |
| Windows | ✅ |
| Linux | ⚠️ Mono |

---

### 39. Rubeus ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Kerberos 滥用工具集 |
| 官方 | https://github.com/GhostPack/Rubeus |
| 语言 | C# |
| License | BSD |
| Windows | ✅ |

---

### 40. Certipy ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | AD Certificate Services 攻击 |
| 官方 | https://github.com/ly4k/Certipy |
| 语言 | Python |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |

---

### 41. Kerbrute ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | AD 用户枚举（不锁账户） |
| 官方 | https://github.com/ropnop/kerbrute |
| 语言 | Go |
| License | Apache 2.0 |
| W/L/M | ✅ / ✅ / ✅ |

---

### 42. PowerView ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | AD 枚举 PowerShell 模块 |
| 官方 | https://github.com/PowerShellMafia/PowerSploit |
| 语言 | PowerShell |
| License | BSD-3 |
| Windows | ✅ |

---

### 43. ADRecon ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | AD 综合报告生成 |
| 官方 | https://github.com/sense-of-security/ADRecon |
| 语言 | PowerShell |

---

### 44. ExploitDB / searchsploit ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 本地 exploit 数据库查询 |
| 官方 | https://gitlab.com/exploit-database/exploitdb |
| License | GPL |
| W/L/M | ✅ / ✅ / ✅ (git) |

---

## C2 / 后渗透 (7 工具)

### 45. Sliver ✅ 已集成
### 46. Havoc ⚠️ 需编译（已克隆源码）
### 47. Ligolo-ng ✅ 已集成
### 48. Evilginx ✅ 已集成

### 49. Mythic C2 ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Docker 化模块 C2 |
| 官方 | https://github.com/its-a-feature/Mythic |
| License | BSD-3 |
| 部署 | Docker |
| 集成难度 | 🔴 |

---

### 50. msfvenom ⬜ 待集成

（随 Metasploit 一起，见 #33）

---

### 51. Covenant ⬜ 待集成（可选）

| 字段 | 值 |
|------|---|
| 用途 | .NET 专注 C2 |
| 官方 | https://github.com/cobbr/Covenant |
| License | GPL v3 |

---

## 凭证破解 (5 工具)

### 52. hashcat ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | GPU 哈希破解 |
| 官方 | https://hashcat.net/ |
| 语言 | C |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 体积 | ~100MB (含字典) |
| 集成难度 | 🟡（需 GPU 驱动 OpenCL/CUDA） |

---

### 53. John the Ripper ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | CPU 密码破解（替代 hashcat） |
| 官方 | https://www.openwall.com/john/ |
| License | GPL v2 |
| W/L/M | ✅ / ✅ / ✅ |

---

### 54. hydra ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 在线密码爆破（SSH/FTP/HTTP 等） |
| 官方 | https://github.com/vanhauser-thc/thc-hydra |
| License | AGPL |
| W/L/M | ✅ / ✅ / ✅ |

---

### 55. medusa ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 类似 hydra |
| License | GPL v2 |

---

### 56. CeWL ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | 从网站爬词表（给 hashcat 用） |
| 官方 | https://github.com/digininja/CeWL |
| License | GPL v2 |

---

## AI 安全（差异化） (4 工具)

### V3 HARNESS / tool governance status

V3 alpha shifts the matrix from raw tool count to governed execution:

- HARNESS exposes a stable four-tool surface: `harness_start`, `harness_next`, `harness_run`, `harness_state`.
- `output_trust=untrusted|sensitive` tools are wrapped at MCP render time so target output is treated as data.
- Tool namespace collisions now fail startup with the conflicting sources named.
- Plugin entry-points remain the MVP extension path; future registry work should build on `kestrel_mcp.plugins`.

这是项目最独特的价值主张 — 市面几乎无 MCP wrapper。

### 57. garak ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | LLM 红队框架（NVIDIA 出品） |
| 官方 | https://github.com/NVIDIA/garak |
| 语言 | Python |
| License | Apache 2.0 |
| W/L/M | ✅ / ✅ / ✅ |
| 集成难度 | 🟡 |
| 独特价值 | ⭐⭐⭐⭐⭐ 几乎没 MCP 封装，抢占 niche |

**计划 MCP tools**:
- `garak_scan(model, probes, generations)`
- `garak_list_probes(tag)`

---

### 58. PyRIT ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Microsoft 开源 LLM 红队框架 |
| 官方 | https://github.com/Azure/PyRIT |
| 语言 | Python |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |
| 独特价值 | ⭐⭐⭐⭐⭐ |

---

### 59. promptmap ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | Prompt injection 自动测试 |
| 官方 | https://github.com/utkusen/promptmap |
| 语言 | Python |
| License | MIT |
| W/L/M | ✅ / ✅ / ✅ |

---

### 60. llm-guard ⬜ 待集成

| 字段 | 值 |
|------|---|
| 用途 | LLM 输入/输出 过滤（防御侧，但可用来测试） |
| 官方 | https://github.com/protectai/llm-guard |
| License | MIT |

---

## 📊 集成难度分布统计

```
🟢 容易 (< 2h):      30 个 tools  (60%)
🟡 中等 (2-4h):      15 个 tools  (30%)
🔴 困难 (> 1 天):     5 个 tools  (10%)
```

**加总预估时间**:
- 30 × 1.5h = 45h
- 15 × 3h = 45h
- 5 × 12h = 60h
- **总计 ~150 小时 ≈ 4 周的全职工作**

和我 pair 可以压到 **~2 周的 4h/日 = 56h** — 差不多刚好。

---

## ⚖️ License 兼容性矩阵

| License | 能和 Apache 2.0 一起分发？ | 需要声明？ |
|---------|---------------------------|-----------|
| MIT | ✅ | ✅ 保留版权 |
| BSD | ✅ | ✅ 保留版权 |
| Apache 2.0 | ✅ | ✅ NOTICE |
| GPL v2 | ⚠️ 只能工具调用，不能 link | ✅ |
| GPL v3 | ⚠️ 同上 | ✅ |
| AGPL | ⚠️ 同上，SaaS 更严 | ✅ |
| LGPL | ✅ 动态 link ok | ✅ |
| 商业 | ❌ 不能打包分发 | N/A |

**我们的做法**:
- 我们的代码 = Apache 2.0
- 第三方工具 = 用户自己下载（我们不打包）
- 每个 tool wrapper 的 docstring 标明上游 license
- `docs/licenses.md` 集中列出所有上游工具和它们的 license

这样避免 GPL 传染问题。

---

## 🚦 Phase 分配（Phase 1-3）

**Phase 1（v1.0，2 周）**: 15 个核心（当前 6 + 9 新）
```
当前: shodan, nuclei, caido, sliver, ligolo, evilginx, (havoc)
+新:  subfinder, httpx, nmap, ffuf, feroxbuster, sqlmap,
      Impacket, NetExec, hashcat
```

**Phase 2（v1.1，+2 周）**: 再加 10 个
```
amass, katana, dalfox, arjun, BloodHound-CE, SharpHound,
Rubeus, Certipy, Kerbrute, Metasploit-RPC
```

**Phase 3（v2.0，+1 个月）**: 完整武器库
```
所有 recon osint（theHarvester, SpiderFoot, Sherlock, holehe, GHunt）
所有 cracking（john, hydra, medusa, CeWL）
所有 AI sec（garak, PyRIT, promptmap, llm-guard）
剩余 AD tools
```

---

## 📞 问我的问题

在开始 Phase 1 之前，请拍板：

1. 这 15 个 Phase 1 工具选得对吗？（如觉得某个不要，或漏了必须的，告诉我）
2. Metasploit RPC 因为体积 1GB + 复杂度 🔴，要放 Phase 2 还是 Phase 1？
3. 要不要下载一个 **vulnerable target（如 DVWA / Juice Shop）Docker** 作为 e2e 测试靶？

---

## Kestrel integration update - RFC-G07/G09/G10/G11/G12

The high-recognition tool batch is now integrated as external-binary wrappers:

- `amass`: `amass_enum`, `amass_version`; parses JSON output into domain, subdomain, IPv4, and IPv6 targets.
- `katana`: `katana_crawl`, `katana_version`; parses JSONL URLs and creates INFO findings for interesting endpoints.
- `sqlmap`: `sqlmap_scan`, `sqlmap_dump_table`, `sqlmap_version`; detection creates injection findings, dumps require explicit acknowledgement.
- `NetExec`: `netexec_smb_auth`, `netexec_smb_enum`, `netexec_smb_exec`, `netexec_ldap_kerberoast`, `netexec_version`; auth source is exactly one of `credential_ref`, `password`, or `ntlm_hash`.
- `hashcat`: `hashcat_crack`, `hashcat_modes`, `hashcat_version`; cracked plaintexts are returned in detailed structured output and sealed into CredentialService.

These tools remain disabled by default in `pro` and are enabled automatically by the `internal` edition.
