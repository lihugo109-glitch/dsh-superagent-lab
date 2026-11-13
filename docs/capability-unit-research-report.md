# SuperAgent「能力单元（Capability Unit）」体系设计调研报告

> 文档类型：外部调研工作单交付物（可对外转发）｜版本：v1｜日期：2026-11-13
> 范围：仅基于公开资料与本工作单背景做调研和架构设计；不修改生产系统、不接触凭据、不采集私有数据。
> 字数口径：主报告正文（本文件开头至「附录 A」之前）按中文字符计；代码、schema、伪代码、引用清单均放在附录，不计入正文字数。

---

## 0. 摘要结论（结论先行）

**结论：能做，但要做成「带授权的确定性路由 + 少量可复用会话专家」，不是照搬神经网络的动态 MoE。**

- **能否做**：能，不必发明新运行时。公开原型已有三块骨架：不可变 Mandate 与 Policy version、只记「本会接纳」的 observe 灰度、具名可唤醒的 teammate（fresh / fork）与可回放任务板 [R1][R2][R3]；缺的是接上统一的「能力卡 → 注册表 → 路由决策」。
- **最小值**：可校验的能力卡 schema、Git 版控注册表（≤5 张卡）、一个常驻 persona 专家、规则优先混合路由；先 observe 灰度，不动准入与授权链路。
- **最大风险**：把「看似权限、其实不是」的机制当硬边界。官方 Team 文档明确 `writeScopes` 是 advisory 而非锁、历史 roster 不授权、`TeamId` 绑定单个 root SessionId [R3]；人设或任务板一旦当授权，跨工单复用即成越权通道。

给非本领域读者：现在像「每次来活临时拉人进群、口头交代」；目标像「先有岗位说明和花名册，按岗位派单、每次留痕、不超出工单授权」。「动态 MoE」只是比喻，难点在授权与审计，不在挑选算法。

### 0.1 证据分级与标注规范

- **F0 / F1 事实**：F0 为工作单给定背景（未独立验证内部环境）；F1 为附录 F 标注「已读取」的公开页面，附链接与版本。
- **I 推断**：由 F0/F1 推导，涉及内部运行时行为均标「需内部验证」。
- **R 建议**：本报告选型，不是对现有系统的描述。

下文每问按 F / I / R 作答；未实测的数字一律不写，读数见附录 G，展开论证见附录 H。

---

## 1. 方案对比与明确推荐

| 架构 | 做法 | 定位 |
| --- | --- | --- |
| A 静态技能目录 + 人工指派 | 只维护 skill / 工具清单，人在工单点名 | 基线 / 对照组 |
| **B 文件型注册表 + 混合 gating（推荐）** | 能力卡为唯一事实源，Git 版控注册表，Router 输出可回放 Decision | MVP 与中期主体 |
| C 独立能力服务 | 卡片托管服务端，专家作为独立服务被发现（A2A / MCP Registry 风格） | 跨主机阶段 |

| 维度 | A | B | C |
| --- | --- | --- | --- |
| 授权可审计 | 中（人工） | 高（卡 + Decision） | 高，但依赖身份与网络 |
| 跨工单复用 | 低 | 高 | 高 |
| 跨主机 | 不支持 | 需 L0 代理 | 原生 |
| 实施运维成本 | 最低 | 低至中 | 高 |
| 路由误判 | 无自动路由 | 可控（过滤 + 兜底） | 同 B，另加发现失败 |
| 版本回滚 | 人工 | Git 可回滚 | 依赖服务 |
| 授权链路强依赖外部服务 | 否 | 否（离线可校验） | 是 |

**推荐 B**（C 留作跨主机阶段，A 作对照基线）。能力卡是授权输入，须离线可校验、可逐版本回滚；MCP 官方 Registry 自述处于 preview 且「不提供 uptime 或数据持久性保证」[R9]，不宜成为授权链路强依赖；A2A Agent Card 与 MCP Tool 的字段与发现范式可直接借用 [R6][R7][R8]。

### 1.1 推荐架构与分层

四层实例：**L0 工具 / CLI**（无会话、确定性）→ **L1 skill**（无会话、渐进披露）→ **L2 常驻 persona teammate**（独立会话、项目记忆）→ **L3 独立专家服务**（跨主机）。横切：**Registry**（卡、索引、别名）、**Router**（过滤、gating、Decision）、**Gate**（host 强制权限 / 副作用 / 预算）、**Audit**（调用留痕）。

核心约束：**能力卡是唯一事实源，工单是唯一授权源，Router 只做选择、不做授权。** 这是不牺牲授权与可审计的前提。

---

## 2. 九个问题逐项作答

### 2.1 单元分层：分几层？何时需要独立会话？

**F0**：四类矩阵已确认。**F1**：Agent Skills 以三级渐进披露支撑 L1，并可打包确定性脚本 [R10]；官方 Team 文档给出 `fresh | fork` 两种具名会话创建方式 [R3]。

**I（需内部验证）**：五问判据——要跨轮次状态？要自主多步探索？要隔离注意力？要人设与项目记忆？副作用跨信任域？前四问任一为「是」才升 L2；第五问为「是」升 L3 或用 L0 受控代理。

**R**：① 跨文件系统 / Windows 侧搜索：不需会话，用 L0 工具代理（白名单路径 + 参数化调用 + 结构化输出），effect 0。② 邮件检索 / 发送：不需 persona，检索只读 L0，发送由确定性实现 + 人工确认 + 审计完成。③ 代码评审：需 L2，依赖项目记忆、多轮反馈与线程状态延续。

### 2.2 能力契约：能力卡应有哪些字段？

**F1**：A2A 1.0.0 的 AgentCard 必填 name / description / version / capabilities / skills 等，AgentSkill 必填 id / name / description / tags，可选 examples 与 securityRequirements [R6]；MCP Tool 用 inputSchema / outputSchema / annotations，并明确 annotations 不可信、调用须留痕审计 [R8]；A2A 0.2.5 建议最小权限、按技能授权、卡内不放明文密钥 [R7]。

**I**：这些字段只说明「能做什么」，未表达「影响多大、受哪个工单约束、花多少预算」，缺了就只是说明书，无法治理。

**R**：对齐公开字段并补齐 `side_effect_level`(0–3)、`mandate_scope`、`permissions`、`limits`、`implementation`、`owner`、`status`、`policy_ref`、`observability`、`checksum`、`applicable` / `inapplicable`。Schema、TS 类型与三张示例卡见附录 A。原则：**description 给模型读，scope / effect / budget 给 host 校验，不可混用。**

### 2.3 注册表：放哪一层？命名、版本、废弃与同名治理？

**F1**：MCP Registry 用反域名命名，提供 `/v0.1/servers/{name}/versions/{version}` 与 `latest`；元数据一般不可变，仅 `status` 可改为 `deprecated` / `deleted` [R9]。A2A 0.2.5 列出三类发现机制：well-known URI、Registries / Catalogs、Direct Configuration [R7]。

**I**：注册表一旦成为授权输入，「离线可校验」与「可回滚」比「实时发现」更重要。

**R**：MVP 放 B 层——Git 版控 `capabilities/*.card.json` 加 `registry.json` 索引，走 PR 评审。命名空间 `<reverse-domain>/<name>@<semver>`；别名 `stable` / `canary` 只指向一个不可变版本；废弃 = 改 status 并停新调用，不回溯在途工单（与 Policy version 不立即吊销 Mandate 同构 [R2]）；回滚 = 别名回指。同名治理：`(name, version)` 唯一、禁止覆盖，多份同名落在不同命名空间，由 owner 与信任级别裁决，Router 只在 Mandate 允许范围内取候选。发现用「索引 + 渐进披露」[R10]。模型与示例记录见附录 B。

### 2.4 路由（gating）：怎么选？与 MoE gating 的得失？兜底与可观测性？

**F1**：Anthropic 指出 routing 仅适用于「类别可分且分类能准确完成」的场景，且只在复杂度被证明改善结果时才应增加 [R11]；SuperAgent 授权文档已有混合范式：显式候选直接 route、推断候选需规则评估、observe 只记「would accept」、Decision 记录理由 [R2]。MoE 经典问题见 [R12][R13][R14]。

**I（需内部验证）**：照搬神经 MoE gating 是范畴错误。MoE 门控连续、可微、统计性，错了只是质量下降；agent 路由离散、授权性，错了可能是不可撤销的越权副作用。故首要目标是授权正确性而非负载均衡；坍塌表现为「所有活派给最强专家」，抖动表现为「同工单续跑换专家」，治理靠规则分片与决策绑定，而非损失函数（MoE 论文未证明 agent 应如此）。逐条对比见附录 H。

**R**：三层混合 gating：① 硬过滤（Mandate、命名空间、effect 上限、路径 / egress、预算）先做减法；② 显式指定优先；③ 语义评估只在候选集内 top-1，输出带理由的 Decision。复用 off / observe / auto 灰度，决策以 `(ticket_id, capability@version)` 冻结，续跑不重算。兜底：无匹配 → 通用 worker；低置信 → 人工确认；调用失败 → L2→L1→L0 降级 → 人工；**任何兜底不得扩大 Mandate**。每次 route 落完整 Decision [R8]，字段与伪代码见附录 C。

### 2.5 硬边界：画在哪些维度？如何「边界硬、行为自由」？跨主机与外部 CLI 怎么办？

**F1**：官方 Team 文档明确 `writeScopes` 是 advisory 路径前缀而非锁、历史 roster 不授权 [R3]；A2A 0.2.5 要求最小权限且卡内不放明文密钥 [R7]；MCP 要求服务端校验输入、访问控制与限流，客户端对敏感操作确认 [R8]。

**I**：共享任务板的 owner / 依赖 / 写域是「意图协调」，不是「权限执行」；混用是当前最易踩的坑。

**R**：五个维度由 host 在执行点强制，不写进提示词：能力契约（卡不可变、校验 checksum）、权限与副作用（0 只读 / 1 本地可逆写 / 2 外部可见 / 3 不可逆，≥2 须显式确认）、资源与注意力（超时 / token / 步数 / 并发，按 Ticket 记账）、版本与废弃（pin 不可变版本，工单内不换）、数据访问（读写路径前缀、egress 域名、数据分类）。逐维执行表见附录 H。

跨主机 / 外部 CLI 由 host 受控代理执行：参数化传参（禁止拼 shell）、只读挂载优先、结构化输出、超时限流、逐调用审计；**agent 拿结构化结果，不拿通用 shell**（Windows 侧搜索与邮件脚本的完整做法见附录 H）。

「边界硬、行为自由」：只把不可越过的约束写成机器可校验的禁止清单与完成判据，「怎么写评审意见」留给专家；反例是把评审拆成 12 步固定流程，把 L2 压成 L1 脚本。

### 2.6 生命周期与成本：空闲成本、唤醒回收、崩溃恢复、僵尸单元

**F0**：worker 完成即释放，长跑工单可多轮唤醒。**F1**：官方 Team 文档显示消息与任务「先落盘再确认」，变更写完整快照并用 revision 做 CAS，崩溃可回放 [R3]。

**I（需内部验证）**：休眠是否零 token 无法从公开文档确认。假设是「不调用模型即无 token 计费，但进程 / 上下文留存、唤醒重放仍有成本」；须实测：对 N 个空闲会话记录 24h token 与唤醒首轮 token，给出均值与 P95。

**R**：注册 ≠ 实例化，按需 spawn；事件驱动唤醒，默认 fresh、必要时 fork；空闲 TTL + LRU 回收；检查点 = persona 记忆 + 会话摘要 + task revision；崩溃恢复复用现有 durable mailbox 与 CAS。僵尸治理：每卡有 owner、30 天零调用自动 `deprecated`、季度复审、看板展示调用率与成本。

### 2.7 复用与治理：跨工单授权、维护责任、一次调用的审计、如何度量更优？

**F1**：SuperAgent 授权文档规定只有三种操作改变 Mandate（accept 创建、人 stop 撤销、revalidation 失败吊销），订阅消息不增权限，Decision 与 Policy version 留痕 [R2]；公开原型 README 明确是 research code [R1]。

**I**：能力若「注册即可被所有工单看见」，等于给注册表悄悄加了授权能力，与 Mandate 不可扩大冲突。

**R**：能力不自带权限，权限永远来自 Mandate；一次调用记六元组 `(ticket_id, mandate_id, policy_version, capability_id@version, caller, effect)` 并附成本。跨团队复用需 owner 审批 + 命名空间隔离 + 显式授权；卡片变更走 PR + owner 评审 + semver 递增；审计六段式 who / what / why / where / how much / result。以「工单 + skill + 人工指派」为对照基线，指标见附录 H；**没有基线数据不得宣称更优** [R1]。

### 2.8 与现有机制的映射：哪些可直接复用，哪些必须新增？

**F0 / F1**：工单授权、Mandate、共享任务板、teammate 与 fork / fresh、技能系统均为现状 [R2][R3]。**I**：现有机制围绕单个 root Session 的一次协作，跨工单「能力身份」尚未表达。

**R**：可复用 Policy 与 off / observe / auto、Decision、Mandate 不可变、Ticket / worker / Subscription、skills 渐进披露、durable mailbox 与 revision CAS；需改造的是共享任务板 writeScopes（仅意图协调，授权须另加 host 强制层 [R3]）；必须新增跨 root Session 能力身份 [R3]、能力卡、注册表与别名回滚、调用级预算、副作用执行点、专家记忆持久化。逐项映射表见附录 H。

### 2.9 MVP 与反例：最小先做哪层？何时不划算？

**F0**：现状只有事务型 Unit 成熟，能力型 Unit 仅有 teammate 雏形。**I**：一次性建齐四层与独立服务，会把验证周期拉长，且无法区分「路由有效」与「服务治理有效」两个变量。**R**：MVP 只做「能力卡 + 注册表 + 单一 L2 专家 + 规则优先路由」，具体顺序与退出判据见第 3 章；「何时不该用」的完整清单见第 4 章。

---

## 3. 最小可行方案（MVP）与实施顺序

范围：不改准入策略、不扩大 Mandate、不引入常驻服务、不接触凭据；只增加可读注册表与可回放 Decision 日志。

| 步骤 | 产出 | 退出判据 |
| --- | --- | --- |
| S1 | 能力卡 schema + 校验器（附录 A） | 三张示例卡通过校验，缺字段被拒 |
| S2 | 落 3 张卡：文件搜索、邮件检索 / 发送、代码评审 | 每张含 owner、effect、scope、budget、不适用场景 |
| S3 | `registry.json` + 命名 / 别名 / status 校验 | 同名覆盖被拒，alias 回指完成回滚演练 |
| S4 | Router 硬过滤 + Decision 日志，observe 不执行 | 越权候选被过滤可回放；零实际调用 |
| S5 | 接一个 L2 专家，跑通端到端（附录 D） | 产生六元组审计与成本读数 |
| S6 | 20 张真实工单 A/B 对照，决定是否切 auto | 四个核心假设全部成立才扩面 |

四个核心假设：① 路由准确率不低于人工指派基线（先定义标注集）；② 硬过滤零越权（由 Decision 核对）；③ token / 工单不显著上升（阈值由 S5 实测给定，不预设数字）；④ 至少一次跨工单复用。任一不成立即停止扩面，保留「工单 + skill」路径。

---

## 4. 风险、反例与「何时不该用」

主要风险：把 advisory 写域当权限、路由误判造成外部副作用、注册表成为新单点、僵尸专家、人设漂移、跨主机代理变通用 shell 后门、observe 长期不转 auto 导致空转；前三项靠 host 强制层、硬过滤 + 人工确认 + 灰度、Git 文件索引缓解（完整表见附录 H）。

**明确「何时不该用」，应退回「工单 + skill + 人工指派」**：

1. 工单低频、一次性，复用率接近 0（偶发一次性工作用普通 Session 更简单 [R5]）。
2. 能力数长期少于 5 且稳定，路由收益覆盖不了注册表维护成本。
3. 任务类别无法被准确分类——Anthropic 要求分类准确 [R11]，此时语义路由只增加不确定性。
4. 没有明确的卡片 owner 与评审流程，注册表会迅速腐烂。
5. 无法在 host 侧机器强制副作用等级与数据边界，「边界硬」不成立。
6. 单仓库、串行、人工全程把关，或失败成本远大于指派成本。

退出规则：MVP 阶段四个核心假设任一不成立即停止扩面；不以「已注册多少专家」为成功指标。

---

## 5. 待决问题清单

1. 休眠会话是否零 token？唤醒首轮成本？（需实测）
2. 能力身份是否需跨 root Session 持久？内部版本是否已改变 Team 绑定 [R3]？
3. 副作用 2 / 3 级的人工确认落在哪个界面与线程？
4. Mandate 是否需新增 capability_scope 字段？
5. 跨主机代理信任边界：谁持凭据、如何轮换、是否允许出网？
6. `stable` / `canary` 灰度比例与回滚 SLA。
7. 路由误判的标注集、样本量、准确率定义由谁负责。
8. 是否采用 A2A 式 JWS 签名 [R6]，谁签发与轮换密钥。
9. 「30 天零调用」阈值与复审频率是否合适。
10. 《Super-agent 设计探索》官方原文未取得公开 URL，本报告未引用其结论；需引用时补齐一手来源 [R15]。

---

## 附录 A 能力卡 Schema 与示例

### A.1 JSON Schema（Draft 2020-12 草案）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.org/schemas/capability-card-v1.schema.json",
  "title": "CapabilityCard",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id", "name", "version", "kind", "description", "purpose",
    "inputs", "outputs", "applicable", "inapplicable",
    "side_effect_level", "permissions", "limits", "implementation",
    "owner", "status", "policy_ref", "examples", "observability",
    "created_at", "updated_at", "checksum"
  ],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z0-9]+(\\.[a-z0-9-]+)+/[a-z0-9][a-z0-9._-]*$",
      "description": "反域名命名空间 / 名称，对齐 MCP Registry 命名 [R9]"
    },
    "name": { "type": "string", "minLength": 1 },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "kind": { "enum": ["tool", "skill", "persona", "service"] },
    "description": { "type": "string", "minLength": 10 },
    "purpose": { "type": "string", "minLength": 10 },
    "tags": { "type": "array", "items": { "type": "string" } },
    "inputs": { "$ref": "#/$defs/ioSchema" },
    "outputs": { "$ref": "#/$defs/ioSchema" },
    "applicable": { "type": "array", "minItems": 1, "items": { "type": "string" } },
    "inapplicable": { "type": "array", "minItems": 1, "items": { "type": "string" } },
    "side_effect_level": {
      "type": "integer", "minimum": 0, "maximum": 3,
      "description": "0 只读 / 1 本地可逆写 / 2 外部可见副作用 / 3 不可逆或跨信任域"
    },
    "permissions": {
      "type": "object",
      "additionalProperties": false,
      "required": ["fs_read", "fs_write", "exec", "egress"],
      "properties": {
        "fs_read": { "type": "array", "items": { "type": "string" } },
        "fs_write": { "type": "array", "items": { "type": "string" } },
        "exec": {
          "type": "array", "items": { "type": "string" },
          "description": "命令模板白名单；参数化传参，禁止拼接 shell"
        },
        "egress": {
          "type": "array", "items": { "type": "string" },
          "description": "允许访问的域名；空数组表示禁止出网"
        },
        "host": { "enum": ["local", "windows-agent", "remote"] },
        "data_classes": { "type": "array", "items": { "type": "string" } }
      }
    },
    "limits": {
      "type": "object",
      "additionalProperties": false,
      "required": ["timeout_ms", "max_tokens", "max_steps", "concurrency"],
      "properties": {
        "timeout_ms": { "type": "integer", "minimum": 1 },
        "max_tokens": { "type": "integer", "minimum": 1 },
        "max_steps": { "type": "integer", "minimum": 1 },
        "concurrency": { "type": "integer", "minimum": 1 },
        "max_cost_units": { "type": "number", "minimum": 0 }
      }
    },
    "implementation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["transport", "entrypoint"],
      "properties": {
        "transport": { "enum": ["cli", "mcp", "http", "session"] },
        "entrypoint": { "type": "string" },
        "session_mode": { "enum": ["fresh", "fork", "persistent"] },
        "host": { "type": "string" }
      }
    },
    "owner": { "type": "string", "description": "团队或角色标识，不含个人信息" },
    "status": { "enum": ["active", "deprecated", "deleted"] },
    "policy_ref": {
      "type": "object",
      "additionalProperties": false,
      "required": ["required_mandate_scope", "min_accept_mode"],
      "properties": {
        "required_mandate_scope": { "type": "array", "items": { "type": "string" } },
        "min_accept_mode": { "enum": ["off", "observe", "auto"] },
        "requires_human_confirmation": { "type": "boolean" }
      }
    },
    "examples": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["prompt", "expected_effect"],
        "properties": {
          "prompt": { "type": "string" },
          "expected_effect": { "type": "integer", "minimum": 0, "maximum": 3 }
        }
      }
    },
    "dependencies": { "type": "array", "items": { "type": "string" } },
    "observability": {
      "type": "object", "additionalProperties": false,
      "required": ["audit_fields"],
      "properties": {
        "audit_fields": { "type": "array", "items": { "type": "string" } },
        "metrics": { "type": "array", "items": { "type": "string" } }
      }
    },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "checksum": { "type": "string", "description": "对去除本字段后的规范化卡片计算 sha256" },
    "signature": { "type": "string", "description": "可选，对齐 A2A AgentCardSignature [R6]" }
  },
  "$defs": {
    "ioSchema": {
      "type": "object",
      "additionalProperties": false,
      "required": ["schema"],
      "properties": {
        "schema": { "type": "object", "description": "内嵌 JSON Schema" },
        "media_types": { "type": "array", "items": { "type": "string" } },
        "required": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

### A.2 TypeScript 类型（等价精简版）

```ts
type EffectLevel = 0 | 1 | 2 | 3;
type CardKind = 'tool' | 'skill' | 'persona' | 'service';
type CardStatus = 'active' | 'deprecated' | 'deleted';
type AcceptMode = 'off' | 'observe' | 'auto';

interface CapabilityCard {
  id: string;                 // reverse-domain/name
  name: string;
  version: string;            // semver
  kind: CardKind;
  description: string;
  purpose: string;
  tags?: string[];
  inputs: { schema: object; media_types?: string[]; required?: string[] };
  outputs: { schema: object; media_types?: string[]; required?: string[] };
  applicable: string[];
  inapplicable: string[];
  side_effect_level: EffectLevel;
  permissions: {
    fs_read: string[]; fs_write: string[]; exec: string[]; egress: string[];
    host?: 'local' | 'windows-agent' | 'remote'; data_classes?: string[];
  };
  limits: {
    timeout_ms: number; max_tokens: number; max_steps: number; concurrency: number;
    max_cost_units?: number;
  };
  implementation: {
    transport: 'cli' | 'mcp' | 'http' | 'session'; entrypoint: string;
    session_mode?: 'fresh' | 'fork' | 'persistent'; host?: string;
  };
  owner: string;
  status: CardStatus;
  policy_ref: {
    required_mandate_scope: string[];
    min_accept_mode: AcceptMode;
    requires_human_confirmation?: boolean;
  };
  examples: { prompt: string; expected_effect: EffectLevel }[];
  dependencies?: string[];
  observability: { audit_fields: string[]; metrics?: string[] };
  created_at: string; updated_at: string; checksum: string; signature?: string;
}
```

### A.3 示例卡 1：跨文件系统文件搜索（L0，只读）

```json
{
  "id": "io.example.search/file-find",
  "name": "跨主机文件搜索",
  "version": "1.2.0",
  "kind": "tool",
  "description": "在受控代理主机上按文件名与内容模式检索文件，返回结构化路径列表，不返回文件内容。",
  "purpose": "为工单提供确定性的文件定位能力，避免给出通用 shell 访问。",
  "tags": ["search", "readonly", "cross-host"],
  "inputs": {
    "schema": { "type": "object", "properties": { "pattern": { "type": "string" }, "root": { "type": "string" } }, "required": ["pattern"] },
    "media_types": ["application/json"], "required": ["pattern"]
  },
  "outputs": {
    "schema": { "type": "object", "properties": { "paths": { "type": "array", "items": { "type": "string" } } } },
    "media_types": ["application/json"]
  },
  "applicable": ["定位指定根路径下的文件", "按文件名模式批量检索"],
  "inapplicable": ["读取或修改文件内容", "遍历白名单之外的路径"],
  "side_effect_level": 0,
  "permissions": {
    "fs_read": ["D:/repos/*/src", "/srv/repos/*/src"],
    "fs_write": [],
    "exec": ["find-files --pattern {{pattern}} --root {{root}}"],
    "egress": [],
    "host": "windows-agent",
    "data_classes": ["internal-source"]
  },
  "limits": { "timeout_ms": 15000, "max_tokens": 2000, "max_steps": 1, "concurrency": 4 },
  "implementation": { "transport": "cli", "entrypoint": "find-files", "host": "windows-agent" },
  "owner": "platform-team",
  "status": "active",
  "policy_ref": { "required_mandate_scope": ["repo:read"], "min_accept_mode": "observe" },
  "examples": [{ "prompt": "找出 src 下所有 *router*.ts", "expected_effect": 0 }],
  "observability": { "audit_fields": ["ticket_id", "mandate_id", "pattern", "root", "result_count", "duration_ms"], "metrics": ["invocations", "p95_latency_ms"] },
  "created_at": "2026-11-13T00:00:00Z",
  "updated_at": "2026-11-13T00:00:00Z",
  "checksum": "sha256:PLACEHOLDER_FOR_EXAMPLE_ONLY"
}
```

### A.4 示例卡 2：邮件检索 / 发送（L0，高副作用）

```json
{
  "id": "io.example.mail/search-and-send",
  "name": "邮件检索与发送",
  "version": "2.0.0",
  "kind": "tool",
  "description": "检索指定邮箱的邮件元数据；发送需单独确认，发送动作不可撤销。",
  "purpose": "把外部可见副作用收敛到确定性实现与人工确认，避免由会话专家自由发挥。",
  "tags": ["mail", "external-effect", "human-confirmation"],
  "inputs": {
    "schema": { "type": "object", "properties": { "action": { "enum": ["search", "send"] }, "query": { "type": "string" }, "draft_id": { "type": "string" } }, "required": ["action"] },
    "media_types": ["application/json"], "required": ["action"]
  },
  "outputs": {
    "schema": { "type": "object", "properties": { "message_ids": { "type": "array", "items": { "type": "string" } }, "delivery_receipt": { "type": "string" } } },
    "media_types": ["application/json"]
  },
  "applicable": ["按主题或发件人检索邮件元数据", "发送已由人工确认的草稿"],
  "inapplicable": ["自动撰写并发送新邮件", "批量导出邮件正文"],
  "side_effect_level": 3,
  "permissions": {
    "fs_read": [], "fs_write": [],
    "exec": ["mailctl search --query {{query}}", "mailctl send --draft {{draft_id}}"],
    "egress": ["mail.example.org"], "host": "local", "data_classes": ["external-communication"]
  },
  "limits": { "timeout_ms": 30000, "max_tokens": 4000, "max_steps": 2, "concurrency": 1, "max_cost_units": 1 },
  "implementation": { "transport": "cli", "entrypoint": "mailctl" },
  "owner": "platform-team",
  "status": "active",
  "policy_ref": { "required_mandate_scope": ["mail:send"], "min_accept_mode": "auto", "requires_human_confirmation": true },
  "examples": [{ "prompt": "发送已确认的草稿 draft-42", "expected_effect": 3 }],
  "observability": { "audit_fields": ["ticket_id", "mandate_id", "action", "draft_id", "approver_role", "delivery_receipt"], "metrics": ["send_count", "confirmation_rate"] },
  "created_at": "2026-11-13T00:00:00Z",
  "updated_at": "2026-11-13T00:00:00Z",
  "checksum": "sha256:PLACEHOLDER_FOR_EXAMPLE_ONLY"
}
```

### A.5 示例卡 3：代码评审专家（L2，常驻会话）

```json
{
  "id": "io.example.review/code-reviewer",
  "name": "代码评审专家",
  "version": "0.3.0",
  "kind": "persona",
  "description": "常驻评审会话，携带项目约定与历史评审记忆，对 PR 给出分级意见与证据路径。",
  "purpose": "让需要项目记忆与多轮反馈的评审能力跨工单复用，而不是每次临时 spawn。",
  "tags": ["review", "persona", "project-memory"],
  "inputs": {
    "schema": { "type": "object", "properties": { "pr_ref": { "type": "string" }, "focus": { "type": "string" } }, "required": ["pr_ref"] },
    "media_types": ["text/plain", "application/json"], "required": ["pr_ref"]
  },
  "outputs": {
    "schema": { "type": "object", "properties": { "findings": { "type": "array", "items": { "type": "object" } }, "summary": { "type": "string" } } },
    "media_types": ["application/json"]
  },
  "applicable": ["多轮 PR 评审与追问", "沿用项目既有评审约定"],
  "inapplicable": ["直接合并或关闭 PR", "修改被评审代码"],
  "side_effect_level": 1,
  "permissions": {
    "fs_read": ["D:/repos/*"], "fs_write": ["D:/repos/*/review-notes"],
    "exec": ["git diff", "git show"], "egress": [], "host": "local", "data_classes": ["internal-source"]
  },
  "limits": { "timeout_ms": 600000, "max_tokens": 40000, "max_steps": 60, "concurrency": 2 },
  "implementation": { "transport": "session", "entrypoint": "teammate:code-reviewer", "session_mode": "fork" },
  "owner": "review-guild",
  "status": "active",
  "policy_ref": { "required_mandate_scope": ["repo:review"], "min_accept_mode": "observe" },
  "examples": [{ "prompt": "评审 PR-42，重点看并发安全", "expected_effect": 1 }],
  "dependencies": ["io.example.search/file-find@1.2.0"],
  "observability": { "audit_fields": ["ticket_id", "mandate_id", "pr_ref", "findings_count", "tokens_used", "fallback_used"], "metrics": ["invocations", "reuse_rate", "p95_latency_ms"] },
  "created_at": "2026-11-13T00:00:00Z",
  "updated_at": "2026-11-13T00:00:00Z",
  "checksum": "sha256:PLACEHOLDER_FOR_EXAMPLE_ONLY"
}
```

> 注：示例中的 `checksum`、`mail.example.org`、路径与 ID 均为占位示例值，不是实测数据，也不代表任何真实环境配置。

---

## 附录 B 注册表数据模型与一条示例注册记录

四类对象：`Entry`（按 id 聚合）、`VersionRecord`（不可变版本 + status）、`Alias`（指向唯一版本）、`Stats`（调用侧统计，示例值非实测）。`status` 是 VersionRecord 上唯一可变的字段，对齐 MCP Registry 的做法 [R9]。

```json
{
  "registry_version": "1.0",
  "generated_at": "2026-11-13T00:00:00Z",
  "source": "git:capabilities/",
  "aliases": {
    "stable": "io.example.review/code-reviewer@0.3.0",
    "canary": "io.example.review/code-reviewer@0.4.0-rc.1"
  },
  "entries": [
    {
      "id": "io.example.review/code-reviewer",
      "owner": "review-guild",
      "visibility": { "namespaces": ["io.example.review"], "ticket_scopes": ["repo:review"] },
      "versions": [
        {
          "version": "0.3.0",
          "status": "active",
          "card_path": "capabilities/review/code-reviewer-0.3.0.json",
          "checksum": "sha256:PLACEHOLDER_FOR_EXAMPLE_ONLY",
          "published_at": "2026-11-13T00:00:00Z",
          "side_effect_level": 1
        }
      ],
      "stats": { "invocations_30d": 0, "last_invoked_at": null, "success_rate": null }
    }
  ]
}
```

回滚演练：`stable` 从 `0.3.0` 回指 `0.2.0` 即完成新调用回滚；已在途工单继续使用其 Decision 中 pin 的 `0.3.0`，不中断、不回溯。

---

## 附录 C 路由伪代码（含兜底）

```text
function route(ticket, message, registry, policy):
    d = Decision(ticket.id, policy.version, ticket.mandate.id)

    # 1) 取候选：状态可见 + 命名空间在 Mandate 允许范围内
    candidates = registry.list(status == "active")
    candidates = [c for c in candidates if in_allowed_namespace(c.id, ticket.mandate)]

    # 2) 硬过滤（Gate 前置，先做减法，绝不扩大授权）
    candidates = [c for c in candidates if
        c.side_effect_level <= ticket.mandate.max_effect and
        c.policy_ref.required_mandate_scope <= ticket.mandate.scope and
        c.limits.max_tokens <= ticket.budget.remaining and
        resolve_alias_or_pin(c) != None]
    d.candidates = [c.id + "@" + c.version for c in candidates]

    # 3) 显式指定优先
    specified = parse_explicit_capability(message)
    if specified in candidates:
        chosen, reason = specified, "explicit"
    elif candidates.is_empty():
        return fallback(d, "no-match", GENERAL_WORKER)
    else:
        # 4) 规则 + 语义，仅在过滤后的候选集内 top-1
        scores = [(c, rule_match(c, ticket) + semantic_score(c, message)) for c in candidates]
        best, why = argmax(scores)
        if why.confidence < policy.min_confidence:
            return fallback(d, "low-confidence", HUMAN_CONFIRM)
        chosen, reason = best, why.reason + "; " + why.evidence

    # 5) 冻结决策：同一工单续跑不重算，抑制路由抖动
    d.bind(ticket.id, chosen.id + "@" + chosen.version, reason)
    if ticket.decision_pinned and ticket.decision_pinned != d.binding:
        d.chosen = ticket.decision_pinned       # 沿用原决策

    # 6) 灰度：observe 只记录，不执行
    if policy.accept_mode == "observe" and reason != "explicit":
        d.outcome = "would_route"
        log(d)
        return NO_EXECUTION

    # 7) 执行；Gate 在执行点强制 scope / effect / budget
    try:
        result = invoke(chosen, ticket, enforce_gate=True)
        d.actual_effect, d.cost = result.effect, result.cost
    except CapabilityError:
        d.fallback_used = "degrade"
        result = try_lower_layer(chosen, ticket)
        if result is None:
            return fallback(d, "invoke-failed", GENERAL_WORKER)
    log(d)
    return result

function fallback(d, reason, target):
    d.fallback_used = reason
    d.chosen = target
    log(d)
    return target        # 关键：任何兜底都不修改 ticket.mandate
```

---

## 附录 D 一次端到端调用的时序描述

1. 外部消息进入 Eval，通过准入后生成 Ticket-42 与不可变 Mandate（policy_version v7，scope `repo:review`，max_effect 1）[R2]。
2. Router 读取 Git 版本化的 `registry.json`，按 Mandate 过滤出可见能力卡。
3. 渐进披露：仅把候选卡的 name / description / effect 放进 Router 上下文，不加载全文 [R10]。
4. 硬过滤：排除 `mail/send`（effect 3 > 1）与非白名单命名空间的卡；Decision 记录候选集。
5. 语义评估在剩余候选内给 `code-reviewer@0.3.0` 最高分，Decision 记录理由与证据。
6. observe 阶段：只写 `would_route`，不执行；切 auto 后 Decision 冻结绑定 `(Ticket-42, code-reviewer@0.3.0)`。
7. host 校验卡片 checksum 与 scope，按 `session_mode: fork` 唤醒具名 teammate [R3]。
8. 专家读取 persona 记忆与 PR diff；过程中每次工具调用都经 Gate 校验路径、副作用等级与剩余预算。
9. 共享任务板记录 owner / 依赖 / writeScopes，仅用于意图协调，不作为权限 [R3]。
10. 结果经原 Channel 回线程；审计写入调用六元组、token 与耗时。
11. 工单结束释放 worker；专家会话按 TTL 转 idle，记忆写检查点。
12. 若连续 30 天零调用，卡片自动置为 `deprecated`，等待 owner 复审。

---

## 附录 E 术语表

| 术语 | 定义 |
| --- | --- |
| Capability Unit（能力型 Unit） | 以能力契约 + 边界 + 权限描述、可复用可专精的执行单元；与随单生灭的事务型 Unit 正交。 |
| 能力卡（Capability Card） | 描述一个能力能做什么、边界在哪、如何调用的标准元数据；本设计中是唯一事实源。 |
| 注册表（Registry） | 能力卡的目录与发现入口；MVP 为 Git 版本化文件 + 索引，不是独立服务。 |
| gating / 路由 | 根据任务从候选能力中选出执行单元的过程；本报告指显式规则 + 语义评估的混合决策。 |
| Decision | 一次路由的可回放记录：候选集、理由、选中项、policy_version、mandate_id、兜底与实际副作用。 |
| Mandate | 工单的不可变授权范围，来自准入策略；只有 accept 创建、人 stop 撤销、revalidation 失败吊销三种变更 [R2]。 |
| side_effect_level | 0 只读 / 1 本地可逆写 / 2 外部可见副作用 / 3 不可逆或跨信任域；由 host 强制，不由提示词保证。 |
| Gate | host 侧执行点，在调用发生时校验路径、副作用等级、egress 与预算。 |
| fresh / fork | teammate 的两种创建方式：干净上下文 / 继承已完成对话上下文的分支 [R3]。 |
| alias（stable / canary） | 指向唯一不可变版本的可变指针，用于灰度与回滚。 |
| observe 模式 | 正向决策只记录「本会路由 / 本会接纳」而不执行的灰度档位 [R2]。 |
| 僵尸单元 | 已注册但长期零调用、仍占用维护与注意力成本的单元。 |
| advisory writeScopes | 共享任务板上声明写入意图的路径前缀，明确不是锁、不构成权限 [R3]。 |

---

## 附录 F 引用来源与核验状态

> 核验说明：标注「已读取」表示本次调研中页面正文已成功取得并核对；这是内容可读性核验，不等同于对线上服务实时 HTTP 状态的独立探测。标注「未验证」的条目不作为结论依据。所有链接均为公开页面。

| 编号 | 来源与版本 | 核验状态 |
| --- | --- | --- |
| R1 | `https://github.com/deepseek-ai/dsh-superagent-prototype` — 官方仓库，MIT，首次提交 `8c32a9d`（2026-10-31）；README 声明为 research prototype、非官方产品、与内部版本及设计文章不完全一致；含 docs/000–008 编号文档 | 已读取（2026-11-13） |
| R2 | `https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/002-authorization.md` — 002 Authorization：Mandate 三操作、Policy version、Gate 三强度、off / observe / auto、订阅不增权限、orchestrator_route、revalidation | 已读取 |
| R3 | `https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/agent-team.md` — 官方仓库 master 分支：`TeamId` brands root `SessionId`；`writeScopes` 为 advisory 而非锁；`revision` CAS；历史 roster 不授权；`context: 'fresh' | 'fork'` | 已读取。注：`main` 分支同名路径实测返回 404 |
| R4 | `https://github.com/deepseek-ai/deepseek-harness` — 官方仓库，2026-11-13 仍有提交，页面可见 `0.2.2-rc.3` 相关工作树信息 | 已读取 |
| R5 | `https://deepseekharness.io/agent-teams` — **第三方文档站（非官方）**：描述 Agent Teams `0.1.0-rc.8`（tag 2026-08-19）、npm 实验包 `0.1.5-alpha.2`（2026-09-09）、默认关闭、experimental 契约可变、持久组织 ≠ Agent Teams | 已读取；技术细节以 R3/R4 为准 |
| R6 | `https://a2a-protocol.org/latest/specification` — A2A Protocol Specification，Latest Released Version `1.0.0`（协议版本 `1.0`）；AgentCard 与 AgentSkill 字段、JWS signatures | 已读取 |
| R7 | `https://a2a-protocol.org/v0.2.5/specification` — A2A `0.2.5`（页面标注 out of date）：well-known URI / Registries / Direct Config 三种发现机制、`/.well-known/agent.json`、最小权限、按 AgentSkill.id 授权、卡内不放明文密钥 | 已读取 |
| R8 | `https://modelcontextprotocol.io/specification/2025-11-25/server/tools` — MCP `2025-11-25`（页面提示 latest 为 `2026-07-28`）：Tool 字段、annotations 视为不可信、human in the loop、输入校验与审计日志 | 已读取 |
| R9 | `https://modelcontextprotocol.io/registry/registry-aggregators` — MCP Registry（preview）：反域名命名、`/v0.1/servers` 与 versions / latest、status `deprecated` / `deleted`、不提供 uptime 与数据持久性保证 | 已读取 |
| R10 | `https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills` — 2025-10-16：渐进披露三级、skills 可打包确定性脚本 | 已读取（无 www 的 URL 会重定向至 www） |
| R11 | `https://www.anthropic.com/engineering/building-effective-agents` — 2024-12-19：routing workflow 要求分类准确；仅在复杂度被证明改善结果时才增加 | 已读取（无 www 的 URL 实测 fetch failed，改用 www 成功） |
| R12 | `https://arxiv.org/abs/1701.06538` — Shazeer et al., *Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer*, 2017 | 已读取 abs 页 |
| R13 | `https://arxiv.org/abs/2101.03961` — Fedus, Zoph, Shazeer, *Switch Transformers*, v3 2022-06-16（辅助负载均衡损失、capacity factor） | 已读取 abs 页 |
| R14 | `https://arxiv.org/abs/2204.08396` — Dai et al., *StableMoE: Stable Routing Strategy for Mixture of Experts*, ACL 2022（routing fluctuation、冻结 router） | 已读取 abs 页 |
| R15 | 《Super-agent 设计探索：迈向更自主的 Agent 系统》——官方原文为 DeepSeek Harness 团队微信公众号文章（2026-10-31），未取得可公开访问的原文 URL；标题与日期可见公开报道：`https://news.cnr.cn/native/gd/kx/20261102/t20261102_527860134.shtml`、`https://3w.huanqiu.com/a/c36dc8/4TqWPXmdLEt` | **未验证原文**；二手报道仅用于确认标题与日期，不用于技术结论 |

---

## 附录 G 验收自检（实测读数）

统计口径：正文 = 文件开头至「附录 A」之前；中文字符按 CJK 统一表意文字计数（不含标点、英文、代码）。下表读数由落盘文件实测得到，不含本附录自身文本。

| 项目 | 实测值 | 验收要求 |
| --- | --- | --- |
| 正文中文字符数 | 3526 | 2000–4000，达标 |
| 正文总字符数（含 Markdown / 英文 / 标点） | 8315 | 参考值 |
| 更严口径（中文字符 + 英文标识符 + 数字） | 4155 | 参考值；英文标识符 454、数字 175，重复计数使该口径偏高 |
| 九个问题逐项作答 | 9 个小节（2.1–2.9） | 达标 |
| F0 / F1 / I / R 标注出现次数 | 5 / 7 / 10 / 12 | 每问均含事实、推断、建议，达标 |
| 架构方案对比 | 3 种（A / B / C），明确推荐 B | ≥2 种且明确推荐，达标 |
| MVP 步骤 | 6 步（S1–S6），含退出判据与四个核心假设 | 可执行，达标 |
| 能力卡示例 | 3 张（文件搜索 / 邮件检索发送 / 代码评审） | 2–3 个，达标 |
| JSON Schema 与示例记录 | 5 个 JSON 代码块，全部通过 `json.loads` 解析 | 可落地，达标 |
| TypeScript 类型 / 路由伪代码 | 各 1 个代码块 | 达标 |
| 引用条目 | 15 条（R1–R15），逐条标注版本与核验状态 | 达标 |
| 待决问题 | 10 条 | 达标 |
| 「何时不该用」 | 6 条明确退出条件 + 退出规则 | 达标 |
| 私有 / 个人信息扫描 | 未检出（示例均使用 example.org 与占位值） | 达标 |

链接核验的失败项也如实记录：`https://github.com/deepseek-ai/deepseek-harness/blob/main/docs/subsystems/agent-team.md` 实测 404（改从 master 分支取得，见 R3）；无 `www` 的 `https://anthropic.com/engineering/building-effective-agents` 实测 fetch failed（改用 www 成功，见 R11）。R5 为第三方文档站，R15 官方原文未取得公开 URL，均已在 F 中标注，未作为技术结论依据。

可重跑校验命令（Windows Git Bash / bash，Python 3）：

```bash
python -c "import re,pathlib; p=pathlib.Path(r'D:/WorkBuddyCache/2026-11-13-17-41-06/capability-unit-research-report.md'); s=p.read_text(encoding='utf-8'); b=s.split('## 附录 A')[0]; c=lambda t:len(re.findall(r'[\u4e00-\u9fff]',t)); print('CJK_BODY',c(b),'CHARS_BODY',len(b),'NINE',len(re.findall(r'^### 2\.\d ',b,re.M)),'JSON_BLOCKS',s.count(chr(96)*3+'json'),'REF_ROWS',len(re.findall(r'^\| R\d+ \|',s,re.M)),'BYTES',p.stat().st_size,'LINES',s.count(chr(10))+1)"
```

```bash
python -c "import re,json,pathlib; s=pathlib.Path(r'D:/WorkBuddyCache/2026-11-13-17-41-06/capability-unit-research-report.md').read_text(encoding='utf-8'); blocks=re.findall(chr(96)*3+'json'+chr(10)+r'(.*?)'+chr(10)+chr(96)*3,s,re.S); [json.loads(x) for x in blocks]; print('ALL_JSON_VALID',len(blocks))"
```

---

## 附录 H 详细论证与补充表

> 本附录承载正文为保证 2000–4000 字而移出的展开论证，不影响正文结论。

### H.1 神经 MoE gating 与显式规则路由逐条对比

| 维度 | 神经 MoE gating | 显式规则 + 语义路由 |
| --- | --- | --- |
| 决策对象 | token → expert，连续向量、top-k | 工单 → 能力，离散 ID、通常唯一 |
| 首要目标 | 模型质量、计算稀疏、负载均衡 | 授权正确性、可审计、成本可控 |
| 错误代价 | 质量下降，可经梯度纠正 | 越权或不可撤销副作用，必须事前拦截 |
| 负载不均 | 辅助负载均衡损失、capacity factor [R13] | 不追求均衡；用规则分片、限流、强制降级 |
| 路由抖动 | StableMoE 蒸馏并冻结 router [R14] | `(ticket_id, capability@version)` 绑定并冻结 Decision |
| 专家坍塌 | dying expert / routing collapse | 「所有活都派给最强专家」→ 调用率看板 + owner 复审 |
| 可观测性 | 路由分布统计（训练期） | 逐次 Decision 日志，可回放 [R2][R8] |
| 纠正方式 | 训练时反向传播 | 改规则 / 改卡 / 别名回滚，立即生效 |
| 相同点 | 都需要候选集、选择函数、失败兜底与负载观测 | 同左 |

结论：两者共享「稀疏选择」的形式，但优化目标不同，因此不能把负载均衡损失、soft routing 等机制直接移植到授权链路上；可借鉴的只有「候选集 + 打分 + 兜底 + 观测」这一结构。

### H.2 硬边界五维执行表

| 维度 | 硬约束 | 执行点 | 违反时 | 反例（不该怎么做） |
| --- | --- | --- | --- | --- |
| 能力契约 | 卡片不可变、校验 checksum / 签名，模型不得改卡 | registry 校验器 | 拒绝加载并告警 | 让模型在运行时自行补充权限字段 |
| 权限与副作用 | 0 只读 / 1 本地可逆写 / 2 外部可见 / 3 不可逆；≥2 须人工确认 | host / gateway 执行点 | 阻断调用，写审计 | 把「不要发邮件」写进提示词当作控制 |
| 资源与注意力 | 超时、max_tokens、max_steps、并发上限，按 Ticket 记账 | runtime 预算器 | 中断并降级 | 只靠专家自觉「少想一点」 |
| 版本与废弃 | pin 不可变版本，工单内不换；status 只影响新调用 | registry + router | 拒绝隐式升级 | 在长跑工单中途自动切到新版本 |
| 数据访问 | 读写路径前缀、egress 域名、数据分类标签 | host 文件系统 / 网络层 | 拒绝并记拦截 | 用共享任务板的 advisory writeScopes 代替锁 [R3] |

### H.3 跨文件系统、跨主机与外部 CLI 的完整调用约定

1. 能力卡只声明 `host`、`fs_read` / `fs_write` 根路径、`exec` 命令模板、`egress` 域名与 `data_classes`，不包含凭据。
2. Gate 在调用前校验 Mandate scope、`side_effect_level` 上限、路径前缀、egress 白名单与剩余预算；不通过直接拒绝并写拦截记录。
3. host 侧受控代理进程按模板做参数化调用（禁止字符串拼接 shell、禁止通配符越出白名单、禁止返回原始 shell 句柄）。
4. 只读挂载优先；输出必须是结构化 JSON（路径列表、命中数、退出码），超时与速率限制在代理侧强制。
5. 每次调用写审计：ticket_id、mandate_id、card_id@version、命令模板 ID、参数摘要、结果摘要、耗时、副作用等级。
6. agent 只拿到结构化结果，拿不到通用 shell、主机凭据或跨主机跳转能力。

具体映射：Windows 侧文件搜索脚本 → `host: windows-agent`、effect 0、`exec` 为 `find-files --pattern {{pattern}} --root {{root}}`、egress 空；邮件检索 / 发送脚本 → effect 2 / 3、`exec` 为 `mailctl search|send` 两个模板、egress 仅邮件服务域名、发送需 `requires_human_confirmation`。两者都需要更硬的边界，不需要更多自主性，因此都不升 L2。示例见附录 A.3 / A.4。

### H.4 与现有机制的逐项映射表

| 现有机制 | 可直接复用 | 必须新增或改造 |
| --- | --- | --- |
| Policy、准入表、off / observe / auto、Decision | 路由灰度与留痕 | 路由候选集的命名空间过滤 |
| Mandate 不可变 + policy_version + 订阅不增权限 | 调用授权上限 | 能力调用级 scope 与副作用等级字段 |
| Ticket / worker / Subscription | 能力调用的执行与结果回传容器 | 无 |
| 共享任务板（owner / 依赖 / writeScopes） | 意图协调 | **不可当权限**；需新增 host 强制层 [R3] |
| teammate fresh / fork、具名可唤醒 | L2 专家实例 | 跨 root Session 的能力身份与生命周期（`TeamId` 绑定 root SessionId [R3]） |
| skills 渐进披露 | 注册表索引与卡片懒加载 | 无 |
| durable mailbox + 任务快照 revision CAS | 崩溃恢复 | 无 |
| —— | —— | 能力卡 schema、注册表与别名回滚、调用级预算计量、副作用等级的 host 执行点、专家记忆持久化 |

### H.5 「是否真的更优」的度量指标

| 指标 | 定义 | 基线来源 | 判定方向 |
| --- | --- | --- | --- |
| 一次通过率 | 无需返工即满足工单完成判据的比例 | 工单 + skill + 人工指派 | 越高越好 |
| 返工轮次 | 每张工单的平均追加消息 / 重开次数 | 同上 | 越低越好 |
| 人工指派次数 | 每张工单需要人点名能力或专家的次数 | 同上 | 越低越好 |
| token / 工单 | 一张工单端到端消耗（含专家唤醒与重放） | 同上 | 不显著上升 |
| P95 完成时间 | 工单从准入到就绪的 P95 耗时 | 同上 | 不劣化 |
| 误路由率 | 被人工纠正或兜底接管的路由占比 | 标注集 | 越低越好 |
| 越权拦截数 | Gate 阻断的调用次数 | Gate 日志 | 用于验证边界有效性，非零即说明过滤在起作用 |
| 复用率 / 僵尸率 | 被调用过的卡占比 / 30 天零调用的卡占比 | 注册表统计 | 复用率上升、僵尸率下降 |

所有指标必须来自 A/B 对照实验；公开原型 README 明确其为 research code [R1]，不提供可直接引用的收益数字。

### H.6 风险完整表

| 风险 | 触发条件 | 缓解 | 残留 |
| --- | --- | --- | --- |
| 把 advisory 写域当权限 | 直接复用共享任务板做隔离 | host 强制层 + 执行点校验 [R3] | 需内部验证实现 |
| 路由误判造成外部副作用 | 语义评估命中高副作用能力 | 硬过滤 + ≥2 级人工确认 + observe 灰度 | 无法完全消除 |
| 注册表成为新单点 | 过早采用独立服务 | MVP 用 Git 文件 + 离线索引 | 跨团队时需重新设计 |
| 僵尸专家 | 注册即实例化 | 按需 spawn + 30 天零调用自动废弃 | 依赖 owner 复审 |
| 人设漂移 / 记忆污染 | fork 继承过多历史上下文 | 默认 fresh、记忆写检查点、定期复审 | 需内部验证 |
| 跨主机代理变通用 shell 后门 | 允许字符串拼命令 | 参数化调用 + 命令模板白名单 | 需安全评审 |
| 体系空转 | observe 长期不转 auto | S6 设明确切换判据 | 组织决策 |

### H.7 验收覆盖索引

| 工作单问题 | 正文小节 | 事实 / 推断 / 建议 | 支撑附录 |
| --- | --- | --- | --- |
| 1 单元分层 | 2.1 | F0 + F1 + I + R | H.2、A.3–A.5 |
| 2 能力契约 | 2.2 | F1 + I + R | A.1、A.2、A.3–A.5 |
| 3 注册表 | 2.3 | F1 + I + R | B |
| 4 路由 gating | 2.4 | F1 + I + R | C、H.1 |
| 5 硬边界 | 2.5 | F1 + I + R | H.2、H.3 |
| 6 生命周期与成本 | 2.6 | F0 + F1 + I + R | D、B（stats） |
| 7 复用与治理 | 2.7 | F1 + I + R | D、H.5 |
| 8 与现有机制映射 | 2.8 | F0/F1 + I + R | H.4 |
| 9 MVP 与反例 | 2.9、第 3、4 章 | F0 + I + R | C、D、G、H.6 |

