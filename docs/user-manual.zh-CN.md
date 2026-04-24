# Kestrel MCP 详细使用说明书

## 1. 项目简介

Kestrel MCP 是一个面向授权安全测试场景的 MCP 服务器。它把侦察、扫描、信息收集、资产管理、发现流转、报告生成等能力统一暴露给支持 MCP 的 LLM 客户端，例如 Cursor、Claude Desktop、Cline、Continue、Zed。

它的核心价值不只是“把命令包起来”，而是把下面这些约束一起带上：

- 作用域校验：高风险工具会在执行前检查目标是否在授权范围内。
- 审计记录：每次工具调用都会留下结构化日志，并写入带 SHA-256 hash chain 的 `tool_invocation` 审计链。
- 统一配置：YAML、环境变量、CLI 参数共用一套配置模型。
- Engagement 工作流：把一次测试任务拆成 Engagement、Scope、Target、Finding 等实体。
- 分级运行模式：`pro`、`team`、`internal` 三种 Edition 对安全策略和工具面有不同默认值。

当前代码中，默认可暴露的能力大致分为 11 组：

| 类别 | 说明 |
|---|---|
| Engagement / Scope / Target / Finding | 管理测试任务、范围、目标和发现 |
| Readiness | 做攻击准备度评估、火控审批包、证据打包 |
| Shodan | 被动情报检索 |
| Nuclei | 模板化漏洞扫描 |
| Subfinder / httpx / Nmap / ffuf | 子域名枚举、HTTP 探测、端口扫描、目录与参数探测 |
| Impacket | Windows / AD 远程执行与凭据相关操作 |
| BloodHound / Caido | 图关系数据查询、代理/重放类辅助能力 |
| Ligolo / Sliver / Havoc / Evilginx | 隧道、C2、团队服务器、钓鱼与对抗框架 |
| Workflow | `recon_target`、`full_vuln_scan`、`exploit_chain`、`generate_pentest_report` 这类组合型工具 |
| MCP Resources / Prompts | 供 MCP Host 按需读取的 engagement 上下文资源与预置提示词 |
| Web UI / HTTP Transport | 面向浏览器和反向代理的访问层 |

## 2. 核心概念

在真正使用前，先理解 6 个概念：

### 2.1 Edition

Edition 决定系统默认的安全策略。

| Edition | 特点 |
|---|---|
| `pro` | 最保守，适合严格授权与合规场景 |
| `team` | 更偏内部团队协作，默认放宽部分运行时限制 |
| `internal` | 在 `team` 的安全策略基础上，额外默认启用全部内置工具模块 |

代码里的差异点主要在这里：

- `pro` 默认 `scope_enforcement = strict`
- `team` 默认 `scope_enforcement = warn_only`
- `team` 和 `internal` 默认关闭速率限制与软超时
- `internal` 会自动打开所有已内置的工具模块

注意：`team` 不等于“自动启用所有工具”。如果你只切到 `team`，但没有在配置里把 `subfinder`、`httpx`、`nmap`、`ffuf`、`impacket` 等工具打开，它们仍然可能是关闭状态。想要“一次性全开”，优先用 `internal`。

### 2.2 Engagement

Engagement 是一次测试活动的顶层容器。它保存：

- 客户与任务信息
- 状态：`planning`、`active`、`paused`、`closed`
- 作用域
- 资产目标
- 发现与证据
- 凭据与工具调用轨迹

如果你准备长期使用这个项目，建议把每次任务都放在单独的 Engagement 里，而不是只靠全局 `authorized_scope`。

### 2.3 Scope

Scope 是授权边界。它支持：

- 精确主机名，例如 `app.example.com`
- 通配符主机名，例如 `*.example.com`
- 含 apex 的通配符，例如 `.example.com`
- 单个 IP，例如 `192.168.56.10`
- CIDR，例如 `192.168.56.0/24`
- URL

如果高风险工具收到的目标不在 Scope 内，`pro` 模式下会直接拒绝；`team` / `internal` 默认是记日志并放行。

### 2.4 Target

Target 是某个具体资产，可以是域名、子域名、URL、IPv4、IPv6、应用、组织、邮箱等。很多侦察结果都应该沉淀为 Target，而不是只留在终端输出里。

### 2.5 Finding

Finding 是一个发现项，带有：

- 严重级别
- 状态流转
- 证据
- 修复建议
- CVE / CWE / CVSS 等字段

它不是“扫描输出原样转存”，而是后续报告、评估、审批和流转的核心对象。

### 2.6 Readiness / Fire Control

这部分工具不执行攻击动作，而是回答：

- 这个发现值得先验证吗？
- 是否需要人工审批？
- 证据是否足够？
- 下一步应该补哪类材料？

如果你把 Kestrel MCP 接到 LLM 上，建议把这些工具当成危险操作前的“缓冲层”。

## 3. 安装前准备

### 3.1 运行环境

- Python `3.10+`
- 推荐使用仓库自带 `.venv` 或独立虚拟环境
- Windows 下建议 PowerShell 5.1+ 或 PowerShell 7+
- 如需高级工具，需自行安装对应二进制或 Python 包

### 3.2 常见外部工具

不是所有工具都强制安装。你只需要为要启用的模块准备对应依赖。

| 模块 | 依赖 |
|---|---|
| `shodan` | Shodan Python SDK + `SHODAN_API_KEY` |
| `nuclei` | `nuclei` 可执行文件 |
| `subfinder` | `subfinder` 可执行文件 |
| `httpx` | ProjectDiscovery `httpx` 可执行文件 |
| `nmap` | `nmap` 可执行文件 |
| `ffuf` | `ffuf` 可执行文件 |
| `impacket` | `impacket` Python 包 |
| `bloodhound` | BloodHound CE API |
| `caido` / `evilginx` / `sliver` / `havoc` / `ligolo` | 各自的二进制与运行环境 |

### 3.3 推荐安装方式

#### Windows

```powershell
cd "d:\TG PROJECT\redteam-mcp"
.\.venv\Scripts\python.exe -m pip install -U pip wheel setuptools
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

如果你还没有虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip wheel setuptools
python -m pip install -e ".[dev]"
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel setuptools
python -m pip install -e ".[dev]"
```

#### 使用 `uv` 同步锁定依赖

这是更推荐的方式，尤其适合多人协作与可复现环境：

```powershell
uv sync --frozen --all-extras
```

## 4. 安装后立即验证

先确认基础命令可用：

```powershell
.\.venv\Scripts\python.exe -m kestrel_mcp version
.\.venv\Scripts\python.exe -m kestrel_mcp doctor
.\.venv\Scripts\python.exe -m kestrel_mcp show-config
.\.venv\Scripts\python.exe -m kestrel_mcp list-tools
```

如果你的环境变量里已经有 `KESTREL_EDITION`、`KESTREL_MCP_EDITION`、用户级 `config.yaml` 或项目级 `kestrel.yaml`，`show-config` 输出的结果可能和你“以为的默认值”不一样。遇到这种情况，先以 `show-config` 为准。

## 5. 最小可用配置

当前代码里最可靠的方式是使用 `kestrel.yaml` 或嵌套环境变量，而不是旧文档中的扁平旧变量名。

在仓库根目录创建 `kestrel.yaml`：

```yaml
edition: pro

security:
  authorized_scope:
    - ".lab.internal"
    - "192.168.56.0/24"
    - "127.0.0.1"

logging:
  level: INFO
  format: json

tools:
  shodan:
    enabled: true
  nuclei:
    enabled: true
  subfinder:
    enabled: true
    binary: "C:/Users/YOU/go/bin/subfinder.exe"
  httpx:
    enabled: true
    binary: "C:/Users/YOU/go/bin/httpx.exe"
  nmap:
    enabled: true
    binary: "C:/Program Files (x86)/Nmap/nmap.exe"
  ffuf:
    enabled: true
    binary: "C:/Users/YOU/go/bin/ffuf.exe"
  impacket:
    enabled: true
```

如果你只做最小启动，也可以先只留：

- `edition`
- `security.authorized_scope`
- `tools.shodan.enabled`
- `tools.nuclei.enabled`

## 6. 环境变量说明

### 6.1 配置优先级

当前代码的配置加载顺序是：

1. `config/default.yaml`
2. `~/.kestrel/config.yaml`
3. `./kestrel.yaml`
4. `KESTREL_MCP_*` 环境变量
5. 部分 CLI 参数，例如 `--scope`、`--dry-run`

### 6.2 推荐环境变量

| 变量名 | 用途 |
|---|---|
| `KESTREL_EDITION` 或 `KESTREL_MCP_EDITION` | 选择 `pro` / `team` / `internal` |
| `KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE` | 全局授权范围，逗号分隔或 JSON 数组 |
| `SHODAN_API_KEY` | 启用 Shodan 工具 |
| `KESTREL_MCP_TOOLS__NUCLEI__BINARY` | 指定 `nuclei` 路径 |
| `KESTREL_MCP_TOOLS__SUBFINDER__BINARY` | 指定 `subfinder` 路径 |
| `KESTREL_MCP_TOOLS__HTTPX__BINARY` | 指定 `httpx` 路径 |
| `KESTREL_MCP_TOOLS__NMAP__BINARY` | 指定 `nmap` 路径 |
| `KESTREL_MCP_TOOLS__FFUF__BINARY` | 指定 `ffuf` 路径 |
| `KESTREL_MCP_TOOLS__IMPACKET__ENABLED` | 打开 `impacket` 模块 |
| `KESTREL_MCP_HTTP_TOKEN` | `serve-http` 的 Bearer Token |
| `KESTREL_ENGAGEMENT` | 默认活动 Engagement |
| `KESTREL_DATA_DIR` | 数据目录，默认 `~/.kestrel` |
| `KESTREL_WEB_USER` / `KESTREL_WEB_PASS` | Web UI Basic Auth 凭据 |

### 6.3 关于旧变量名

你可能会在旧文档、旧脚本或报错文案里看到这类名字：

- `KESTREL_MCP_AUTHORIZED_SCOPE`
- `KESTREL_MCP_TOOL_NUCLEI`
- `KESTREL_MCP_TOOL_HAVOC`

当前配置模型优先建议使用新的嵌套写法：

- `KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE`
- `KESTREL_MCP_TOOLS__NUCLEI__BINARY`
- `KESTREL_MCP_TOOLS__HAVOC__BINARY`

如果你发现“明明设置了环境变量但不生效”，优先检查是否用了旧写法。

## 7. 启动方式

### 7.1 标准 MCP `stdio` 模式

这是最常用的模式，适合 Cursor、Claude Desktop 等本地 MCP 客户端：

```powershell
.\.venv\Scripts\python.exe -m kestrel_mcp serve
```

或者直接用安装后的脚本入口：

```powershell
kestrel serve
```

常用参数：

```powershell
kestrel serve --dry-run
kestrel serve --scope "*.lab.internal,192.168.56.0/24"
kestrel --edition internal serve
```

说明：

- `--dry-run` 会保留调用链，但不真正执行高风险动作。
- `--scope` 是一次性覆盖，比修改配置快，适合临时验证。
- 如果你已经设置了 `KESTREL_EDITION`，`show-config` 能帮助你确认最终加载到的 Edition。

### 7.2 Streamable HTTP 模式

适合反向代理、团队共享、远程 MCP 接入：

```powershell
$env:KESTREL_MCP_HTTP_TOKEN = "replace-with-a-long-random-token"
kestrel serve-http --host 127.0.0.1 --port 8765 --endpoint /mcp
```

常见变体：

```powershell
kestrel serve-http --json-response
kestrel serve-http --stateless
kestrel serve-http --allowed-host mcp.example.com --dns-rebinding-protection
```

要点：

- 如果没有显式传 `--allow-no-auth`，就必须提供 `KESTREL_MCP_HTTP_TOKEN`。
- 这个接口默认提供 `GET`、`POST`、`DELETE` 到 `/mcp`。
- 健康检查地址是 `/__healthz`。

### 7.3 Team Bootstrap

如果你是团队模式，想快速初始化一个 Engagement：

```powershell
kestrel --edition team team bootstrap --name op-winter-2026 --scope "target.lab,*.internal"
```

如果你希望默认启用全部内置工具模块，更适合：

```powershell
kestrel --edition internal team bootstrap --name op-firepower --scope "target.lab,*.internal"
```

执行完成后，通常还要再设置活动 Engagement：

```powershell
$env:KESTREL_ENGAGEMENT = "op-firepower"
```

### 7.4 Web UI

仓库里已经有 FastAPI Web UI 组件，包含这些路由：

- `/`
- `/engagements`
- `/engagements/{slug}`
- `/engagements/{slug}/findings`
- `/settings`
- `/tools`

但当前 CLI 还没有单独暴露一个“启动 Web UI”的稳定命令，所以它更适合作为嵌入式组件或二次封装目标，而不是对外宣称为完整独立产品界面。

如果你只想查看配置与工具状态，优先使用：

```powershell
kestrel doctor
kestrel show-config
```

## 8. 接入 Cursor

### 8.1 推荐方式

优先参考仓库里的示例文件：

`config/cursor-mcp.json.example`

把它合并进你的 `~/.cursor/mcp.json`，关键结构类似：

```json
{
  "mcpServers": {
    "kestrel-mcp": {
      "command": "python",
      "args": ["-m", "kestrel_mcp", "--edition", "internal", "serve"],
      "env": {
        "KESTREL_EDITION": "internal",
        "KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE": "*.lab.internal,192.168.56.0/24,127.0.0.1",
        "SHODAN_API_KEY": "REPLACE_WITH_YOUR_KEY",
        "KESTREL_MCP_TOOLS__NUCLEI__BINARY": "C:/Users/YOU/hacking-tools/nuclei.exe"
      }
    }
  }
}
```

### 8.2 注册脚本

仓库里也有：

```powershell
python scripts/register_cursor.py
```

它适合做快速初始化，但如果你要精确控制全部工具路径，最终仍建议以 `config/cursor-mcp.json.example` 的嵌套环境变量结构为准。

### 8.3 验证接入成功

在 Cursor 中重启会话后，可以直接问：

- `列出当前可用的 Kestrel 工具`
- `显示当前配置和启用的工具`
- `创建一个新的 engagement，名字叫 op-lab，client 是 internal-lab`

如果 MCP 客户端能触发工具调用，说明接入已经成功。

## 9. 推荐使用流程

### 9.1 最标准的一条链路

1. 创建 Engagement
2. 声明 Scope
3. 激活 Engagement
4. 做被动或轻量探测
5. 收敛为 Target 和 Finding
6. 做 Readiness / Fire Control
7. 人工批准后再进行高风险验证
8. 生成报告

### 9.2 典型工具顺序

| 阶段 | 推荐工具 |
|---|---|
| Engagement 建立 | `engagement_new` / `engagement_activate` / `engagement_switch` |
| Scope 管理 | `scope_add` / `scope_list` / `scope_check` |
| 资产发现 | `subfinder_enum` / `httpx_probe` / `nmap_scan` |
| 漏洞与内容探测 | `nuclei_scan` / `ffuf_dir_bruteforce` / `ffuf_param_fuzz` |
| 被动情报 | `shodan_count` / `shodan_search` / `shodan_host` |
| Windows / AD | `impacket_wmiexec` / `impacket_smbexec` / `impacket_get_user_spns` |
| 图分析与代理辅助 | `bloodhound_query` / `caido_replay_request` |
| 隧道与 C2 | `ligolo_*` / `sliver_*` / `havoc_*` / `evilginx_*` |
| 评估与审批 | `exploitability_triage` / `attack_path_plan` / `operator_fire_control` |
| Workflow 收口 | `full_vuln_scan` / `exploit_chain` / `generate_pentest_report` |

### 9.3 LLM 侧示例提示词

你可以直接让支持 MCP 的客户端发起这些请求：

```text
创建一个新的 engagement：
- name: op-lab
- display_name: Internal Lab
- engagement_type: internal_training
- client: lab-team
```

```text
把 .lab.internal 和 192.168.56.0/24 加入当前 engagement 的 scope，然后激活它。
```

```text
对 example.lab.internal 做被动和轻量侦察：
先跑 subfinder_enum，再用 httpx_probe 过滤活跃站点，
最后只对活跃 HTTP 目标做 severity=critical,high 的 nuclei_scan。
```

```text
把刚刚的发现按 exploitability_triage 排序，并为最高优先级项生成 fire-control packet。
```

```text
基于当前 findings 生成一份 Markdown pentest report。
```

## 10. 当前可用工具清单

以下清单来自当前代码入口暴露的工具注册逻辑。

### 10.1 管理与状态

- `engagement_new`
- `engagement_list`
- `engagement_show`
- `engagement_activate`
- `engagement_pause`
- `engagement_close`
- `engagement_switch`
- `scope_add`
- `scope_remove`
- `scope_list`
- `scope_check`
- `target_add`
- `target_list`
- `finding_list`
- `finding_show`
- `finding_transition`

### 10.2 决策与证据

- `exploitability_triage`
- `attack_path_plan`
- `operator_fire_control`
- `zero_day_hypothesis`
- `evidence_pack`

### 10.3 Shodan

- `shodan_count`
- `shodan_search`
- `shodan_host`
- `shodan_facets`
- `shodan_scan_submit`
- `shodan_account_info`

### 10.4 Nuclei

- `nuclei_scan`
- `nuclei_update_templates`
- `nuclei_list_templates`
- `nuclei_version`
- `nuclei_validate_template`

### 10.5 Recon / Web / Network

- `subfinder_enum`
- `subfinder_version`
- `httpx_probe`
- `httpx_version`
- `nmap_scan`
- `nmap_os_detect`
- `nmap_version`
- `ffuf_dir_bruteforce`
- `ffuf_param_fuzz`
- `ffuf_version`

### 10.6 Impacket

- `impacket_psexec`
- `impacket_smbexec`
- `impacket_wmiexec`
- `impacket_secretsdump`
- `impacket_get_user_spns`

### 10.7 BloodHound

- `bloodhound_query`
- `bloodhound_list_datasets`
- `bloodhound_version`

### 10.8 Caido

- `caido_start`
- `caido_stop`
- `caido_status`
- `caido_replay_request`

### 10.9 Ligolo

- `ligolo_start_proxy`
- `ligolo_stop_proxy`
- `ligolo_proxy_status`
- `ligolo_generate_agent_command`
- `ligolo_list_agents`
- `ligolo_tunnel_status`
- `ligolo_add_route`

### 10.10 Sliver

- `sliver_start_server`
- `sliver_stop_server`
- `sliver_server_status`
- `sliver_run_command`
- `sliver_list_sessions`
- `sliver_list_listeners`
- `sliver_generate_implant`
- `sliver_execute_in_session`
- `sliver_upload_file`
- `sliver_download_file`

### 10.11 Havoc

- `havoc_build_teamserver`
- `havoc_start_teamserver`
- `havoc_stop_teamserver`
- `havoc_teamserver_status`
- `havoc_lint_profile`
- `havoc_generate_demon_hint`

### 10.12 Evilginx

- `evilginx_start`
- `evilginx_stop`
- `evilginx_status`
- `evilginx_list_phishlets`
- `evilginx_enable_phishlet`
- `evilginx_create_lure`
- `evilginx_list_captured_sessions`

### 10.13 Workflow

- `recon_target`
- `full_vuln_scan`
- `exploit_chain`
- `generate_pentest_report`

### 10.14 MCP Resources 与 Prompts

这些不是普通 `call_tool` 工具，而是 MCP Host 可以直接调用的上下文接口：

- `resources/list`
- `resources/read`
- `prompts/list`
- `prompts/get`

当前内置资源 URI：

- `engagement://{id}/summary`
- `engagement://{id}/scope`
- `engagement://{id}/targets`
- `engagement://{id}/findings`

当前内置提示词：

- `zh_redteam_operator`
- `en_redteam_operator`

## 11. 数据与文件落盘位置

默认情况下，Kestrel MCP 会把运行数据写到用户目录下的 `.kestrel`：

| 路径 | 说明 |
|---|---|
| `~/.kestrel/config.yaml` | 用户级配置 |
| `~/.kestrel/data.db` | 默认共享 SQLite 数据库 |
| `~/.kestrel/audit.log` | 审计日志 |
| `~/.kestrel/logs/` | 结构化运行日志 |
| `~/.kestrel/runs/` | 子进程工作目录 |

如果设置了 `KESTREL_DATA_DIR`，数据目录会改到你指定的位置。

补充说明：

- `tool_invocation` 审计链写在默认 SQLite 数据库里，不是单独的日志文件；它会记录工具名、参数摘要、成功/失败状态，以及前一条记录的 hash。
- `engagement://...` 资源不是静态文件，而是从当前激活 Engagement 的数据库内容按需投影出来。
- 提示词默认打包在 `src/kestrel_mcp/prompts/*.md`，部署后由 MCP `prompts/list` / `prompts/get` 暴露。

## 12. 常用命令速查

```powershell
# 版本与配置
kestrel version
kestrel doctor
kestrel show-config
kestrel list-tools

# 本地 stdio MCP
kestrel serve
kestrel serve --dry-run
kestrel --edition internal serve

# HTTP MCP
$env:KESTREL_MCP_HTTP_TOKEN = "change-me"
kestrel serve-http --host 127.0.0.1 --port 8765 --endpoint /mcp

# 团队初始化
kestrel --edition team team bootstrap --name op-demo --scope "demo.lab,*.demo.lab"

# Cursor 集成
python scripts/register_cursor.py
```

## 13. 常见问题与排障

### 13.1 `authorized_scope is empty`

原因：

- 你没有在 YAML 或环境变量里设置授权范围
- 或者设置成了旧变量名，没有被当前配置模型读取

优先修复方式：

```powershell
$env:KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE = "*.lab.internal,192.168.56.0/24"
kestrel show-config
```

### 13.2 `binary not found`

说明对应工具已启用，但路径不存在或未在 PATH 中。

优先检查：

```powershell
kestrel doctor
```

然后在 `kestrel.yaml` 或环境变量里补路径，例如：

```powershell
$env:KESTREL_MCP_TOOLS__NUCLEI__BINARY = "C:/Users/YOU/go/bin/nuclei.exe"
```

### 13.3 `SHODAN_API_KEY missing`

Shodan 模块启用但 API Key 未设置。只要你不用 Shodan 工具，可以先忽略；要使用它时必须提供 Key。

### 13.4 `serve-http` 启动失败并提示缺少 Token

默认要求 Bearer Token。处理方式二选一：

- 设置 `KESTREL_MCP_HTTP_TOKEN`
- 仅在本地调试时使用 `--allow-no-auth`

### 13.5 Edition 看起来“不对”

先执行：

```powershell
kestrel show-config
```

然后检查这些来源：

- `KESTREL_EDITION`
- `KESTREL_MCP_EDITION`
- `~/.kestrel/config.yaml`
- `./kestrel.yaml`

### 13.6 工具明明安装了，但没有出现在列表里

先确认两件事：

1. 模块是否 `enabled: true`
2. `doctor` 是否认为依赖已经就绪

如果工具二进制已经装好，但 `enabled` 还是 `false`，它不会出现在最终工具集里。

## 14. 建议的落地方式

如果你是第一次正式使用，建议按下面的顺序推进：

1. 用 `kestrel.yaml` 固定住 Edition、Scope 和常用二进制路径。
2. 先跑 `kestrel doctor`，把环境错误收敛到 0。
3. 用 Cursor 手工接入 `stdio` 模式，不要一上来就用 HTTP 共享。
4. 第一个任务只启用 `engagement`、`readiness`、`subfinder`、`httpx`、`nuclei` 这一条链路。
5. 等流程稳定后，再接入 `ffuf`、`nmap`、`impacket`、`bloodhound`、`sliver`、`evilginx` 等更深的工具。
6. 需要让 Host 按需读上下文时，再启用 `resources/read` 路径；需要标准化开场提示时，再接入内置 prompts。

如果你把它作为团队公共服务，优先考虑：

- `serve-http` 放在反向代理后面
- 固定 `KESTREL_MCP_HTTP_TOKEN`
- 使用 `internal` 只在私有实验室或内部受控环境启用
- 把 `audit.log` 与结构化日志外送到日志平台
