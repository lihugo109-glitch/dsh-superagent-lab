# 补答：Plan mode、可视化、基础 harness 与三组件在 DSH 上的表现

> 接 `docs/pi-agent-as-second-agent.md`（PI Agent 选型调研），本文回答 2026-11-18 的追加追问（8 问 + 1 条三路追问）。调研环境：本机 DSH 0.2.1-rc.3、SuperAgent profile（127.0.0.1:3082 运行中）、原型源码 `/root/work/dsh-superagent-prototype`。标注约定：**【事实】** 有代码/文档/实测出处；**【推断】** 依证据的判断；**【建议】** 可执行选项。

## 0. 结论先行（逐问回答）

1. **Plan mode 为什么「几乎不可用」**：不是 DSH 没有能力，而是 SuperAgent 的设计选择 + 实现缺口。DSH 的 `plan-mode` 与 `ui-plan` 都在（普通 standard 会话开箱可用）；SuperAgent 把 plan mode 从 **worker/router 两个 Agent 预设里刻意排除**，工具白名单还过滤掉 `exit_plan_mode`/`ask_user_question`，且 worker 无人值守、没有客户端能弹计划评审——三层一起挡住。【事实】/【推断】
2. **「设计禁止我用 DSH 界面」不完全成立**：DSH Web UI 里的 Superagent 面板本来就是官方定义的**监督面**（docs/005 第一句），工单详情有 **Open Session** 深链，docs/003 甚至允许人直接往 Executor 会话里写消息。真实限制是：**答复/计划评审被要求回到源线程（IM/GitHub），而面板没有答复/评审入口**——这是设计取向 + 实现缺口，不是平台政策。【事实】
3. **可视化困难的根因**：现有面板是「管理/审计视角」（按 Source→Trigger→Eval→Ticket 领域对象分区，术语重），DSH 原生 Trajectory 是「单会话调试视角」；缺的是「今天需要我拍板什么 / 正在跑什么 / 卡在哪 / 下一步等谁」的工作节拍叙事，以及面板内的答复入口。【事实】/【推断】
4. **GitHub 是否可以扔掉**：setup 层与「PR 合并/关闭」外部锚目前是 GitHub 专属、结构性必需；但**日常交互可以 100% 走飞书，0 代码**（GitHub 只当归档/合并锚，允许名单清空、receive-all 关、提示词改成「推分支 + 报告 + 验证证据」）。彻底去 GitHub 需改 Setup/Deployment/github-watch/完成判定，估 **300–600 LOC / 3–6 人日**，并会失去 PR/review/CI 这个可独立验证的完成锚——**不建议现在做**。【事实】/【建议】
5. **Orchestrator 不是门牌**：它是唯一的授权/裁定/完成判定点（只有它能建工单、stop、attach）和所有 worker 汇报/提问的中转；用户感到的「沉重」主要来自完整领域词汇 + GitHub 管理面 + 面板按对象分区。单人低频场景可以用 **explicit-only 配置**把 Eval/准入的日常负担降到接近零（保留代码，改配置 + 文案 + 面板首页）。【事实】/【建议】
6. **J-Space 的作用（明确回答）**：它是「**推理时认知控制协议 + 可选本地账本**」——把长任务的约束与状态从对话历史里抽出来、外化成可读文件（`.jspace/control.json` + `CONTROL.md`），在压缩/换轮次后重新提醒模型。**它不验证现实、不提供看板、不是 harness 功能**；只校验结构、靠模型自觉，且与 DSH 看板并立会成为第二套台账。→ 只借 3 个机制，不装。【事实】/【建议】
7. **LHH 能用哪些 Agent**：Claude Code、Codex CLI、OpenCode、**DeepSeek Harness（phase-1 CLI-only）**；论文期还有 OpenClaw/Hermes（只在冻结的 eval 副本里，当前代码没有）；自定义 `AgentAdapter` 可加新后端（单方法 Protocol，CLI 后端约 150–250 行）；**Pi 未支持**（issue #73 open）。【事实】
8. **MattSkill / J-Space / LHH 装在 DSH 上的表现**：mattSkill 近乎原生（+~0.75k token/会话目录，按需载正文）→ **装子集**；J-Space 在本机 0.2.1-rc.3 两代都装不干净（要升 0.2.2-rc.4 + 改 profile + 重启），pulse 周期 ~10k token，且是第二台账 → **不装，只借机制**；LHH 是外层编排器（DSH 只是它的 Executor，`dsh --profile headless`，每轮 3 角色、默认最多 25 轮），benchmark 用 Claude Code 后端、不能归因 DSH，且有 git 审计 bug #98 → **不装，只借 MEA 机制**。详见 §5 表。【事实】/【建议】
9. **Pi vs DSH 作为基础 harness**：你听到的「DSH 耗时/token 最差」在公开 benchmark 里**没有找到可支持该说法的证据**（含 DSH 的 benchmark 极少；LHH 图与 Composio 30× 实验都不含 DSH）【见 §6】。本机可测的是「固定 harness 税」：Pi 默认（4 工具）固定前缀约 4.6K–5.4K 字符 ≈1.2–1.9K token；本机 SuperAgent worker 固定前缀约 63K–71K 字符 ≈**1.7–2.0 万 token**（orchestrator ≈1.9–2.2 万），**约 10–15 倍**；只算 system prompt 则 34K–42K vs 1,766 字符。这是"用 token 买治理"（含团队策略/技能段），且 DeepSeek 官方评测用的是 Minimal 薄模式——不能直接当"DSH 最差"的证据。要下结论需一次同模型同任务的 A/B 测（§6 给方案）。Pi 的缺项确实可用插件补（subagents、MCP、上下文压缩、Web UI 等），但每个插件都是新的版本面。【事实】/【推断】
10. **SuperAgent 能改吗 / 自行改造 / 社区替代**：上游是研究原型（MIT、单提交、无 issue/PR/路线承诺，社区 fork 是实际演化面）→ 等上游不是现实路径；**自行改造可行**：先 `git init` 固化基线（0.1 人日）、0 代码双轨试点（0.5–1 人日）、计划工件 + Attention 确认（0 代码）、只读工作看板（本 PR 已附 PoC `tools/superagent-dashboard.py`，0.5–1 人日收尾）、YAML 补 plan 评审（1–2 人日）；面板节拍化要 3–5 人日、源码级去 GitHub 要 3–6 人日。**社区替代**里只有你已在维护的 Hermes 同形态，但换实现会把维护债翻倍（详见 §7）。【推断】/【建议】

一句话建议：**先不动架构，用 0 代码/半天成本把「可视化 + 计划确认 + 飞书优先」补上；GitHub 降级为归档与合并锚；Pi 作为 worker/实验沙盒，J-Space/LHH 只借机制。** 这是与你「低注意力、少不便、轻维护」约束冲突最小的路径。

---

## 1. Plan mode：DSH 有能力，SuperAgent 刻意关掉

### 1.1 事实链

- **DSH 侧完整**：`@deepseek-ai/dsh-plan-mode` 提供 per-agent 计划态、`/plan` 命令、`exit_plan_mode` 工具、指导段与 projection；`dsh-client-ui-plan` 提供输入框 Plan 芯片、计划卡片与右侧栏全文评审。`dsh --profile superagent --dump-config` 里 `plan-mode`（第 277 行）与 `ui-plan`（第 690 行）都存在；`standard`/`ptc` 预设内部挂了 `planning` 组，**普通 standard 会话开箱可用 plan mode**。【事实】
- **SuperAgent 侧三层挡住**：
  1) worker/router 预设**刻意排除** plan mode 与问人工具（`cordis.patch.yml:16,123` 注释明写「Left out: … plan mode」；docs/004:63「Executors work unattended」）；
  2) 即使装回，`WORK_TOOLS` 白名单会过滤 `exit_plan_mode` / `ask_user_question`（`src/app/sessions.ts:61-63,287-293`）；
  3) `exit_plan_mode` 的评审必须有 `userQuestions` 客户端；worker 无人值守、没有客户端弹窗 → 工单会无限挂起（未评审计划时的错误行为：停在 plan mode 等人手动切模式）。【事实】
- **为什么这样设计**：worker 只对 Router 汇报、不直接与人交互；人多信道（IM/GitHub/邮件）异步答复；计划评审在"人写消息的那条线程"完成——docs/005/004/002。**这是取向，不是平台限制**；docs/003:41 允许人直接写 Executor Session。【事实】

### 1.2 三条可落地路径

| 路径 | 做法 | 成本 | 风险/缺点 |
|---|---|---|---|
| **P-1 人类计划桌（先做）** | 在 superagent profile 里开一个普通 standard 会话（不经工单），用它跑 DSH plan mode 做规划；定稿计划再作为飞书请求/工件提交 | **0 代码** | 规划与执行是两处；计划不自动进工单账本 |
| **P0 计划即工件（推荐日常）** | 提示词要求 worker 先写 `PLAN.md`（目标/范围/步骤/验证/风险）+ `orchestrator_report(waiting, human_action="请审批计划")`；你在飞书/面板回「批准」，worker 被该消息恢复后执行；机械门禁=「PLAN.md 存在 + 批准标记存在」 | 改团队提示词（分钟级） | 靠模型遵守文件格式，没有强制 UI 评审；弱门禁 |
| **P1 结构化计划卡（第二阶段）** | 计划作为工单工件落盘/落库，面板加"计划"区 + 批准/退回按钮（需要面板答复 API `POST tickets/:id/answer`）；`ready` 前校验已批准 | **2–4 人日**（改 SuperAgent 应用层） | 新增状态与接口要维护；需要你愿意维护 fork |
| P2 硬启用 plan mode（不建议） | 把 `planning` 组塞进 worker 预设 + 放开工具白名单 + 面板深链到 worker 会话人工评审 | 配置小，但维护 fork | 与"worker 无人值守"设计冲突、审批不落到工单域、升级易碎 |

**【建议】** 今天就做 P-1（想认真规划时）+ P0（日常工单）；若确认计划评审要变成日常，再做 P1。**不建议**为了 plan mode 去动 SuperAgent 的 worker 预设。

---

## 2. 可视化：现有面板是「审计台」，不是「工作驾驶舱」

### 2.1 现有可视化资产（不少，但视角不对）

- **Superagent 面板**（DSH Web 侧栏）：六个 tab（Overview/Source/Trigger/Eval/Execution/Settings），有「待回答/待评审/阻塞/工作中」阶段标签、24h 计数、执行器负载；工单详情有 **Open Session** 按钮跳进 worker 会话；Attention 横幅给「去源线程回答」链接。→ 能回答「是否需要我/系统健康/历史」，但按领域对象分区、术语重。【事实】
- **DSH 原生视图**：会话列表、Chat + **Trajectory**（turn-aware 事件账本、工具/Token/耗时、可检索）、deliverables 卡片、jobs/goal/schedule。→ 单会话调试视角，不跨工单。【事实】
- **缺什么**：①「今天需要我拍板/正在跑/卡住/最近交付」四块总览；②跨工单叙事时间线；③面板内答复/计划评审入口；④列表行深链；⑤"为什么卡住 + 建议"结构化原因。【事实】

### 2.2 可视化方案对比（改动量从小到大）

| # | 方案 | 能看到什么 | 成本/风险 | 是否改 SuperAgent 设计 |
|---|---|---|---|---|
| 0 | 现有面板 + DSH 原生 Trajectory | 待人工、健康、历史、阶段、Open Session、轨迹/工具/耗时 | 0 | 否 |
| **1** | **静态单文件 HTML dashboard（本 PR 已附 PoC）** | 需要你/进行中/长期未动/最近结束/最近事件；只读、可本地打开、可邮件 | 半天（已实现 ~290 行，见 `tools/superagent-dashboard.py`） | 否（纯读者） |
| 2 | `dsh-superagent-trace` 插件（市场 0.1.1/MIT，578 下载/0★） | 来源→事件→工单泳道时序、工具/汇报/提问箭头，事后回看 | 装插件+重启 profile；能力标签与"只读"声明矛盾，**装前必须审码** | 否 |
| 3 | 通用看板插件（`dsh-super-kanban` 126★、`dsh-kanban-flow`、`dsh-team-kanban`、`dsh-decisions-board`） | 任务卡/泳道/待拍板/收件箱 | 中–高；都不读 SuperAgent 工单模型，需二次开发；部分会成第二套台账 | 是（适配层） |
| 4 | 面板节拍化改造 | 今日四块 + 时间线 + 面板内答复 API + 计划卡 + 全列表深链 | 1–3 人日；需维护 fork | 是（应用层，不动核心） |
| 5 | LHH workbench（React/FastAPI，127.0.0.1:8799） | run 级 Plan/Execution/Audit/Rework 四栏、审批、运行中注入 | 高：第三套进程/角色/凭证、只到 run 级、需 LHH 在跑 | 是（引入新控制面，不推荐） |
| 6 | Pi 社区 Web UI（`agegr/pi-web` 8.3k★ 等） | Pi 会话工作区（项目分组、running/cost、worktree） | 面向 Pi 单会话，无工单/多 Agent 节拍；不能直接用 | 仅借鉴 |

### 2.3 推荐：0 + 1 立即，2/4 第二阶段，5/6 不做

- **立即（本次交付）**：`tools/superagent-dashboard.py`（只读 `orchestrator.sqlite`）已生成单文件看板，四块 + 最近事件；可 `--demo` 生成演示、可邮件发送、可在本地浏览器打开。运行：
  `python3 tools/superagent-dashboard.py --db /root/work/state/orchestrator.sqlite --out ~/superagent-dashboard.html`
- **第二阶段（可选）**：需要"实时 + 可操作"时，做面板节拍化（今日四块 + 时间线 + 答复 API + 计划卡，1–3 人日）；想回看审计轨迹可审码后装 `dsh-superagent-trace`。
- **不建议**：为可视化引入 LHH workbench 或 harness-one 画布——第三套控制面/台账，与维护预算冲突。

---

## 3. J-Space 的作用（明确回答）

**一句话：J-Space 是「推理时认知控制协议 + 可选本地账本」，不是 harness 功能，也不负责验证与可视化。**

| 层 | 它做什么 | 不做什么 |
|---|---|---|
| 提示词/技能层（13 模块路由） | 按任务信号加载 1–2 个"认知模块"（broadcast/capacity/deep-reasoning/epistemics/…），把约束、失败检查、外部状态提醒注入上下文；Pi 版每轮强制注入 ~300 token，DSH 版按需加载 | 不改变模型能力、不保证效果；自报 benchmark 标注 "Estimated, based on limited controlled experiments"，适配作者明确"未复现收益" |
| 控制器层（`control.py`） | 维护 `.jspace/control.json`（goal/next/core≤2/checkpoints+证据路径/open Q）+ `CONTROL.md` 人读投影；`check --stage work|ship` 未过 exit 2 | 只校验结构（证据在不在、哈希、覆盖词），**不校验现实**；门禁靠模型自觉调用，无宿主强制；per-task 台账会与统一看板并立 |
| 叙事层（Global Workspace 隐喻） | 解释"为什么这样设计" | 论文（神经科学 J-Space）与工程套件同源不同层，论文效能不能当套件效果保证 |

**与你的需求映射**：需求①（决策可追溯）是它最好的部分（文件可复核）；需求③开局瘦成立、但长任务周期性 ~10k token 重读与"注意力省着用"相反；需求②执行/验证分离**它解决不了**（同模型既执行又验收）；需求⑤看板是负向（第二套台账）。→ **只借 3 个机制**：canonical JSON + 人读投影、证据门（证据存在+sha256+覆盖声明+非零退出）、seam 重读纪律；约 100 行自建。

---

## 4. LHH 能用哪些 Agent、装到 DSH 上是什么样

### 4.1 支持的后端（当前代码）

| 后端 | 状态 | 只读审计的强制力 |
|---|---|---|
| Claude Code | 完整支持 | **有**：deny 写工具 + 审计前后工作区快照 diff（最强） |
| Codex CLI | 支持 | 无快照守卫，靠 prompt + bypass 参数 |
| OpenCode | 支持 | role 只记录不强制（`--yolo`） |
| **DeepSeek Harness（dsh）** | **phase-1 CLI-only**：`dsh --profile headless --patch`，隔离 `DSH_HOME`，按角色设置 read-only/workspace-write | 无快照守卫；上游权限模式 |
| OpenClaw / Hermes | 论文期支持，**当前代码没有**（只在 `eval/` 冻结副本） | — |
| 自定义 AgentAdapter | 接口只有 `run_episode` 单方法；CLI 后端约 150–250 行 + 注册/配置/测试 | 需自补守卫 |
| **Pi** | **未支持**（issue #73 open；维护者欢迎 PR，无现成实现） | — |

### 4.2 装到 DSH 上的真实表现

- **形态**：LHH 是外层 Python 编排器，DSH 只是它的 Executor 后端——**装 LHH ≠ 装进 DSH**。
- **成本**：每轮 = Manager→Executor→Auditor 3 个独立 `dsh --profile headless` 进程（各自 fresh context、工具表、权限），默认 `max_rounds=25` → 最多 **75 次 DSH 冷启动/run**；超时上限 300s+1800s+300s ≈ 40 分钟/轮，理论最坏 ~16.7 小时/run。
- **可观测性**：headless 只把最终答案写回 stdout，**中间工具事件不进 trajectory**，Auditor 只能看最终产物；LHH 自己的 `rounds.jsonl`/`events.jsonl` 账本记录的是角色层信息。
- **benchmark 归属**：论文/图表的提升是 LHH 循环 vs 其他 harness（Claude Code/Codex/OpenClaw/Hermes），**不是 DSH 的表现**；不要用 LHH 的 token 倍数评价 DSH。
- **缺陷**：#98（审计快照把 `.git` 算进去 → 任何 git 仓库审计被误判 violation，11-18 提交、未修）；`verifier_workspace_restored` 恒 False，但文案写「已恢复」；默认 25 轮 × 多角色对"5 秒级小事"过重。

### 4.3 LHH 的可视化能借什么

它的 Web workbench（React/FastAPI，`lh-harness web`，默认 127.0.0.1:8799）有 run 级 **Plan/Execution/Audit/Rework 四栏 + 审批 + 运行中注入/停止**——这个"轮次 + 证据"的视图值得借鉴，但**不能当 SuperAgent 看板**（只显示 LHH 自己的 run，不接 SuperAgent 工单，需第三套进程/凭证）。→ 借"四栏 + 证据链"的信息结构，做进我们自己的静态 dashboard/面板，而不是引入 LHH。

---

## 5. MattSkill / J-Space / LHH 装到 DSH 上的表现（对比）

| 维度 | mattSkill 纯技能子集 | mattSkill Deck | J-Space preset | LHH 外层编排 |
|---|---|---|---|---|
| 装到 DSH 的形态 | 磁盘技能（`SKILL.md`，DSH 原生 skill 工具） | DSH 插件（含面板 + 12 个 deck_* 工具 + 27 技能） | 原生 agent preset（bundle patch 声明） | 不装进 DSH；DSH 作为其 Executor 后端 |
| 安装条件 | 拷 5–8 个目录到 `~/.dsh/skills/`，pin v1.3.2 | 装 npm 包 + 重启；beta（88 版/2.5 月、62 open issues） | **本机装不干净**：1.2.6 需 `dsh-tool-office`（0.2.2 线）、1.2.5 用废弃 `{{cwd}}`；干净路径=升 DSH 0.2.2-rc.4 + 改 profile + 重启 3082 | `uv tool install lh-harness==0.1.8` + 配置 DSH 后端（0.5 天） |
| 每轮固定开销 | 目录 +~0.75k token（仅 11 个模型可见技能）；正文按需 1–3k/个 | +目录 0.75k + 12 工具 schema 推断 +2–3k token/轮 | 目录 65–72；SKILL 加载 3.4k；high 级 pulse 9.5–11.7k/每 5 工具事件或 600s | 每轮 3 进程，≥3×；最多 75 次冷启动/run；论文 token 倍数 2.3–3.6×（弱模型） |
| 可视化产出 | 无（技能文本） | 面板：wayfinder 地图/issue/triage/多并发 | `.jspace/control.json` + `CONTROL.md`（好的可视化原料） | workbench 四栏（run 级） |
| 验证能力 | 流程纪律（review/tdd/retro），无宿主强制 | 同上 | 结构门禁（`check` exit 2），不验现实 | 独立只读 Auditor（仅 Claude 后端有快照守卫） |
| 维护风险 | 低（MIT 文本，pin 版本） | 高（beta + gh 写权限 + DSH API 漂移） | 中高（单维护者、绑定 DSH RC、第二台账） | 高（v0.x、#98、restore 文案不一致、多进程） |
| **DSH 视角判定** | **装子集** | **生产不装**（桌面端已装可继续用） | **不装，只借机制** | **不装，只借机制** |

**最小落地组合（约 1–2 天）**：① 从 v1.3.2 拷 `grilling`/`writing-for-agents`/`code-review`/`retro`/`handoff`（可选 `tdd`/`domain-modeling`）到 `~/.dsh/skills/`；② 自建 `state.json` + `gate.py`（证据存在+sha256+覆盖声明，不满足 exit 2；快照排除 `.git`），核验用 DSH `subagent` + 只读权限；③ 可视化用本 PR 的静态 dashboard + DSH 原生 Trajectory；④ 不装 Deck/J-Space/LHH。

---

## 6. Pi vs DSH 作为基础 harness：先核实「DSH 最差」这个说法

### 6.1 「多家 benchmark 显示 DSH 耗时/token 最差」——没有找到公开证据

**【事实】核查范围**：harness benchmark 元综述 `tmustier/harness-benchmarks`（27 项研究、274 条观测，截至 2026-09-10）逐条检索 "DeepSeek Harness"，**全库只有 1 项包含 DSH**：DeepSeek V4.1-Flash 模型卡里的 scaffold 对比（同一模型、8 个 scaffold、202 个任务，2026-09-10）。该研究中 **DSH Minimal 在 Terminal-Bench 2.1 得 90.6 排第一**（Pi 86.1、Claude Code 88.0），DeepSWE v1.1 得 72.6 排第二（mini-SWE 74.2 第一，Pi 66.2）；但模型卡**不公布 token、耗时与成本**，元综述里 DSH 这条观测的 `tokens_per_task`/`wall_time_seconds`/`cost_usd_per_task` 全为 null。

**【事实】你可能看过的图里都没有 DSH**：LHH 论文图（本机 `/tmp/harness_perf.png`）只含 LongHorizon-Harness / Claude Code / Codex CLI / OpenClaw / Hermes（WeaveBench 80.7 vs 51.8 是 LHH vs Claude Code）；Composio「三大框架最多差 30×」是 Claude Code / Hermes / Kimi Code；Portkey《The Harness Tax》是 Pi / Codex / Claude Code；Claw-SWE-Bench、Harness-Bench 也无 DSH。**把它们的数字安到 DSH 头上属于误归因。**

**【推断】该说法可能的三个来源**：① 把上述"harness 差异很大"的图误记成含 DSH；② 本机 DSH SuperAgent 的**体感**——它的固定提示确实比 Pi 重约 10 倍（见下），长会话里"又慢又费 token"是真实可测的；③ 非公开内测数据。①② 都不构成"多家 benchmark"。

### 6.2 本机可测的「固定 harness 税」：约 10–15 倍（中位约 12 倍）

口径来自本机会话日志（`~/.dsh/sessions/**/session.v4.jsonl.zstd` 解压读 system/message）与 Pi 1.5.2 安装包内 `buildSystemPrompt()` 实测，并用公开 Portkey 实测互校：

| 配置 | 固定前缀构成 | 字符数 | token 估算（±20–30%） |
|---|---|---:|---:|
| **DSH SuperAgent worker** | system message 41,671 + 29 个工具 schema 21,409 + 技能目录 7,838 | **63K–71K** | **≈1.7–2.0 万** |
| DSH SuperAgent orchestrator | role prompt 44,157 + 基础 prompt ≈7.5K + 21 工具 schema + 技能目录 | 72K–80K | ≈1.9–2.2 万 |
| DSH 团队 teammate（本会话被 spawn 的调研 worker） | system 7,472 + 23 工具 + 技能目录 | 30.8K | ≈0.8–0.9 万 |
| **Pi 默认 profile（4 工具、无插件）** | system 1,766（短路径）–2,593（长路径）+ 4 工具 schema 2,836 | **4.6K–5.4K** | **≈1.2–1.9K**（Portkey 实测 ≈2.6K） |

**读表注意**：① 这只是**每请求固定前缀**，不含会话历史、任务输入与工具结果，**不能直接推出任务级吞吐排名**；② DSH 这 16.6K 字符是 `communication/delivery/scope` 治理配置（约占 system prompt 40%），是"**用 token 买治理**"，不是纯浪费；③ DeepSeek 官方评测用的是薄模式 DSH Minimal——**不能把 SuperAgent 治理档的开销归给 DSH 内核**；④ 每个 Pi 插件也会增加固定开销，装载 subagents/plan/看板后 Pi 不再"裸装"；⑤ provider 前缀缓存会显著降低实际计费，要用真实 usage 的 uncached 部分判断。

### 6.3 Pi 的缺项可以插件补——功能上成立，治理上不成立

| 缺项 | 现状（2026-11-18） | 判断 |
|---|---|---|
| Subagents | `pi-subagents` 103 万下载/月（0.89.0）、`@tintinweb/pi-subagents` 7.7 万/月；两套 API 不兼容 | 成熟但竞争分叉 |
| Plan mode | **无官方内置**，npm 至少 10+ fork（如 `@narumitw/pi-plan-mode` 3.5 万/月） | 碎片化最严重 |
| Web UI/看板 | `agegr/pi-web` 8,305★（2.75 万下载/月）、`pi-gui` 1,466★、`pi-agent-dashboard` 351★ | 可视化可补，质量分层 |
| MCP | `pi-mcp-adapter` 210 万下载/月（7.0.1，1,663★） | 成熟 |
| 上下文压缩 | Pi 本体自带 compaction；`billion-context` 352 万下载/月（非 Pi 专属） | 可选 |
| Hooks/扩展事件 | Pi 内建 30+ 生命周期事件（`tool_call` 可阻断、`tool_result` 可改写） | 已满足（Pi 强项） |
| **治理（票据/角色/审批/审计/权限边界）** | **无等价包**；Pi 无内建权限系统；LHH 的 Pi 后端 issue #73 至今未实现 | **真缺口** |

**【建议】结论**：Pi 固定开销低、生态活跃、可视化可补；DSH 治理内置、固定开销高、但已在跑且迁移成本低。不要基于"DSH 最差"的说法选型——先做一次 1–2 小时的同模型同任务小 A/B：3 个 arm（Pi 默认 / DSH Minimal / 当前 DSH SuperAgent worker）× 3 个确定性任务 × 2 次重复，先过质量门（确定性测试 ≥2/3）再比 uncached token、wall time、人工介入；另跑一次 trivial prompt 直接量固定 input token（预期 Pi ≈2.6K、DSH worker ≈18–22K）。若结论是"治理档太重"，优先**裁剪 SuperAgent 提示词到 Minimal 级**或让 Pi 只当 worker，而不是整体换 harness。

---

## 7. SuperAgent 三条路：上游改 / 自行改造 / 社区替代

### 7.1 上游改：没有可行通道

**【事实】** `deepseek-ai/dsh-superagent-prototype`：MIT；**只有 1 个 commit**（2026-10-31，`8c32a9dc`）；`pushed_at` 2026-11-03；**issues/discussions 关闭、PR 总数为 0、无 release/tag**；社区 fork 自述"官方仓库不接受外部 PR"。README 自述"研究原型、仅供参照，文章里部分设计是未来方向、本原型未实现"。
→ **【建议】不要等 roadmap、不要提 PR**（没有通道，投入即沉没）；社区 fork（2,937 fork）才是实际演化面。

### 7.2 自行改造：可行，但先做版本管理

**【事实】** 本机 profile 用 `link:/root/work/dsh-superagent-prototype` 安装，而该目录**没有 `.git`**；与上游 main 对比已有 6 个源文件 + docs/007 被本地改过（飞书说话人前缀功能），`lib/` 是 2026-11-13 构建产物；docs/006 写的升级步骤是 `git pull && pnpm install && pnpm build`——**本机照文档升级走不通**。
→ **【建议】第一步（0.1 人日）**：在该目录 `git init`，提交"base=上游 8c32a9dc + 本地补丁"基线；不改运行中服务。

**三类改动的最小路径**（均基于本机源码核读，含文件级清单与粗估）：

| 改什么 | 最小实现 | 成本 | 风险/取舍 |
|---|---|---|---|
| **Plan 评审（YAML 层，推荐先试）** | profile `cordis.patch.yml` 覆写 `dsh-superagent-worker-preset`：加 `@deepseek-ai/dsh-plan-mode` + `@deepseek-ai/dsh-user-questions`（整行 config 替换，需复制现有 preset 约 110–130 行 YAML）；另在 `WORK_TOOLS` 加 `exit_plan_mode`（约 1 行 TS，需 rebuild）；人从工单页打开 worker Session 在 DSH UI 评审 | **0 行核心逻辑 + 1 行 TS + 110–130 行 YAML；1–2 人日** | 中低：root plan-mode 与 preset 子实例组合语义未验证；评审需人当场打开会话；可回滚 |
| **计划即工件（0 代码，先做）** | 提示词要求 worker 先给短计划（≤800 字）写进 `report.summary` + `human_action="请批准计划"`；人回复"批准"即触发后续执行；计划审批无显式状态机 | **0 行** | 低：靠模型遵守；长计划在面板摘要里被截断（160 字 preview） |
| **计划卡进面板（中改，第二阶段）** | report 加 `plan` 字段；`POST tickets/:id/plan-decision`；`ticket.tsx` 渲染计划 + 批准/退回 | **230–260 行 TS + ~80 行测试；2–4 人日** | 中高：碰 report/Attention/输入交付核心域；审批要确保唤醒 idle worker |
| **只读工作节拍页（推荐先做）** | 独立本地只读页，消费 `GET overview`/`GET tickets`（已含 title/stage/action/summary/sessionId/inputs），按"等我拍板/在跑/卡点/下一步"分组；**本 PR 的 `tools/superagent-dashboard.py` 已是此路径 PoC（约 290 行）** | **150–250 行；1–2 人日**（PoC 已完成大半） | 低：只读、不动域；耦合无版本号的管理 API（上游冻结中，风险低） |
| 面板内嵌看板 tab | `views/board.ts` + client board 组件 + 路由 + 测试 | 330–430 行 TS；3–5 人日 | 中低：只读但把维护面绑进面板代码 |
| **人侧去 GitHub（推荐先做）** | 0 行 TS：团队提示词把"先 PR/等 CI/auto-merge"等按需收起，交付改为"本地 git 提交 + ready 报告 + 飞书回复"；GitHub 仅 agent 侧留档 | **0 行代码；0.5–1 人日** | 无（人侧）；setup 仍需 agent 的 gh 账号 |
| 源码级去 GitHub | `resolveDeployment` 可选化 + github-watch 可选 + 新完成锚（本地 git/验证证据） | **300–600 行；3–6 人日** | 高：**失去 PR/review/CI 这个外部可验证锚**，与"执行与验证分离"需求冲突 |

**【建议】** 顺序：计划即工件（0 代码）→ YAML plan 评审（1–2 人日）→ 只读 dashboard（1–2 人日，PoC 已可用）→ 人侧去 GitHub（0 代码）→ 只有前几步被证伪后，再评估"计划卡进面板"或"源码级去 GitHub"。

### 7.3 社区替代：有同形态实现，但没有"更省心"的

| 项目 | 形态 | 人机界面 | GitHub 依赖 | 许可/活跃 | 判定 |
|---|---|---|---|---|---|
| **Hermes Agent**（你 Windows 侧已在用） | 个人/团队 agent + gateway + 多 agent Kanban | 桌面 + Web dashboard（127.0.0.1:9119）+ TUI/CLI + 21+ IM 渠道；**内置 `/plan`（写 `.hermes/plans/`）**；Kanban 看板（triage/todo/ready/running/blocked/review/done）+ 评审交接工具 | 无（可选；支持 local-only 完成契约） | MIT，264,373★，当天仍在提交 | **同形态里最强**；但本机是 detached v0.22.7 + **393 个本地提交 + patches 台账**——你已在这套栈上付维护费；再叠加 SuperAgent = 两套台账/两套提示词/两套权限，**不建议整体迁移**，只建议 1–2 周并行小实验 |
| OpenClaw | IM-first 个人助理 gateway（多渠道路由 + 插件生态） | Control UI + CLI/TUI + 20+ 渠道 | 无 | MIT，394,712★，活跃 | **参考实现**（人机面/渠道最成熟），但无 ticket/mandate/计划评审形态 |
| DeerFlow（字节） | "super agent harness"（subagent/memory/sandbox/skills/message gateway） | Web workspace + 多 IM 渠道 + HITL 审批 | 无 | MIT，85,480★，活跃 | 同形态但**重**（Docker + LangGraph/Postgres），与"少维护"冲突 |
| OpenHands Agent Canvas | 自托管 coding agent 控制中心 + 自动化 | Web UI + Slack/Linear 集成 | 无（可选） | MIT，93,724★，活跃 | 参考（无 IM-first、无工单路由） |
| Agent Zero / AutoGen | 单机单 agent / agent 编程框架 | Web UI / 无产品界面 | 无 | MIT / CC-BY-4.0 | 不同形态，仅参考 |
| **社区 SuperAgent fork**：`dsh-superagent-local`（无 GitHub 可运行）、`dsh-superagent-ui`（operator 控制台/看板）、`dsh-session-superagent`（把任务注入当前会话 + 状态栏）、`dsh-superagent-windows`、`open-superagent`（GitLab/钉钉、只接聊天）、`pi-superagent` 移植 | 都是同一形态的**裁剪件/参考实现** | 各自小面板 | 部分已可选/无 | 均为单人小项目（★3–49） | **可裁剪参考**，不能长期依赖 |

**【建议】** 三条路排序：**自改最小集（2.5–5 人日，0 行核心 TS）> 社区裁剪件参考 > 换 Hermes（仅 1–2 周实验）> 等上游（不可行）**。社区替代里最值得借鉴的是 Hermes 的三件：`/plan` 计划文件、Kanban 看板 + 评审交接、local-only 完成契约——**借模式，不搬栈**。

---

## 8. 建议的下一步（按成本从低到高，每步可停）

0. **先固化现状（0.1 人日）**：在 `/root/work/dsh-superagent-prototype` 执行 `git init` 并提交"上游 8c32a9dc + 本地 6 文件补丁"基线——本机 link 目录目前没有版本管理，不改就没有回滚点。
1. **0 代码双轨试点 1 周（0.5–1 人日）**：人侧固定只用飞书；GitHub 只由 agent 留档（允许名单清空、receive-all 关，提示词把"先 PR/等 CI"按需收起）；计划用 P0（`PLAN.md`/短计划 + Attention + 飞书确认）。验收：至少 3 个真实工单在不看 GitHub 的情况下完成评审与验收。止损：计划阅读体验不可接受则进第 2 步。
2. **YAML 补 plan 评审（1–2 人日，0 行核心逻辑 + 1 行 TS 白名单 + rebuild）**：profile `cordis.patch.yml` 覆写 worker preset，加 `@deepseek-ai/dsh-plan-mode` + `@deepseek-ai/dsh-user-questions`；从工单页 `SessionButton` 打开 worker Session，在 DSH Web UI 右侧栏评审计划。验收：一次完整 approve/keep-planning 闭环。止损：preset 组合语义不通就回退到 P0/A1 评估。
3. **只读工作节拍看板（0.5–1 人日收尾）**：本 PR 的 `tools/superagent-dashboard.py` 已是可用 PoC（读 sqlite，输出"需要你/进行中/长期未动/最近结束/最近事件"）；给它加"计划/待拍板"分组与定时刷新即可。验收：一页回答"现在几件在跑/卡在哪/等我什么/下一步"。止损：若只是重复现有 Overview，停手。
4. **1–3 人日（可选）**：只有第 1–3 步被证伪/不够用时，再做面板节拍化（今日四块 + 时间线 + 面板内答复 API `POST tickets/:id/answer` + 计划卡，3–5 人日）或源码级去 GitHub（3–6 人日，丢外部锚，不建议现在做）。
5. **不做的**：装 Deck 到 WSL2、装 J-Space/LHH 本体、为 plan mode 硬改 worker 预设、为可视化引入 LHH workbench/harness-one 画布、等上游/提 PR。

## 9. 需要你拍板

1. 是否按 **第 1 步「飞书人机面 + GitHub 仅存档/合并锚」试点 1 周**（0 代码，0.5–1 人日）？
2. 是否接受 **P0/P-1 计划流程**（短计划 + Attention + 飞书确认；0 代码）？
3. 是否需要 **YAML 补 plan 评审**（1–2 人日，可回滚）与 **静态看板收尾**（0.5–1 人日）？
4. 是否继续 Pi 作为 worker/实验沙盒的 P1–P3 实验（首版报告 §6）；还是先解决 SuperAgent 人机面再并行？
5. 面板节拍化/源码级去 GitHub 这类"碰核心"的改法，暂不做可以吗（报告建议先不做）？

## 附录：证据与来源

- 本机 SuperAgent 原型：`docs/001-domain.md`、`002-authorization.md`、`003-execution.md`、`004-prompts.md:63`、`005-panel.md`、`006-deployment.md:7-27,159-207`；`src/app/setup.ts`、`src/deployment.ts`、`src/app/sessions.ts:61-63,287-293`、`src/core/tickets.ts`、`src/sources/github.ts`、`cordis.patch.yml:16,123`。
- DSH 0.2.1-rc.3：`dsh --profile superagent --dump-config`（plan-mode 277、ui-plan 690、standard preset planning 组）；`@deepseek-ai/dsh-plan-mode`（`exit_plan_mode` 依赖 `userQuestions`）、`dsh-client-ui-plan`、`dsh-skill*` README。
- 运行中服务：`GET /orchestrator/api/{state,overview,tickets,sources}`（127.0.0.1:3082，只读）；`git reflog` 不属于事实来源，略。
- 插件市场快照：`/tmp/plugins.json`（11,744 条，2026-11-17）中 `dsh-superagent-trace`、`dsh-super-kanban`、`dsh-mattpocock-skills-deck` 等。
- LHH：`research/lhh.md`、PyPI `lh-harness==0.1.8`、GitHub `AMAP-ML/LongHorizon-Harness`（#73/#98、v0.1.8、1,876★）。
- J-Space：`research/j-space.md`、npm `@anonyjcy/dsh-j-space@1.2.6`、上游 `Tiger3807861189/J-Space-Cognition-Suite`。
- mattSkill：`research/matt-skills.md`、`mattpocock/skills` v1.3.2（commit 5863806）。
- Pi：`research/pi-agent.md`、`research/probe-pi/`（Pi 1.5.2 隔离安装 + `buildSystemPromptSections` 实测 1,766 字符）。
- 上游设计文章：`https://raw.githubusercontent.com/QianJinGuo/wiki-public/main/entities/deepseek-super-agent-design-router-worker-architecture-2026-10-31.md`。
- 可视化 PoC：`tools/superagent-dashboard.py`（本 PR，只读 sqlite，`--demo` 可生成演示）。
