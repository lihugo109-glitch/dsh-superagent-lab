# SuperAgent 引入 DSH 常驻队友：现状验证、设计取舍与分阶段计划

> 状态：待方向确认（2026-11-13）。
> 结论先行：能力已经跑通，缺的不是版本而是开关；「常驻」应落在**工单粒度**上——用「项目级工单」承载持续工作，而不是另做一套跨工单团队去绕开 SuperAgent 的架构。

## 0. 结论摘要

- **不是 DSH 版本落后，缺的是开关**：本机部署的 DSH 0.2.1-rc.3 已内置实验性 Agent Teams bundle（`@deepseek-ai/dsh-experimental-agent-team-profile`），默认关闭；在 profile 的 `dsh.profile.bundles` 中启用后，SuperAgent 的 worker Session 立即获得 `spawn_teammate` / `send_message` / `wait_agent` / `team_task_*` 等团队工具，不需要升级 DSH。
- **已实机验证**：worker 会话内成功创建 fork 分身与 fresh 队员各一个，`list_agents` 可见、`send_message` 往返正常。当前是「工单内常驻」：team root 就是 worker 会话自身，工单结束即释放。
- **主 Session 也有 Team 工具（实证）**：orchestrator 的 model 请求头里已出现 `spawn_teammate` / `list_agents` / `send_message` / `team_task_*` 等工具；但它的系统提示是 `complete: true`，会丢弃 Team 策略段，等于「能自行开团却没有策略约束」——这是需要加守卫/提示词的现实风险。
- **设计取舍：按工单粒度承载持续项目，而不是跨工单团队**。一个持续项目放进一个工单：worker Session 在工单存续期内可反复唤醒、多轮 handoff、里程碑推进；工单完成后才释放。这样保留授权、外部锚（thread/PR/CI）与完成判定，也避免绕开 SuperAgent 的架构。跨工单常驻只作为未来可选项（P3），默认不做。
- **建议**：P1 把「工单内 teammate（默认 fork、评审 fresh）」用起来并补提示词与守卫；P2 定义「项目级工单」的边界与生命周期规则（提示词/策略层，必要时小改 executor 对 teammate 的处置）；暂不动 Session 创建路径。
- **未来方向（讨论中）**：方向专精路由、per-unit 注意力上限、飞书身份前缀（交付/工具层确定性注入）；记录在 §5，不改变 P1/P2。

## 1. 现状验证（2026-11-13）

### 1.1 版本与开关

| 项 | 事实 | 证据 |
| --- | --- | --- |
| DSH CLI | 0.2.1-rc.3（已安装，`dsh -V`） | `/usr/local/lib/node_modules/@deepseek-ai/dsh/package.json` |
| Agent Teams 包 | 随安装分发，实验性 optional bundle；`dsh-experimental-agent-team`、`-tool-agent-team`、`-profile` 同为 0.2.1-rc.3 | CLI 的 `node_modules/@deepseek-ai/dsh-experimental-agent-team-profile/cordis.patch.yml` |
| 默认状态 | 关闭：shipped profile 模板不含该 bundle，插件管理器把它列为可开启项 | `@deepseek-ai/dsh-app-boot/lib/index.js` 的 `OPTIONAL_BUNDLES` |
| 本机启用 | profile bundles 已追加该 bundle | `/root/.dsh/profiles/superagent/package.json` |
| 启用方式 | 面板开关；或 `dsh plugin --profile <name> add @deepseek-ai/dsh-experimental-agent-team-profile`（透传 pnpm） | `dsh plugin --help` |
| npm 版本 | `@deepseek-ai/dsh` latest=0.2.2-rc.1、next=0.2.2-rc.3；team 包 0.2.2-rc.1 描述与 0.2.1-rc.3 相同，无新能力证据；注意 team 包 latest tag 停在旧的 0.1.5-alpha.2，勿按 latest 裸装 | `npm view` |
| teammate 提供者 | fresh=`spawn`、fork=`fork`，两个 provider 均由 dsh-base 注册 | profile dump：`subagent-spawn-in-process` / `subagent-fork-in-process` |

### 1.2 为什么 worker 会话能拿到 Team 工具

1. `tool-agent-team` 只在「Team 成员」的 Agent scope 安装工具（`dsh-experimental-tool-agent-team/lib/index.js` 的 `apply`/`install`）。
2. DSH 的 Team 是隐式的：顶层 Session（没有 `parentSession`，或父会话不是成员）自己就是 team root，`tryMembership` 返回 `role: 'lead'`（`dsh-experimental-agent-team/lib/index.js` 的 `tryMembership`）。SuperAgent 的 worker Session 由 `sessionController.create` 创建，是顶层 Session，因此自动成为 lead。
3. Team 工具注册在 Agent 自身 scope；SuperAgent 的 `tools.restrict` 只过滤继承工具，不遮蔽本层注册（`src/app/sessions.ts` 的 `workOnly` 按父 scope 取可用名单）。所以 `WORK_TOOLS` 不参与 Team 工具的可见性，无需修改。
4. 主 Session 同属顶层 Session，按同一逻辑也拿到 Team 工具——已用其 model 请求头的工具表实证。

### 1.3 实机验证记录

- 工单 worker 会话内 `list_agents` 可见自身为 lead。
- `spawn_teammate` 创建 fork 分身（继承 lead 已完成轮次）成功；分身确认能看到 lead 已完成上下文，当前未完成轮次不在继承范围内。
- `spawn_teammate` 创建 fresh 队员（独立上下文）成功；两者均通过 `send_message` 向 lead 回报，成员完成后转 `inactive`。
- 主 Session 请求头工具表含 Team 工具（实证）；但其 system prompt 中 `TEAM_POLICY` 段被 `complete: true` 抑制（`src/app/sessions.ts` 的 prompt section 注册 + `dsh-system-prompt` 的 complete 语义）。

### 1.4 生命周期与边界

| 能做 | 不能做 / 风险 |
| --- | --- |
| 工单内创建 fork/fresh 队友，多次唤醒、互相发消息、共享任务板 | 队友不跨工单：team root 是 `worker-<ticketId>`，工单结束即释放，工具随之收回 |
| 队友与 lead 共享文件系统，按 `write_scopes` 分工写（advisory，无锁） | 多个成员写同一文件会互相覆盖；也没有 git worktree 级隔离 |
| fork 继承 lead 已完成轮次；fresh 只带初始任务 | fork 不包含未完成的当前轮，spawn 初始任务必须自包含 |
| 成员可冷唤醒（continuable 语义） | handoff / Assignment 结束时 executor 会 `stopSubagents` 让队友休眠；工单内后续可 `send_message` 冷唤醒，但需要 lead 主动发消息，且工单结束后无法再唤醒 |
| 主 Session 已持有 Team 工具 | 主 Session 的 Team 策略段被抑制，Router 可能自行开团却无约束 → 需要 guard 或提示词禁用 |

## 2. 设计取舍：项目级工单，而不是跨工单团队

- **工单可长可短**：工单不是一次性会话，而是「按目标切分的持久执行单元」——worker Session 按 `worker-<ticketId>` 常驻，可在工单存续期内被后续消息反复唤醒、多轮 handoff、推进里程碑；目标完成（ready）或放弃（dropped）才释放。
- **持续项目 = 一个项目级工单**：如果预期一个项目会持续数天/数周、多轮推进，就把它放在一个工单里；里程碑用 progress 报告推进，交付时再 ready。上下文仍按工单隔离，文件与 PR 作为跨轮记忆的真源。
- **为什么不做跨工单常驻**：
  1. 会绕开 SuperAgent 的授权、外部锚（thread/PR/CI）、完成判定与报告回传链路；
  2. 技术上要把 worker 挂到长期 team root 下，而 `SessionCreateRequest` 没有 `parentSession` 字段，必须改走 Team/subagent 创建路径，并豁免 `stopSubagents` 对 Team child 的停止——是实质性的架构改动；
  3. 收益可以用「项目级工单」低成本获得：同一工单内上下文、目录、队友、文件都连续。
- **跨工单常驻只作为未来可选项（P3）**：仅用于「跨项目共享角色」（如长期评审官、架构看护）且无法用文件/PR 承载时，再单独立项。

### 2.1 两层工作单元，不要混为一谈

| 层 | 是什么 | 管什么 | 不管什么 |
| --- | --- | --- | --- |
| 外层：SuperAgent Ticket | 对外的工作单元，建议做成项目级、可长可短 | 授权、外部锚（thread/PR/CI）、报告回传、完成判定 | 团队内部分工的细节 |
| 内层：Team 共享任务板 | DSH Agent Teams 自带 `team_task_*`，轻量任务 DAG | 团队内分工：owner、`blocked_by`、`write_scopes`、revision | 授权、外部锚、结束工单 |

因此「常驻」不等于「跨工单团队」：外层仍用 Ticket（项目级），内层用现成任务板分工；短活/评审也可以完全免 Ticket，只用 teammate + 任务板（无外部锚，不适合对外交付）。

### 2.2 长工单的可行性核对

- **寿命**：工单没有时间上限，只有人停止、`ready` 且无 PR、或 PR 全部关闭会结束它（`src/core/tickets.ts:86-89,345`）；人的消息可以恢复原工单（`:258`）。硬限制只在每轮：后台工作 30 分钟（`src/executor/dsh.ts:32`）、prepare 只在首轮最多 10 分钟（`:28`）、并发槽只占 launch/turn（`docs/003-execution.md` 的 Concurrency）。
- **上下文**：工具结果超过 8192 字符只保留头 4096 + 尾 1024（`cordis.patch.yml` 的 tool-result-pruner），长工单会「腐烂」；但工单目录稳定、prepare 只跑一次，worktree/PR/thread 天然是外部真源，**文件为真源 + 阶段性 checkpoint** 是对策。
- **卡点**：现有规则下「PR 合并/关闭即结束工单」，所以项目级工单必须把寿命锚在项目级（issue/milestone/thread），PR 只是阶段产物——这是规则改动，不是 executor 代码改动。

## 3. 三种工作形态对比

| 维度 | 临时工单 | 项目级工单（推荐承载持续工作） | 免工单转交（Team teammate） |
| --- | --- | --- | --- |
| 适用 | 一次性小改、单点修复 | 持续项目、多轮推进、需要外部锚 | 对话内调研/评审/并行推演 |
| 生命周期 | 完成即释放 | 项目存续期内常驻，里程碑推进，交付后释放 | 随 lead 会话存活，成员可休眠/唤醒 |
| 上下文 | 每单独立、显式转交 | 同单连续，文件/PR 为真源 | fork 继承主线已完成轮次 |
| 外部锚/授权 | 有 | 有（里程碑 + 最终交付锚） | 无（只在对话中被要求） |
| 队友 | 工单内可用 | 工单内常驻（handoff 后休眠、可冷唤醒） | lead 的会话分身 |

## 4. 分阶段计划

### P0（已完成）：启用与实机验证

- 启用 `@deepseek-ai/dsh-experimental-agent-team-profile`。
- 验证 worker 会话内 fork/fresh 队友创建、消息往返、成员可见性。
- 记录边界：工单内常驻、handoff 会休眠、工单结束即释放。

### P1（低成本，不需要改 executor）：把工单内队友用起来

- 提示词：worker 的团队提示词说明「何时创建 teammate、默认 fork、评审用 fresh、spawn 任务必须自包含、handoff 后成员会休眠」。
- 守卫：主 Session 的 Team 工具加 `tools.guard` 拒绝，或在其提示词里显式禁止开团；worker 侧保留现状。
- 协作规范：写域划分、成员上限（默认每队 8）、共享任务板（`team_task_*` + `write_scopes` + `blocked_by`）。
- 决策：经典 `subagent` 与 Team 并存还是收敛到一种。

### P2（策略/文档层 + 少量代码）：定义「项目级工单」

- 定义什么算工单：持续项目一个工单；只有出现「新的外部目标/新的完成锚/新的授权」才拆新工单。
- 项目级锚：用 issue/milestone/thread 定义工单寿命；完成 = 人宣布或里程碑关闭；PR 只是阶段产物。需要解耦现有「PR 关闭即结束工单」的规则。
- 上下文纪律：文件为真源 + 阶段 checkpoint（工具结果会被 8192 字符截断，必须落文件）。
- 队友在长工单内的处置：handoff 时 `stopSubagents` 会 drain 掉 worker 的 teammate（`src/executor/dsh.ts:588`、`src/executor/background.ts:141`）。两个选项：依赖 `send_message` 冷唤醒（continuable 语义，`dsh-subagent` 类型定义）或对 Team child 做豁免——二选一后再验证。
- `workOnly` 的允许名单显式列出 Team 工具（当前靠「本地注册不被遮蔽」生效，显式列出更稳，且未来若 Team 工具改为继承注册也不会被误遮）。
- 文档：更新 `docs/003-execution.md`（长工单与队友生命周期）、`docs/004-prompts.md`、`docs/006-deployment.md`、README/SETUP；如动 preset 需同步 `tests/bundle-patch.spec.ts`。

### P3（可选，默认不做）：跨工单常驻

- 仅在跨项目共享角色确有需要时启用；需要把 team root 迁到长期 Session（主 Session 或专用常驻队长会话），并改 Team child 的停止/恢复策略。

## 5. 未来方向（讨论中，未纳入当前计划）

以下思路来自 2026-11-13 的讨论，作为本 PR 的方向记录，不改变 P1/P2 的实施范围；等其中某项成为可执行的改动时再单独立项、单独开 PR。

- **方向专精路由**：现状没有持久专精——worker 按工单创建，主 Session 只按 Policy/Eval 决定接不接单，不按专精分派。低成本近似：不同 Source/规则配专用提示词与 skills，用 teammate 人设做「专家分身」；要做自动分派，需要领域注册表 + 路由规则 + 专精池。
- **方向限制**：Policy 规则 + admission 表决定哪些消息可建单，ticket Mandate 定范围，worker 工具白名单 + guard 限制能做什么；缺口是按方向绑定路径/仓库/工具集（当前 `prepare` 与 `blockedCommands` 是全局设置）。
- **注意力上限**：工单级注意力预算已有雏形（ack≤100 字、进度内部化、只有 ready/结构化问题才打扰人），硬资源上限也有（并发槽、后台 30 分钟、Team `maxMembers=8`/`maxTasks=256`、消息大小上限）。缺口是 per-unit 的「打扰配额」（如每单元每周报告/打扰次数上限），需新增配置。
- **身份前缀（哪个单元在说话）**：应在交付层/工具层确定性注入（Source 发送或 replies 渲染时加「层级 + 单元名」前缀），不写进模型提示词，避免占用注意力；与飞书多单元对话的可识别性一起作为 UX 项。

## 6. 待拍板决策

1. **工单粒度与项目级锚**：是否采用「项目级工单」（持续项目一个工单、issue/milestone/thread 定寿命、里程碑推进、交付后由人宣布完成）？拆单条件 = 新目标/新锚/新授权，是否认可？
2. **主 Session 的 Team 权限**：禁用（guard/提示词）还是保留但补策略段？
3. **上下文默认**：默认 fork、评审用 fresh？fork 的成本与假设继承偏差是否接受？
4. **工具收敛**：经典 `subagent` 与 Team 并存，还是只保留一种？
5. **并发与隔离**：每队默认 8 个成员、无 worktree 隔离是否接受？

## 7. 验证方法与限制

- 验证方式：静态核对相关代码/配置，加实机创建 teammate 与消息往返；主 Session 工具表取自其持久化 model 请求头。
- 限制：只在 DSH 0.2.1-rc.3 + 实验性 Agent Teams 上验证；未做进程重启后的成员恢复测试；工单内队友跨 handoff 的冷唤醒是代码推断（continuable 语义支持，但未实测）；fork 的 token 成本未量化；项目级工单与「PR 关闭即结束」的解耦尚未落成规则。
