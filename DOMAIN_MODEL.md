# DOMAIN MODEL

> 本文档定义 kestrel-mcp 的领域模型。
> 所有代码、文档、UI、报告都必须使用这里的术语和结构。
> 参照 **DDD**、**PTES (Penetration Testing Execution Standard)**、**MITRE ATT&CK**。

**Status**: draft → 目标 v0.2 前冻结

---

## 1. 领域定位

kestrel-mcp 服务于一类业务场景：**"受授权的进攻性安全作业"**（Authorized Offensive Security Engagement）。
该业务由以下核心实体构成：

```
Actor → Engagement → { Target × Scope × Credential × Finding × Artifact × Session }
                      └── 由 ToolInvocation 产生
```

所有实体都归属于某个 Engagement。脱离 Engagement 的数据没有业务意义。

---

## 2. 实体关系图

```
┌────────────┐
│   Actor    │  执行者（人 + LLM + 其组合）
└─────┬──────┘
      │ 1..N
      ▼
┌────────────┐    1..N    ┌──────────────┐
│ Engagement │◄──────────►│    Scope     │  授权范围
└─────┬──────┘            └──────────────┘
      │
      ├──1..N──► Target          (被测资产)
      │
      ├──1..N──► Credential      (已获取凭证)
      │
      ├──1..N──► Finding         (漏洞发现)
      │
      ├──1..N──► Artifact        (产物文件)
      │
      ├──1..N──► Session         (C2 / shell 会话)
      │
      └──1..N──► ToolInvocation  (每次 tool 调用记录)
```

---

## 3. 实体定义

### 3.1 Actor

**语义**: 一次操作的执行者。既包含人（operator），也包含代理其操作的 LLM 及其 MCP client。

```python
class Actor(BaseModel):
    id: UUID
    kind: Literal["human", "llm", "automation"]
    display_name: str
    # 如 kind == "llm"
    llm_provider: str | None = None       # "anthropic" / "openai" / "local"
    llm_model: str | None = None          # "claude-opus-4.7" / "gpt-4"
    llm_client: str | None = None         # "cursor" / "claude-desktop" / "cline"
    # 如 kind == "human"
    handle: str | None = None             # github / gitlab 用户名
    contact: str | None = None            # 邮箱

    created_at: datetime
    last_seen_at: datetime
```

**关键不变量**:
- 每个 `ToolInvocation` 必须有 actor。如果由 LLM 触发，actor.kind == "llm" 且 `llm_*` 字段必填。
- Actor 只被创建、不被删除（只能标记 `deactivated_at`）。审计需要。

**产生时机**: MCP server 初始化时从 transport 元数据中识别 client。首次见到则创建。

---

### 3.2 Engagement

**语义**: 一次授权作业。有明确的起止时间、授权书、范围、负责人。所有操作必须挂靠在 engagement 下。

```python
class Engagement(BaseModel):
    id: UUID
    name: str                             # 短 slug, e.g. "acme-webapp-q1"
    display_name: str
    status: EngagementStatus              # planning / active / paused / closed

    # 法律与授权
    authorization_doc_ref: str | None     # 签署的授权书存储引用
    started_at: datetime
    expires_at: datetime | None           # 超时后所有 dangerous tool 禁用
    closed_at: datetime | None

    # 作业元数据
    client: str                           # 客户/组织名（CTF 比赛也算"客户"）
    engagement_type: EngagementType       # pentest / red_team / ctf / research / bug_bounty
    owners: list[UUID]                    # Actor IDs

    # 运行时开关
    dry_run: bool = False
    opsec_mode: bool = False              # 见 G-U2

    created_at: datetime
    updated_at: datetime


class EngagementStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class EngagementType(str, Enum):
    PENTEST = "pentest"
    RED_TEAM = "red_team"
    CTF = "ctf"
    RESEARCH = "research"
    BUG_BOUNTY = "bug_bounty"
    INTERNAL_TRAINING = "internal_training"
```

**关键不变量**:
- `expires_at` 过了之后，所有 `dangerous=true` 的 tool 必须被 server 级别拒绝
- 一个 actor 同时只能有一个 `active` engagement（切换要显式 pause）
- `closed` 后不可修改，只读
- 删除 engagement 需要同时删除所有关联的 Finding / Credential / Artifact（合规要求）

**状态机**:
```
planning ──activate──► active ──pause──► paused ──resume──► active
                         │                  │
                         └──────close──────►└──► closed (terminal)
```

**MCP 层暴露**:
- `engagement_new(name, type, client, expires_at)` 创建
- `engagement_activate(id)` 激活
- `engagement_pause(id)`
- `engagement_close(id)` 不可逆
- `engagement_list(status?)` 列表
- `engagement_show(id?)` 默认当前 active

---

### 3.3 Scope

**语义**: 一个 engagement 所授权的目标范围。由多条规则组成。

```python
class Scope(BaseModel):
    id: UUID
    engagement_id: UUID
    entries: list[ScopeEntry]
    created_at: datetime
    updated_at: datetime


class ScopeEntry(BaseModel):
    pattern: str                          # "*.acme.com" / "10.0.0.0/16"
    kind: ScopeEntryKind                  # 冗余字段，用于 analytics
    included: bool = True                 # False = exclusion（优先级高）
    note: str | None                      # 为什么加这一条
    added_by: UUID                        # Actor
    added_at: datetime


class ScopeEntryKind(str, Enum):
    HOSTNAME_EXACT = "hostname_exact"
    HOSTNAME_WILDCARD = "hostname_wildcard"
    CIDR_V4 = "cidr_v4"
    CIDR_V6 = "cidr_v6"
    IP_V4 = "ip_v4"
    IP_V6 = "ip_v6"
    URL_PATH = "url_path"                 # e.g. "https://x.com/api/*"
```

**关键不变量**:
- `ScopeGuard.ensure()` 对每个 dangerous tool 调用的 target 必须成功匹配一条 `included=True` 条目且不匹配任何 `included=False` 条目
- scope 修改必须记录 changelog（who、when、before、after）

**Precedence**:
1. Explicit exclusion （included=False）总是赢
2. 否则匹配任一 inclusion 即通过
3. 都不匹配 → 拒绝

**MCP 层暴露**:
- `scope_add(pattern, note)`
- `scope_remove(pattern)`
- `scope_list()`
- `scope_check(target)` → 返回是否命中 + 匹配的 entry

---

### 3.4 Target

**语义**: 一个在 scope 内的具体被测资产。由 tool 发现或用户手动加入。

```python
class Target(BaseModel):
    id: UUID
    engagement_id: UUID
    kind: TargetKind
    value: str                            # "example.com" / "10.0.0.5" / "https://api.x/"
    parent_id: UUID | None                # 如 web app 下的端点 / 子域

    # 发现信息
    discovered_by_tool: str | None        # "subfinder" / "user_input"
    discovered_at: datetime

    # 富数据（由 tool 写入）
    open_ports: list[int] = []
    tech_stack: list[str] = []            # "nginx/1.18", "WordPress 6.2"
    hostnames: list[str] = []             # 反查 DNS
    organization: str | None = None       # WHOIS / Shodan
    country: str | None = None

    # 状态
    last_scanned_at: datetime | None
    notes: str = ""
    tags: list[str] = []                  # 用户自定义


class TargetKind(str, Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    HOSTNAME = "hostname"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    URL = "url"
    EMAIL = "email"                       # OSINT 目标
    PERSON = "person"                     # OSINT 目标（社工场景）
    ORGANIZATION = "organization"         # OSINT 目标
    APPLICATION = "application"           # 特定应用
    NETWORK = "network"                   # CIDR
```

**关键不变量**:
- Target 创建时必须通过 ScopeGuard
- Target 不能跨 engagement 共享（隔离）
- 删除 engagement 级联删除 targets

**唯一性**: 同一 engagement 内 `(kind, value)` 唯一。subfinder 多次运行不会重复写入。

**MCP 层暴露**:
- `target_add(kind, value)`
- `target_list(filter?)`
- `target_show(id)`
- `target_update(id, fields)`

---

### 3.5 Credential

**语义**: 渗透过程中获取的认证凭证。**绝对不能明文通过 MCP response 返回**。

```python
class Credential(BaseModel):
    id: UUID
    engagement_id: UUID
    kind: CredentialKind

    # 关联
    target_id: UUID | None                # 适用的目标
    obtained_from_tool: str               # "responder" / "impacket_secretsdump"
    obtained_at: datetime

    # 凭证本体（加密存储）
    identity: str                         # 用户名 / 邮箱 / 账户 ID（可明文）
    secret_ciphertext: bytes              # 密文
    secret_kdf: str                       # "age-x25519-v1"
    secret_metadata: dict[str, str]       # e.g. {"algorithm": "NTLM"}

    # 状态
    validated: bool = False               # 是否已验证可用
    validated_at: datetime | None = None
    revoked: bool = False                 # 目标已改密码

    tags: list[str] = []
    notes: str = ""


class CredentialKind(str, Enum):
    PASSWORD_PLAINTEXT = "password"
    NTLM_HASH = "ntlm_hash"
    NETNTLMV2_HASH = "netntlmv2_hash"
    KERBEROS_TGT = "krb_tgt"
    KERBEROS_TGS = "krb_tgs"
    KERBEROS_AS_REP = "krb_as_rep"
    JWT = "jwt"
    SESSION_COOKIE = "session_cookie"
    API_KEY = "api_key"
    SSH_PRIVATE_KEY = "ssh_private_key"
    CLOUD_ACCESS_KEY = "cloud_access_key"    # AWS/GCP/Azure
    OTHER = "other"
```

**关键不变量**:
- `secret_ciphertext` 加密才存盘
- MCP tool 返回给 LLM 的**始终是引用**（`cred://engagement-id/credential-id`），从不是明文
- 明文解密只有两种方式:
  1. 下游 tool 用 credential reference 调用，server 解密后注入 subprocess（不进 LLM context）
  2. 用户执行 `kestrel cred reveal <id> --engagement <e>` 手动（记录日志）
- 删除凭证是硬删除，彻底清除

**密钥派生**:
- 每个 engagement 有独立的 encryption key
- Key 存储位置优先级:
  1. Native keychain (macOS/Windows/Linux secret service)
  2. HashiCorp Vault / cloud KMS (企业场景)
  3. age 加密文件 + passphrase（fallback，开发用）

**MCP 层暴露**:
- `credential_list(target_id?, kind?)` 返回元数据（不含密文）
- `credential_store(kind, identity, secret, ...)` 仅工具内部调用
- `credential_validate(id, against_target_id?)` 用 tool 验证可用性
- `credential_revoke(id, reason)`

**绝对不暴露给 LLM 的 tool**:
- 任何返回明文 `secret` 的路径

---

### 3.6 Finding

**语义**: 一个发现的漏洞 / 弱点 / 风险点。报告的核心原料。

```python
class Finding(BaseModel):
    id: UUID
    engagement_id: UUID
    target_id: UUID                       # 必须关联到目标

    # 分类
    title: str
    severity: FindingSeverity
    confidence: Confidence
    category: FindingCategory

    # 标准引用
    cwe: list[str] = []                   # ["CWE-89"]
    cve: list[str] = []                   # ["CVE-2024-1234"]
    owasp_top10: list[str] = []           # ["A03:2021-Injection"]
    mitre_attack: list[str] = []          # ["T1190"]
    cvss_vector: str | None = None        # "CVSS:3.1/AV:N/AC:L/..."
    cvss_score: float | None = None

    # 描述
    description: str                      # 技术描述
    impact: str                           # 业务影响
    remediation: str                      # 修复建议
    references: list[str] = []            # URL

    # 证据
    evidence: list[FindingEvidence] = []

    # 元数据
    discovered_by_tool: str
    discovered_at: datetime
    verified: bool = False
    verified_by: UUID | None = None
    verified_at: datetime | None = None

    # 生命周期
    status: FindingStatus                 # new / triaged / confirmed / fixed / closed_wontfix / false_positive
    triage_notes: str = ""
    fixed_at: datetime | None = None

    # 分组
    group_id: UUID | None = None          # 多 finding 共享根因


class FindingEvidence(BaseModel):
    kind: EvidenceKind                    # request_response / screenshot / log / output
    content_ref: UUID                     # 指向 Artifact
    sanitized: bool                       # 是否已去敏


class FindingSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, Enum):
    SUSPECTED = "suspected"
    LIKELY = "likely"
    CONFIRMED = "confirmed"


class FindingStatus(str, Enum):
    NEW = "new"
    TRIAGED = "triaged"
    CONFIRMED = "confirmed"
    FIXED = "fixed"
    CLOSED_WONTFIX = "closed_wontfix"
    FALSE_POSITIVE = "false_positive"


class FindingCategory(str, Enum):
    INJECTION = "injection"
    BROKEN_AUTH = "broken_auth"
    SENSITIVE_DATA = "sensitive_data"
    MISCONFIGURATION = "misconfiguration"
    VULNERABLE_COMPONENT = "vulnerable_component"
    ACCESS_CONTROL = "access_control"
    CRYPTOGRAPHY = "cryptography"
    LOGIC_FLAW = "logic_flaw"
    INFORMATION_DISCLOSURE = "information_disclosure"
    SOCIAL_ENGINEERING = "social_engineering"
    SUPPLY_CHAIN = "supply_chain"
    OTHER = "other"
```

**关键不变量**:
- Finding 必须有 target_id（不能凭空）
- CVSS 分与 severity 必须一致（post-hook 检查）
- `status` 只能按状态机迁移

**状态机**:
```
new ──triage──► triaged ──confirm──► confirmed ──fix──► fixed
  │                                       │
  └──fp────► false_positive            closed_wontfix
```

**MCP 层暴露**:
- `finding_create(target_id, title, severity, ...)` 自动或手动
- `finding_list(status?, severity?, target?)`
- `finding_show(id)`
- `finding_transition(id, to_status, note?)`
- `finding_verify(id, evidence_artifact_id)`

---

### 3.7 Artifact

**语义**: 渗透过程中产生或收集的文件。包括 dump 文件、生成的 payload、截图、PCAP 等。

```python
class Artifact(BaseModel):
    id: UUID
    engagement_id: UUID
    kind: ArtifactKind

    # 存储
    storage_path: Path                    # 绝对路径
    size_bytes: int
    sha256: str
    encrypted: bool = False

    # 来源
    produced_by_tool: str
    produced_at: datetime
    source_target_id: UUID | None

    # 元数据
    mime_type: str
    original_filename: str | None
    tags: list[str] = []
    notes: str = ""


class ArtifactKind(str, Enum):
    PAYLOAD = "payload"                   # sliver implant, msfvenom output
    CRED_DUMP = "cred_dump"               # secretsdump, mimikatz output
    PACKET_CAPTURE = "pcap"
    SCREENSHOT = "screenshot"
    LOG = "log"
    REPORT = "report"                     # 生成的 report
    BLOODHOUND_DATA = "bloodhound_data"
    HTTP_REQUEST_RESPONSE = "http_rr"
    SHELLCODE = "shellcode"
    MALWARE_SAMPLE = "malware_sample"     # 反向，分析用
    OTHER = "other"
```

**关键不变量**:
- Artifact 存储路径在 engagement 根目录下（`~/.kestrel/engagements/<eng>/artifacts/<id>`）
- SHA256 创建时计算，不可变
- 删除前必须确认所有引用它的 Finding/Credential 都已处理

**安全要求**:
- malware / shellcode 默认加密存储
- artifact 目录 chmod 0700
- 导出前警告敏感内容

**MCP 层暴露**:
- `artifact_store(path, kind, notes?)` → 返回 id
- `artifact_list(kind?, produced_by?)`
- `artifact_show(id)` 元数据
- `artifact_export(id, to_path)` 复制到用户指定位置

---

### 3.8 Session

**语义**: 一个活跃的 C2 / shell / 代理会话。短生命周期。

```python
class Session(BaseModel):
    id: UUID
    engagement_id: UUID
    target_id: UUID | None

    # 类型
    kind: SessionKind                     # sliver / havoc / msf / ssh / ligolo

    # 标识
    external_id: str                      # sliver session id
    protocol: str                         # https / mtls / smb / dns
    callback_addr: str

    # 状态
    status: SessionStatus                 # active / stale / lost / closed
    first_seen_at: datetime
    last_check_in_at: datetime
    closed_at: datetime | None

    # 目标信息
    remote_hostname: str | None
    remote_user: str | None
    remote_os: str | None
    remote_pid: int | None
    remote_integrity: str | None          # "high" / "medium" / "low" / "system"

    # 关联
    credentials_used: list[UUID] = []
    findings_produced: list[UUID] = []
    artifacts_produced: list[UUID] = []


class SessionKind(str, Enum):
    SLIVER = "sliver"
    HAVOC = "havoc"
    MSF = "msf"
    COBALT_STRIKE = "cobalt_strike"       # 未支持但保留
    SSH = "ssh"
    RDP = "rdp"
    LIGOLO_TUNNEL = "ligolo_tunnel"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"                       # 超时未 check-in
    LOST = "lost"                         # 主动 probe 失败
    CLOSED = "closed"                     # 用户关闭
```

**关键不变量**:
- Session 必须通过 scope 检查（callback 在 scope 内才允许创建）
- `stale` 状态由后台 job 定期检查（> 24h 无 check-in）
- 关闭 engagement 前必须显式关闭所有 session（防野）

**MCP 层暴露**:
- `session_list(kind?, status?)`
- `session_show(id)`
- `session_execute(id, command, timeout?)`
- `session_close(id, reason?)`

---

### 3.9 ToolInvocation

**语义**: 每次 MCP tool 调用的完整记录。审计、回放、报告生成的原始数据。

```python
class ToolInvocation(BaseModel):
    id: UUID
    engagement_id: UUID
    actor_id: UUID

    # 调用信息
    tool_name: str
    arguments_sanitized: dict             # 敏感字段替换为 "<REDACTED>"
    arguments_hash: str                   # SHA256(原始 arguments) 用于回放

    # 执行
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    exit_code: int | None                 # 子进程退出码
    truncated: bool
    timed_out: bool

    # 结果关联
    findings_created: list[UUID] = []
    credentials_created: list[UUID] = []
    artifacts_created: list[UUID] = []
    targets_created: list[UUID] = []

    # 错误
    error_code: str | None
    error_message: str | None

    # 审计链
    prev_hash: str                        # 前一条 invocation 的 hash
    this_hash: str                        # 本条的 hash（Merkle 式）
```

**关键不变量**:
- **append-only**：从不删除
- 哈希链：`this_hash = SHA256(prev_hash || serialize(self))`
- 如需"销毁"某个 engagement 的数据，只能销毁整个 engagement（keepsakes linked）

**MCP 层暴露**:
- `audit_query(engagement_id, tool_name?, since?, until?)`
- `audit_verify(engagement_id)` 验证哈希链完整

---

## 4. 持久化

### 存储选择

- **SQLite**（默认）— 单机、嵌入式、零配置
- **PostgreSQL**（可选）— 企业场景，支持多 actor 并发

### Schema 迁移

用 **alembic**。每个 migration 必须是可逆的（有 downgrade）。

### 数据库文件位置

```
~/.kestrel/
├── engagements/
│   ├── acme-webapp-q1/
│   │   ├── engagement.db           # SQLite
│   │   ├── artifacts/              # 文件存储
│   │   ├── audit.log               # 结构化日志
│   │   └── key.age                 # 加密密钥（或 keychain 引用）
│   └── ...
├── config.yaml
└── logs/
```

---

## 5. 与现有代码的对应

当前代码库里：
- `ScopeGuard` → `Scope` 实体的运行时验证器
- `Settings.security.authorized_scope` → 其实是 Engagement.Scope（现在是全局单例，见 G-A2）
- `audit_event(...)` → 写 `ToolInvocation.*_hash` 字段的简化版
- `ToolResult.structured` → 大部分字段未来会结构化为 `Finding` / `Artifact`

**重构路径**: 见 GAP_ANALYSIS.md G-P1 和 G-A2。

---

## 6. 边界与非目标

**kestrel-mcp 的领域模型不包含**:
- 蓝队防御数据（SIEM alerts / EDR events）
- 客户端 CRM（谁联系过谁，发票）
- 授权书的法律生效机制（只做引用）
- 漏洞管理平台（JIRA / DefectDojo 的功能）

如需集成上面这些，通过 export hook（见 Architecture ADR-0009）。

---

## 7. 版本与演进

**语义版本**:
- 新增字段（optional）→ minor
- 破坏性字段变更 → major
- Enum 新值 → minor（消费者用 `str` enum 处理未知值）
- Enum 删除值 → major

**迁移策略**:
- 每个 major 提供 data migration tool
- 旧 engagement 可只读导入新版本

---

## 8. 相关文档

- [MASTER_PLAN.md](./MASTER_PLAN.md)
- [GAP_ANALYSIS.md](./GAP_ANALYSIS.md)
- [DEVELOPMENT_HANDBOOK.md](./DEVELOPMENT_HANDBOOK.md)
- [THREAT_MODEL.md](./THREAT_MODEL.md) (即将发布)
