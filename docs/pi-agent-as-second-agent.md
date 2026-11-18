# PI Agent 作为 WSL2 第二个 Agent：实验选型调研

- 日期：2026-11-18
- 项目：PI Agent 作为 WSL2 第二个 Agent 的实验选型（新项目）
- 交付范围：调研结论 + 分层选型建议 + 最小实验方案（P0 已完成实测）
- 证据约定：每条关键判断标注 **【事实】**（附来源或本机命令）/**【推断】**/**【建议】**；本机未验证的项统一列在 §7.3，不混入事实。
- 本报告基于 2026-11-18 的公开资料与本机 WSL2 隔离探针，结论只对当前部署成立。

---

## 0. 结论先行

**一句话：PI Agent 值得作为 WSL2 的第二个 Agent 做实验，但它的位置是「受控 worker + 实验沙盒」，不是新的 Orchestrator，也不该现在替代 DSH；三个已知件不是三选一，而是三个不同层的候选。**

1. **PI Agent 本体可行、成本低（已实测）**：隔离安装 12 秒 / 160MB，`--help` 322ms，无 key 也能完成 RPC 握手（0.27s）；DeepSeek 是内置 provider（`DEEPSEEK_API_KEY`，1M 上下文模型）；配置可用 `PI_CODING_AGENT_DIR` 隔离。**没有真实模型调用**（未使用共享凭据）。
2. **Pi 的强项与短板都很清楚**：树状单文件会话、30+ 扩展事件（`tool_call` 可阻断、`tool_result` 可改写、`agent_before_settle` 可续跑）、skills 渐进披露、RPC（33 条命令）/SDK 一等公民；但**没有内建 sub-agents、plan mode、权限系统、验证器、看板**——治理与验证必须外置。
3. **三个已知件的定位（【事实】+【建议】）**：
   - **mattSkill = 技能层**：`mattpocock/skills` v1.3.2（27 个技能，含 grilling），MIT。Pi 1.5.2 实测 **27/27 技能零改动可发现**。→ **建议采用：装上游快照 + 挑 6–8 个 + 一次性轻适配**。
   - **J-Space = 状态/认知层**：上游 `J-Space-Cognition-Suite`（Apache-2.0，2,954★，单维护者、2 个月未 push）；四个 npm 包是四家独立第三方适配，Pi 两包停在 Pi 0.84 时代。它有真实外部状态（`.jspace/control.json`），但只是**协作式结构门禁**，不验证现实。→ **建议不装，只借 3 个机制自建约 100 行**。
   - **LHH = 编排/审计模式**：高德 `AMAP-ML/LongHorizon-Harness`（MIT，1,876★，v0.1.8），Manager-Executor-Auditor 循环，**需求②「执行与验证分离」的最佳参考实现**。但它是套在 agent 外的第三层，Pi 未被支持（issue #73 open，需自写 adapter 约 150–250 行），且有 git 审计误报 bug（#98）。→ **建议：只做架构参考 + 一次性 1 小时验证，不装成第二 agent**。
4. **推荐组合**：**DSH SuperAgent 继续当控制面**（授权、工单、外部锚、统一看板、验收），**Pi 作为受控 worker**（RPC/CLI 驱动，单任务单目录、fresh context）；技能层装 mattpocock 子集；状态/门禁自建轻量 `state.json + gate.py`（借 J-Space 账本 + LHH Auditor 结构）；LHH 只做一次性验证。**不建议 Pi 当 Orchestrator**（需第三方 subagent 包，等于第三套任务板/审批/看板，正面撞「维护预算」约束）。
5. **最小实验（WIP=1）**：P0 已完成（本次探针）→ P1 技能层（0.5–1 天）→ P2 状态/门禁（1–2 天）→ P3 worker 位（1–2 天）→ P4 可选 LHH 一次性验证（约 1 小时）。每阶段先写 ADR、再动手，验收判据见 §6。
6. **需要你拍板的 6 件事**见 §8：模型通道与预算、Pi 可写目录、实验范围/WIP、第三方包策略、成功判据、长期定位。

---

## 1. 需求基线（来自你的 grill 总结）

本报告用你的总结作为唯一需求来源，不增不减，只把它转成可判定的评估口径。

### 1.1 根本目标

- **文件和项目管理不依赖回翻对话历史**；
- **skill 复用率高，同一个坑不反复踩**；
- 上位需求是「**可信的自主性**」：长期自主运行，错误不累积、不悄悄漂移，注意力只花在决策、验收和升级项上。

### 1.2 约束

- 你是**唯一决策枢纽**，注意力有限、并行线多：设 WIP 上限、只升级决策项、验收尽量机械化、不为 5 秒的烦恼搭三天的框架。
- 维护机制**已耗掉大部分精力和 token**，就地纠正已堆成屎山。
- 环境**单机、同账号、没有权限边界**。

### 1.3 七条需求 → 本报告的判定口径

| # | 需求 | 判定口径（本报告用） |
|---|---|---|
| 1 | 决策可追溯 | 有独立的决策文件/账本，能回答理由、前提、是否仍有效、授权可查可撤 |
| 2 | 执行与验证分离 | 存在独立于执行者的验证动作，完成判定由客观证据而非自述决定 |
| 3 | 思考前口径正确、开局读取面瘦 | 启动时载入的规则/环境事实正确且体积小；按需展开 |
| 4 | 从失败中改进 | 能把复盘结论写回 skill / harness / 全局指令三个面 |
| 5 | 统一看板 | 一个地方能看到当前状态、分歧与收敛，而不是多套台账 |
| 6 | 分工与借鉴 | 外部件可接、自有部分文本化、可版本化 |
| 7 | 底座选型 | 在树状历史、hook、插件生态之间做明确取舍 |

### 1.4 五条未调和张力（评估时必须正面回答，见 §4.3）

完整链路 vs 维护预算；验证器稀缺；外部件版本不稳 + 无权限隔离；结构化 vs 填表摩擦；ADR 在先 vs 事后追认。

---

## 2. 事实底座：PI Agent、DSH 与本机环境

### 2.1 PI Agent 是什么

**【事实】** PI Agent = `pi.dev`，npm 包 `@earendil-works/pi-coding-agent`，仓库 `earendil-works/pi`（前身 `badlogic/pi-mono`），MIT。

| 项 | 值 |
|---|---|
| 版本/发布 | **1.5.2**（2026-11-10）；1.0.0 发布于 2026-10-01，**六周内 5 个 minor** |
| 热度 | 仓库 122,656★ / 15,826 forks；npm 单包 unpacked 24.4MB |
| 运行时 | Node ≥ 22.19（本机 24.22.2 满足） |
| 定位 | 「极简可扩展的终端 agent harness」；官方明说不内建 sub-agents、plan mode、权限弹窗 |
| 生态 | Pi 包目录 5,626 个（npm 发布）；模型目录 1,680 模型 / 42 个 provider 选项 |
| 模型 | DeepSeek 内置（`DEEPSEEK_API_KEY`）；任意 OpenAI 兼容端点可走 `models.json` |
| 与 DSH 关系 | **DSH 0.2.1-rc.3 已 vendor `@earendil-works/pi-ai@1.4.0`**（包 `dsh-llm-pi-ai`）——模型层同源，harness 各自独立 |

### 2.2 四种接口与扩展/钩子（决定它能站哪个位置）

**【事实】** Pi 有四种接口：interactive、print（`-p`）、JSON（`--mode json`）、**RPC（`--mode rpc`）**，外加进程内 **SDK**（`createAgentSession()`）。

- **RPC**：长驻子进程，stdin/stdout 走 JSONL，**33 条命令**（prompt / steer / follow_up / abort / compact / bash / get_tree / fork / clone / switch_session / set_model / get_session_stats 等），响应带 id 关联、事件流可重建。→ **外部编排器驱动 Pi 的官方一等公民接口**。
- **扩展**：进程内 TypeScript，30+ 事件；关键钩子：
  - `tool_call`——**可阻断/改写**工具调用；
  - `tool_result`——**可改写**结果；
  - `agent_before_settle`——可追加条目并**请求续跑**；
  - compaction、session、provider 请求等可完全接管。
  → 钩子足以**承接**「门禁 + 留痕」，但**不生产验证器**。
- **技能**：实现 Agent Skills 规范（目录 + `SKILL.md` + frontmatter）；启动只注入 name/description/path，按需读全文（渐进披露）。
- **会话**：JSONL 单文件树（entry 有 id/parentId），`/tree`、`/fork`、`/clone`、`/share`、`/export`；活动分支才进模型上下文。
- **安全**：**无内建权限系统**；工具与扩展以启动用户权限运行；project trust 只决定启动资源是否加载，不构成权限边界；隔离靠容器/微 VM。

### 2.3 WSL2 隔离探针（本次已实测，2026-11-18）

探针在本工单工作区的 `research/probe-pi/` 完成（不随本 PR 提交；HOME / `PI_CODING_AGENT_DIR` / TMPDIR 全部隔离，未触碰 `~/.pi`、`/root/.dsh`、3082 服务；可整体删除）。

| 项 | 结果 |
|---|---|
| 安装 | `npm install --prefix … @earendil-works/pi-coding-agent@1.5.2` → **12s / 123 包 / 160MB**，exit=0 |
| `--version` / `--help` | 1.5.2；help 正常输出，**322ms** |
| 无 key `pi -p` | exit=1，报 `No API key found…`，不落半截会话（351ms） |
| 假 key `--list-models deepseek` | 列出 `deepseek-flash` / `deepseek-v4-pro`（均 1M ctx / 384K out） |
| RPC 无 key | `get_state` **0.27s** 返回；关 stdin 后 exit=0，stderr 空 |
| TS 扩展 `-e` + RPC | `get_commands` 可见扩展命令，`session_start` 事件触发，exit=0 |
| 配置落点 | `PI_CODING_AGENT_DIR` 生效，未写 `~/.pi` |
| **未做** | 真实模型调用（无独立 key，未用共享凭据）、TUI、curl 安装器、内存占用 |

**【事实】** DeepSeek 内置、需独立 `DEEPSEEK_API_KEY`；DSH 已 vendor 同源 `pi-ai`，但两套 harness 的配置/会话/插件目录完全独立。

### 2.4 DSH 0.2.1-rc.3 对照（当前体系）

**【事实】**（本机审查 + 既有调研）：

- **控制面成熟**：工单/授权/外部锚/完成判定、worker 独立会话、Agent Teams（teammate + 共享任务板）、session-query/projection、`--profile acp` / `--profile sdk` / `headless`。
- **插件生态**：profile + bundles + `cordis.patch.yml` 叠加，`dsh plugin` 转发 pnpm，插件市场目录快照 11,744 条（含 `engines.dsh` 兼容声明与能力红线字段）；HMR 热重载。
- **技能**：`SKILL.md` + frontmatter，文件系统 provider / 任意 provider 注册表——**与 Pi 的 Agent Skills 同规范**，技能文本可跨 harness 复用。
- **【推断】差异**：DSH 没有 Pi 那种「单文件会话树 + 任意节点分叉」的面向用户能力（会话 JSONL + subagent fork 是另一套形状；本机包审查未见 `/tree` 等价物，未逐项实测）；也没有 Claude Code 式通用 hook 层（扩展靠 Cordis 插件/接缝，未找到 PreToolUse 类等价物）。

**结论：DSH 强在治理/看板/插件生态；Pi 强在树状历史/hook/RPC/最小上下文。两者是互补面，不是替代关系。**

---

## 3. 三个已知件的定位与评估

> 你给的三件物品不是同层竞品：**mattSkill 是技能包，J-Space 是状态/认知层，LHH 是编排/审计层**。把它们当「三个候选 agent」比较会得出错误结论。

### 3.1 mattSkill（技能层）——建议采用子集

**【事实】上游**：`github.com/mattpocock/skills`（"Skills for Real Engineers"），MIT，327,073★，v1.3.2（release 2026-10-29），近 90 天 116 commits；正式 27 个技能（engineering 20 + productivity 7），合计 129KB / 1,858 行。格式是 **Agent Skills 规范**（目录 + `SKILL.md` + YAML frontmatter），不是 Claude Code 私有格式；官方安装矩阵覆盖 Claude Code / Codex / Copilot / VS Code / Gemini CLI，其余走 `npx skills add … -a <agent>`（注释里含 `pi`，并注明各 agent 于 2026-10-07 实测）。

**【事实】「mattSkill」指代**：你 Windows DSH 桌面端装的 `dsh-mattpocock-skills-deck@1.9.0-beta.33` 就是该仓库 v1.3.2 的 27 技能快照 + 任务面板（Deck）；抽查其英文 grilling 与上游逐字节一致（SHA256 相同）。上游从未提及 DSH，**没有官方 DSH 移植**；Deck 是社区事实主线（382★、约 1.7 万下载/月），但它是 beta（88 版本/3 个月、62 open issues），且面板用本机 `gh` 权限直接改 issue——**不要把 Deck 当 Pi 的技能源**，只把它当 DSH 侧参考。

**【事实】grilling 技能**：30 行原语——把问题画成**决策树**，按**轮次**推进；每轮只问「前沿」（前置条件已定的决定），一轮问完整个前沿、每题编号并给 `➡️ 推荐答案`；事实由 agent 派子代理去查，**决定必须等用户**；前沿清空 + 用户确认「理解一致」前**不得动手**。典型 13 题约 3 轮。它**不产出固定文档**（`grill-with-docs` 才落 `GLOSSARY.md`/ADR）——你贴出的「目标/约束/需求/未调和张力」是事后结构化总结，不是技能原生格式（内容与 grill 已定分支一致）【推断】。

**【事实】Pi 接入实测**（隔离探针 env，Pi 1.5.2，只读发现、未调模型）：`--skill` 加载 27/27，0.4s；项目 `.agents/skills/` 需项目信任（无 `--approve` 则 0 个）；**用户级 `~/.agents/skills/` 免信任 27/27**。格式零改动可用。

**【事实】Pi 缺口**：Pi 内置工具只有 read/bash/edit/write，**没有 Skill tool**——上游 10 个文件里「Call the Skill tool with X」的互调用在 Pi 中指向不存在的工具（grill-me、grill-with-docs、handoff、implement、implement-spec、improve-codebase-architecture、retro、tdd、triage、wayfinder）；Pi **没有内置子代理**，而 grilling/code-review/implement-spec/wayfinder/research 等会派子代理（需社区 `pi-subagents` 一类扩展）。社区已有若干小移植包，但均新、小、非官方，不宜作底座。

**【建议】**：
- **装上游快照**（钉 v1.3.2）到用户级 `~/.agents/skills/`，**挑 6–8 个技能子集**：`grilling`、`writing-for-agents`、`tdd`、`diagnosing-bugs`、`domain-modeling`、`handoff`、`retro`、`code-review`（先接受单上下文降级）。不启用需要子代理又无替代的（`implement-spec`、`wayfinder` 等）。
- **一次性轻适配**：把启用文件的「Call the Skill tool with X」改为「读取 <技能目录>/SKILL.md」；不改技能正文，不 fork 全仓。
- **维护预算**：一次接入约 0.5–1 天；此后每月约 1–2 小时（盯 release、diff 启用子集、用 retro 把重复坑转成检查）。
- 对应你的需求：③「开局瘦」与④「从失败改进」覆盖最强（`writing-for-agents` 的指针/负载/渐进披露；`retro` 的七类改写候选；`diagnosing-bugs` 强制先建反馈回路）；①有方法论（grilling 决策树、`wayfinder` 决策票、ADR）但 grilling 本身不落盘；⑤在 Pi 无 UI（看板应留在 DSH）。

### 3.2 J-Space（状态/认知层）——建议只借机制，不装

**【事实】上游**：`Tiger3807861189/J-Space-Cognition-Suite`（原 `…-V3.6`），Apache-2.0，2,954★ / 221 forks，Zenodo DOI；**单维护者**（129 commits 中 128 个属同一人）；最后 push 2026-09-14，2 个 open issue 无人回。两代：V3.6 = 9 模块；**SV1 = 13 模块 + 7 参考**（不继承旧版数据）。

**【事实】四个 npm 包是四个独立第三方适配，不是官方发行**：

| 包 | 宿主 | 形态 | 版本/最后发布 | 近 30 天下载 |
|---|---|---|---|---|
| `@tony0721/pi-j-space` | Pi | skill + **逐轮强制注入** extension | 1.1.0 / 08-18 | 37 |
| `pi-v4-jspace` | Pi（DeepSeek V4 专用） | vendor V3.6 + 首请求 payload 重写 + 每 epoch steer | 1.0.0 / 08-18 | 43 |
| `@anonyjcy/dsh-j-space` | DSH | 原生 agent preset | 1.2.6 / **11-18** | 2,108 |
| `@spy2006/dsh-jspace-harness` | DSH | 旧式 preset 安装器 | 0.1.1 / 08-20 | 120 |

**【事实】接入方式**：Pi 侧只能当 Pi package（`package.json` 的 `pi.extensions` + `pi.skills`）；DSH 侧有原生 agent preset（bundle patch 声明 `@deepseek-ai/dsh-agent-preset` row），无需改核心。**GitHub 上的「Anthropic J-Space」论文（Jacobian space / global workspace）是神经科学概念，和这套工程协议同源不同层——论文效能不能当作套件效果保证。**

**【事实】真实外部状态（有，但只是协作式门禁）**：`control.py`（Python stdlib、无网络/子进程、路径安全）维护 `.jspace/control.json`（canonical）+ `.jspace/CONTROL.md`（人读投影）；`check --stage work|ship` 未满足返回 **exit 2**（探针实跑：init 成功、work 阶段输出 `BLOCK: Repository map missing`、exit=2）。但它只校验**结构**（证据文件存在、哈希、覆盖词汇、报告轮次），不校验现实；门禁靠模型自己调用，**没有宿主 hook 兜底**；同一模型既执行又验收。token 实测：静置约 65 token；high 级一次 pulse 输出 46,816 字节（≈11k token），默认每 5 个工具事件/600 秒一次——**「开局瘦」成立，「长任务持续瘦」不成立**。

**【事实】本机兼容坑（实测）**：本机 DSH 0.2.1-rc.3 + Cordis 4.0.5 上，`@anonyjcy/dsh-j-space@1.2.6` 缺 `@deepseek-ai/dsh-tool-office`（0.2.2 线 11-12 才首发）→ 装不干净；`1.2.5` 的 persona 仍含已废弃 `{{cwd}}` → prompt 组装失败（与其 issue #1 一致）；`@spy2006` 的安装器把 preset 复制到 `$DSH_HOME/.agent-presets/`，而本机 DSH 文档已写明该目录不再被读取 → 实际不可用。**若要在 DSH 试，先 pin 升级到 DSH 0.2.2-rc.4 并隔离 profile。** Pi 两个包停在 2026-08-18（Pi 0.84 时代），未声明兼容 Pi 1.x；其使用的 hooks 在 Pi 1.5.2 仍有文档，属「可能能跑、未验证」。

**【建议】**：**不装任何 J-Space 包作为依赖**。值得抄的 3 个机制（约 100 行自建）：
1. **canonical JSON + 人读投影**（`state.json` 机器可读 + `STATE.md` 人读），字段带证据引用；
2. **证据门**（证据文件存在 + sha256 + 覆盖声明，失败非零退出）；
3. **seam 重读纪律**（按信号路由、只读 1–2 个相关模块，而不是每轮全文重读）。

对应需求：①是它最好的部分（文件可复核）；②仍需自建（只验结构不验现实）；③部分满足但周期性 11k token 重读与「注意力省着用」相反；④不满足；⑤负向（per-task 台账与 DSH 看板并立 = 第二套台账）；⑥⑦有参考价值。

### 3.3 LHH（编排/审计层）——建议架构参考 + 一次性验证

**【事实】** `AMAP-ML/LongHorizon-Harness`（组织显示名 DreamX，论文署名 DreamX Team, Alibaba Group），MIT，Python ≥3.10，1,876★ / 196 forks，v0.1.8（2026-10-21），PyPI `lh-harness==0.1.8`（wheel 0.37MB）；arXiv 2608.01964（2026-08-03，HF Daily Papers W32 #1）。12 open issues / 11 open PR，核心维护者 2–3 人；main 上已合并未发布的 MCP server PR。

**【事实】MEA 循环**：Manager 从「原始任务 + 任务态 + 全部审计报告」产出下一子任务契约与路由（execute / done / blocked / ask）；Executor 用 **fresh context** 只执行一个子任务、轨迹丢弃；**只读 Auditor** 独立核验环境（不看 executor 推理），产出三行控制头报告（Status / Integrity / Contract audit）。**只有 auditor 报告能推进任务态**；Manager 声称 done 时，只有最近一次审计为 clean + complete + aligned 才被接受，否则合成 invalid-completion 反馈重来。

**【事实】任务态与账本**：没有 DB/JSON schema——Manager 每轮维护自然语言 `task_state.txt` / `task_contract.txt`；append-only `rounds.jsonl`（ManagedRound 全字段）+ `events.jsonl`（schema_version=1、event_id=`run:seq`、flock+fsync）+ `report.json`；恢复靠重放账本（同轮取最后一条），支持 resume/follow-up。

**【事实】AgentAdapter 与后端**：接口极简（`async run_episode(prompt, env, budget, …) -> EpisodeResult`）；现有后端 = Claude Code、Codex、OpenCode、**DeepSeek Harness（dsh，phase-1 CLI-only：`dsh --profile headless`、隔离 DSH_HOME、executor=workspace-write / Manager+Auditor=read-only）**。**Pi 未被支持**（issue #73 open；维护者欢迎 PR，要求实现 run_episode、规范化流式/退出码/provider 错误、遵守超时取消、保持 executor 与只读 auditor 边界；新增 CLI 后端估算 150–250 行 + 注册/配置/测试）。

**【事实】只读强制按后端衰减**：只有 Claude Code 有「审计前后工作区快照 mutation 守卫」；Codex 用 bypass 参数、无守卫；OpenCode 只记录 role；dsh 靠上游权限模式。代码里 `verifier_workspace_restored` 恒为 False、未见真正回滚实现，但文案会写「已恢复」——**采信任何「自动恢复」说法前必须实测**。另有 **#98（2026-11-18 提交，未修）：快照把 `.git` 算进去，审计窗口内跑 `git status` 会改 `.git/index`，导致任何 git 仓库的审计被误判 violation**——对 coding 场景是直接踩雷。

**【事实】基准**（同 backbone 只换 harness）：WeaveBench 51.8%→80.7%；OSWorld 2.0 Binary 2.8→8.3（3×）；Terminal-Bench 2.1 69.7→77.2 且 token 省 24%；弱模型 token 2.3–3.6×、强模型反而更省。默认 25 轮 × 每轮 3 角色 episode，**不适合 5 秒级小事**。

**【事实】WSL2 可行性**：官方明确原生 Windows 不可用（POSIX 原语），**建议用 WSL2 并在 Linux 内装 harness + agent CLI**；macOS 是唯一已测平台，Linux 未被官方列为已测。纯 CLI coding **不需要桌面/浏览器/computer-use 插件/Docker**；GUI 才需桌面，且 WSLg 不能驱动 Windows 原生应用。

**【建议】**：**不把 LHH 装成 WSL2 第二个 agent**（它是第三层，需要底层 harness）。值得借的机制（约 100–200 行复刻）：
- 只读独立 verifier、不看 executor 轨迹；
- **done 必须引用最近一次 clean+aligned 审计**；
- executor 自述不入账，失败只作证据；
- 按 round id 稀疏注入证据（而不是回翻全部历史）；
- append-only 轮次账本 + 工作区快照 mutation 检测（**记得排除 `.git`**）。
若确实想验证 LHH 本体：只做一次性 1 小时验证——WSL2 内 `uv tool install lh-harness==0.1.8`，`lh-harness doctor`，在 `/tmp` 的非 git 目录用 `--agent deepseek_harness --max-rounds 2` 跑一轮，检查 `runs/<id>/role_orchestration/` 产物；**不作为依赖接入**。

### 3.4 三者关系一览

| 对象 | 层 | 与 Pi 的关系 | 成熟度 | 本报告建议 | 成本 |
|---|---|---|---|---|---|
| mattpocock/skills | 技能层 | Pi package/skill 直接可用（27/27 实测） | 上游活跃规范稳定；Pi 侧需一次性适配 | **采用子集** | 0.5–1 天接入 + 1–2 小时/月 |
| J-Space | 状态/认知层 | Pi package（两个过期适配）；机制可借 | 单维护者、适配过期、兼容坑多 | **不装，借 3 机制** | 自建约 100 行 |
| LHH | 编排/审计层 | 不替 Pi；Pi 需自写 adapter（150–250 行） | v0.x 快速迭代、Pi 未支持、git bug | **架构参考 + 1 小时验证** | 验证约 1 小时；不可依赖 |

---

## 4. 事实之上的关键判断：Pi 到底该站哪

### 4.1 四个候选位置

| 位置 | 形态 | 收益 | 新增维护面/冲突 | 判定 |
|---|---|---|---|---|
| A 平级第二 agent | 你直接开 Pi 干活 | 低 token、树历史、生态大 | 一套新治理/台账/使用习惯；与 DSH 争「记录真源」 | **只做实验沙盒** |
| B **受控 worker** | DSH/脚本用 RPC/CLI 驱动 Pi | worker 是一等公民；隔离干净；省 token；可独立核验 | 薄 adapter；并发写需隔离；模型额度共用 | **推荐** |
| C Pi 当 Orchestrator | Pi 派 agent/子任务 | 树历史 + hooks 可做门禁 | 需装第三方 subagent 包（=第三套任务板/审批/看板）；与「唯一决策枢纽」「维护预算」正面冲突 | **暂不采用**；若长期要做，等 Pi Durable 稳定 |
| D LHH 当外层 | LHH 编排 agent 跑长任务 | 现成 MEA/看板/恢复；原生支持 dsh 后端 | 第三层进程 + 每角色一份 agent CLI/凭证；Pi 未支持；git 审计 bug | **只做一次性验证/借架构** |

### 4.2 位置校准结论

**【建议】推荐 B：DSH 管控制面，Pi 管执行面。**

```
用户（唯一决策枢纽）
   │ 决策 / 验收 / 升级
   ▼
DSH SuperAgent（控制面：工单、授权、外部锚、统一看板、完成判定）
   │ RPC / CLI（单任务单目录）          ▲ 读证据（只读）
   ▼                                  │
Pi worker（fresh context，树状会话）──► 受控工作目录 + state.json / 证据账本
   │                                  ▲
   └──────── 独立验证器（脚本/另一会话）┘
```

理由：① Pi 的 worker 位是官方一等公民（RPC 33 命令 + 事件流），集成成本最低；② 控制面已经在 DSH 里且成熟，不重复建设；③ 树历史/hooks/skills 这些 Pi 强项在 worker 位全部用得上；④ 把「多一套台账」限制在 Pi 的本地会话里，项目状态与看板仍归 DSH。

### 4.3 对五条张力的正面回答（不迎合）

| 张力 | 正面回答 |
|---|---|
| 完整链路 vs 维护预算 | 只加**一层** Pi worker，不再新建编排层。控制面、看板、验收留在 DSH；Pi 侧只允许「技能文本 + 一个约 100 行的状态/门禁」。凡是要再建任务板/审批/看板的方案（Pi orchestration、LHH 全量）一律不做。 |
| 改进回路需要验证器 | Pi 的钩子只能**承接**验证结果，不能生产验证器。验证器必须是外部独立进程（脚本优先，或另一会话/模型），并借鉴 LHH 的 Auditor 结构。「验证器稀缺」不因引入 Pi 而缓解，必须当作项目资产单独立项。 |
| 借鉴外部成果 vs 版本不稳/无权限隔离 | 三条规则：**pin 版本**（Pi 1.5.2、skills v1.3.2、LH_H 不装）；**只从官方/高下载量来源装**；**隔离 profile/目录**。Pi 扩展是任意代码、与主进程同权限——在本机「同账号无边界」环境下，装第三方 Pi 包 ≈ 裸跑不可信代码。 |
| 结构化 vs 填表摩擦 | 用 grilling 只收敛「决策」，不产出大表；状态文件只保留 5 个字段（goal / next / verified / open / evidence）；拒绝为框架而框架。 |
| ADR 在先 vs 事后追认 | 项目一开始就写 `ADR-0001`（为什么 Pi 取 worker 位、不取 orchestrator 位），之后每个实验阶段先写决策再动手；会话树只挂证据，不承担「理由」。 |

### 4.4 与 DSH 并存的冲突面与分工（必须提前定死）

| 维度 | 结论 | 规则 |
|---|---|---|
| 授权/工单/外部锚/看板/完成判定 | 归 DSH | Pi 不建第二套；Pi 的产出以文件/报告交给 DSH |
| 执行/树历史/技能实验 | 归 Pi | 单任务单会话、fresh context；会话文件留在 Pi 本地 |
| 项目状态真源 | 归项目目录（`state.json` + 决策文件） | Pi 会话不是真源；树历史只是回滚/调试工具 |
| 模型凭据/额度 | 可共用 `DEEPSEEK_API_KEY` | 需单独记账；Pi 用哪档模型要显式配置（默认不要用最贵档） |
| 同一仓库并发写 | 冲突 | **每个 worker 用独立 worktree/目录**；同一时刻单 writer |
| 端口 | 无冲突 | Pi CLI 默认不监听；不要装会开服务的扩展（pi-server 等） |
| 插件格式 | 不通用 | Pi 扩展 ≠ DSH 插件；技能文本（SKILL.md）可共享，但需各自安装 |

---

## 5. 分层选型建议（汇总）

| 层 | 结论 | 理由 | 最小验证 |
|---|---|---|---|
| Pi 运行时（worker/沙盒） | **采用** | WSL2 实测可跑、成本低；RPC/SDK 一等公民；与 DSH 无硬冲突 | P0 已过；P3 三任务对照 |
| Pi 作为 Orchestrator | **暂不采用** | 需第三方 subagent 包 = 第三套任务板；撞维护预算 | — |
| Pi Durable（实验包） | **观察** | 任务图/崩溃恢复/exactly-once 最贴近「可信自主性」，但 API 标 experimental | 不纳入本轮 |
| mattSkill（技能层） | **采用子集** | 零改动可加载；覆盖需求③④；接入成本近零 | P1（grilling/tdd 验收） |
| J-Space（状态/认知层） | **只借机制** | 适配过期/单维护者/第二台账/长任务 token 重读 | P2 自建对照 |
| LHH（编排/审计层） | **架构参考 + 一次性验证** | 需求②最佳参考；Pi 未支持；git 审计 bug | P4 1 小时 dsh 后端验证 |
| 统一看板/决策账本 | **留在 DSH + 项目目录** | 避免第二套台账；DSH 已有 ticket/panel | 随 P1–P3 |

---

## 6. 最小实验方案（WIP=1，先写 ADR 再动手）

### P0 可行性探针（**已完成**，2026-11-18）

- 动作：隔离安装 Pi 1.5.2；`--version/--help`；无 key RPC 握手；TS 扩展加载；DeepSeek 模型目录（假 key）。
- 验收（机械化）：① 未触碰 `/root/.pi`、`/root/.dsh`、3082；② 探针目录可整体删除；③ 命令与输出有日志；④ 未使用共享凭据。
- 结果：**PASS**（见 §2.3 与附录 B）。

### P1 技能层（0.5–1 天）

- 动作：钉 `mattpocock/skills` v1.3.2 → 安装到用户级 `~/.agents/skills/`（Pi 免信任）；启用子集 6–8 个；一次性把启用文件里的「Call the Skill tool」改成「读取 SKILL.md」；写 5 行 `AGENTS.md` 指路。
- 两个测试任务：① 一个真实小任务（有明确完成判据，如修一个文案 + 跑检查）；② 一个小决策（用 `grilling` 走 2–3 轮）。
- 验收：a) RPC `get_commands` 出现启用技能的 `skill:*`；b) grilling 满足官方 "It's working if"（整轮编号 + 推荐答案、同轮互不依赖、事实自查、结束前停下等确认）；c) tdd 先声明接缝、一次一个红→绿切片（在临时仓库）；d) 同任务有/无技能 token 增量 **< 30%**；e) 不写到实验目录之外。
- 判据/回滚：4 条中 ≥3 条通过则保留子集；否则砍到 3 个（grilling / writing-for-agents / tdd）。

### P2 状态/门禁层（1–2 天，可与 P1 串行）

- 动作（自建约 100 行，借鉴 J-Space + LHH）：`state.json`（goal / next / verified[] / open[] / evidence[] 带 sha256）；`gate.py`（证据存在 + 哈希 + 覆盖声明，失败 exit 2）；Pi 扩展钩子（`tool_call` 在未过 gate 时阻断提交类动作、`agent_before_settle` 要求 gate 通过才允许结束）。
- 验收：a) 预埋 2 个「编造完成」用例，gate 必须抓到（2/2）；b) 正常任务开销 < 10%；c) compaction 之后 state 仍可读、不丢证据引用；d) 代码量 ≤ 200 行；超过即停止并重估（防「搭三天框架」）。
- 判据/回滚：a+b 通过则保留；任一失败则退回「只写 state.json、不接钩子」。

### P3 worker 位（1–2 天）

- 动作：在 SuperAgent 或脚本里写薄驱动：spawn `pi --mode rpc`，发任务上下文 + 工作目录，收集事件；要求产物 + gate 通过；独立验证器（另一 fresh 会话或确定性脚本，只读）核验后交回 DSH。用 3 个真实小任务，与 DSH worker 同任务对照。
- 验收：a) 3 个任务全部有产物与独立核验记录；b) **未验证结论 0 条**（executor 自述不算）；c) 记录 token/时延/人工介入次数；d) Pi worker 在 3 个任务中 ≥2 个不劣于 DSH worker（质量 + 成本综合），否则停止长期使用。
- 判据/回滚：任一失败即回滚到 P2 末端，Pi 只留实验沙盒。

### P4 可选：LHH 一次性验证（约 1 小时）

- 动作：`uv tool install lh-harness==0.1.8` → `lh-harness doctor` → `/tmp` 非 git 目录 `--agent deepseek_harness --max-rounds 2`；检查 `role_orchestration/{rounds.jsonl,rounds/round_001,task_state.txt,auditor_report.txt,report.json}`。
- 验收：链路真实跑通（或如实记录卡点）；只做一次性，不写入任何长期依赖。
- 判据：能跑通 → 记「可作长任务外循环候选，观察 v0.1.9 与 #98」；跑不通 → 记「暂不采用」，不影响 P1–P3。

### 实验纪律

- **WIP=1**：同一时间只开一个阶段；每阶段先写 ADR（决策、前提、预期、回滚）。
- **真源**：产物与证据落文件；会话历史只作证据/回滚。
- **机械验收优先**：能用脚本判的不用人判；不能脚本判的写清人工判据。
- **失败即记录**：失败轮次与原因入账，不重试到成功为止。

---

## 7. 风险与限制

### 7.1 主要风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| Pi 版本节奏快 | 1.0→1.5.2 六周 5 个 minor；扩展 API 可能变 | 钉 1.5.2；升级前 diff 变更日志；扩展只留最小集 |
| 无权限边界 + 第三方代码 | Pi 扩展是任意代码、同账号同权限；装第三方包 ≈ 裸跑不可信代码 | 只装官方/高下载固定版本；隔离 profile；不装会开服务的扩展；除自建门禁脚本外不引入自动化 |
| 第二套台账 | Pi 会话树 + J-Space `.jspace/` + DSH 记录容易三套 | 状态真源只留「项目目录 state.json + DSH 工单」；Pi 会话本地；不装 J-Space |
| 验证器稀缺 | Pi 钩子不生产验证器 | P2 门禁 + P3 独立验证器；借 LHH Auditor 结构；验证器单独立项 |
| token 开销 | J-Space pulse ≈11k token/次；LHH 弱模型 2.3–3.6× | 不装 J-Space；LHH 只做一次性；Pi 默认用省 token 的最小配置 |
| LHH 维护与缺陷 | v0.x、Pi 未支持、git 审计 bug #98、restore 文案与实现不一致 | 不作依赖；只做一次性验证；借结构不借代码 |
| 并发写同一仓库 | 两个 harness 同时写会互相踩 | 每个 worker 独立 worktree/目录；单 writer 规则 |
| 模型额度共用 | 与 DSH 共用 key 时成本混在一起 | 单独记账；Pi 默认模型选低档 |

### 7.2 限制（本次未做的事）

- 未做**真实模型调用**（Pi 与 J-Space 探针均为无 key/假 key）；
- 未安装/运行 **LHH 本体**、未验证 Pi↔DSH 的 ACP/端到端；
- 未验证 **Pi Durable**、`pi-subagents` 后台 runner；
- 未做 Pi 单进程内存占用、TUI 交互、curl 安装器测试；
- J-Space 的 DSH 侧兼容结论基于 0.2.1-rc.3 实测，未升级 DSH 复验。

### 7.3 需要复核的项

- Pi `tool_call` 门禁在真实模型下的阻断行为（探针只验证扩展被发现与事件触发）；
- mattSkill 10 个「Skill tool」引用适配后的行为是否一致；
- `.git` 快照误报修复前，任何 git 仓库的 audit 都不可采信（LHH）；
- DSH 0.2.2-rc.4 下 `@anonyjcy/dsh-j-space` 的实际可用性（如要走 DSH 侧试验）。

---

## 8. 需要你拍板的决策项

1. **模型通道与预算**：Pi 用 DSH 现有 DeepSeek key 共用，还是单开？有没有每日/每实验的 token 上限？（【建议】先单开一个实验用 key，记账，避免污染生产额度。）
2. **Pi 可写的目录**：只允许专用实验目录/独立 worktree，还是允许直接改 `D:\AgentWork` 主树？（【建议】只允许专用 worktree，禁主树。）
3. **实验范围与 WIP**：是否按 P1→P2→P3 走（约 2.5–5 人日，分段可停）？P4 是否要做？（【建议】先 P1+P2，P3 看 P2 结果再定。）
4. **第三方包策略**：是否只允许官方/高下载/固定版本？是否接受「无沙箱、扩展同权限」的风险？（【建议】是；先不装任何非官方 Pi 扩展。）
5. **成功判据**：P3 里 Pi worker 要以什么指标不劣于 DSH worker 才继续长期使用？（【建议】3 个真实小任务、0 条未验证结论、综合成本不高于 DSH worker 的 120%。）
6. **长期定位**：实验结束后 Pi 留作长期第二 agent，还是验证完即删？（这决定要不要投入 P2 的状态/门禁自建。）

---

## 9. 项目落地建议（把「新项目」落到你的体系里）

若你决定开这个项目，建议按你现有的项目结构落最小骨架（不新建框架）：

- 项目名：`PI-Agent-试验`（或 `pi-agent-second-agent`）；
- 项目页：①目标（一句话）②判据（§6 各阶段验收）③WIP 上限=1 ④真源（`state.json` + DSH 工单）⑤回滚（每阶段可退）；
- 三个 unit（对应 P1/P2/P3），每个 unit 只写完成锚，不写计划正文；
- `ADR-0001`：**为什么 Pi 取 worker 位、不取 orchestrator 位**（本报告 §4 的判据 + 你的约束）；
- 看板：继续用 DSH 工单/面板，**不为 Pi 另建看板**；
- 记录：实验日志落项目目录，不靠回翻对话。

---

## 附录 A：关键证据与版本清单

| 对象 | 版本/日期（2026-11-18） | 来源 |
|---|---|---|
| Pi CLI | 1.5.2（2026-11-10），MIT，Node ≥22.19 | npm `@earendil-works/pi-coding-agent`；pi.dev；docs.pi.dev |
| Pi 文档 | RPC / RPC Commands / SDK / Extensions / Skills / Packages / Session Format / Security / Windows / NVIDIA | docs.pi.dev/latest/* |
| Pi 探针 | 安装 12s/160MB/123 包；help 322ms；RPC 0.27s；未真实调用 | 本工单工作区 `research/probe-pi/log.md`（不随 PR 提交） |
| DSH | 0.2.1-rc.3；vendor `pi-ai@1.4.0`（`dsh-llm-pi-ai`） | 本机 `/usr/local/lib/node_modules/@deepseek-ai/dsh` |
| mattpocock/skills | v1.3.2（2026-10-29），MIT，327,073★，27 技能 | github.com/mattpocock/skills；Pi 探针 `get_commands` 实测 27/27 |
| DSH MattSkills Deck | `dsh-mattpocock-skills-deck@1.9.0-beta.33`（2026-11-01），382★，约 16,989 下载/30 天 | npm；/tmp/plugins.json 快照 |
| J-Space 上游 | Apache-2.0，2,954★，单维护者，最后 push 2026-09-14；V3.6=9 模块 / SV1=13 模块 | github.com/Tiger3807861189/J-Space-Cognition-Suite |
| J-Space 适配 | `@tony0721/pi-j-space@1.1.0`、`pi-v4-jspace@1.0.0`、`@anonyjcy/dsh-j-space@1.2.6`、`@spy2006/dsh-jspace-harness@0.1.1` | npm registry |
| LHH | v0.1.8（2026-10-21），MIT，1,876★；arXiv 2608.01964 | github.com/AMAP-ML/LongHorizon-Harness；arXiv；PyPI `lh-harness` |
| LHH 关键 issue | #73（Pi 支持，open）、#98（git 审计误报，open）、#70（Windows/WSL2）、#1（验证漂移） | GitHub |

## 附录 B：P0 探针命令摘要（可复现）

```bash
# 隔离前缀安装（不写系统目录）
npm install --prefix research/probe-pi/npm --ignore-scripts --no-audit --no-fund \
  @earendil-works/pi-coding-agent@1.5.2

# 隔离配置 + 无 key 冒烟
export HOME=$PWD/research/probe-pi/home XDG_CONFIG_HOME=$HOME/.config \
       PI_CODING_AGENT_DIR=$HOME/pi-agent TMPDIR=$PWD/research/probe-pi/tmp
PI=$PWD/research/probe-pi/npm/node_modules/.bin/pi
$PI --version            # 1.5.2
$PI --help               # 322ms
$PI --mode rpc --no-session --offline      # get_state → 0.27s，exit 0

# DeepSeek 模型目录（假 key，无真实请求）
DEEPSEEK_API_KEY=dummy $PI --offline --list-models deepseek
# deepseek-flash / deepseek-v4-pro（1M ctx / 384K out）
```

## 附录 C：术语表

| 术语 | 含义 |
|---|---|
| harness | 模型之外的一层执行环境：loop、工具、上下文、权限、会话 |
| worker / Orchestrator | 执行单任务的 agent 会话 / 拆任务、派 worker、收结果的编排者 |
| 树状历史 | 会话以树保存，可从任意节点分叉/回滚（Pi 的 `/tree`） |
| hook / 扩展事件 | harness 暴露给扩展的生命周期拦截点（Pi 的 `tool_call` 等） |
| skill | 按需加载的指令包（`SKILL.md` + 附件，Agent Skills 规范） |
| compaction | 上下文接近上限时把旧消息压成摘要 |
| MEA | Manager-Execute-Audit：维护任务态、执行、独立审计的循环（LHH） |
| 门禁（gate） | 未满足客观证据就拒绝完成/提交的机械检查 |
| ledger | 只追加的轮次/事件账本 |
| WIP=1 | 同一时间只推进一条实验线 |
