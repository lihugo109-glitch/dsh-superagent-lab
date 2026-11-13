# SuperAgent 引入 DSH 常驻队友：现状验证、设计意图与分阶段计划

> 状态：待方向确认。本文记录 2026-11-13 的实机验证结果与实施计划，供评审后再进入 executor 层改动。
> 结论先行：能力已经跑通，但当前是「工单内常驻」；「跨工单常驻」需要把 team root（团队根会话）从 worker 会话移到长期存在的会话，属 executor 层改动。

## 0. 结论摘要

- **不是 DSH 版本落后，缺的是开关**：本机部署的 DSH 0.2.1-rc.3 已内置实验性 Agent Teams bundle（`@deepseek-ai/dsh-experimental-agent-team-profile`），默认关闭；在 profile 的 `dsh.profile.bundles` 中启用后，SuperAgent 的 worker Session 立即获得 `spawn_teammate` / `send_message` / `wait_agent` / `team_task_*` 等团队工具，不需要升级 DSH。
- **已实测可用**：worker 会话内成功创建一个 fork 分身与一个 fresh 队员，均收到回报。当前形态是「工单内常驻」：team root 就是 worker 会话自身，工单结束即释放。
- **跨工单常驻的核心约束**：`SessionCreateRequest` 没有 `parentSession` 字段（`@deepseek-ai/dsh-api-session-controller/lib/types/types.d.ts`），所以不能用现有 `sessionController.create` 把 worker 挂到主 Session 名下；要挂必须改走 Team/subagent 的创建路径。这是本计划的关键判断。
- **建议**：先用「工单内 teammate（默认 fork、评审 fresh）」承接并行调研与评审；跨工单常驻按 P2 单独设计，先拍板 team root 形态与免工单边界。

## 1. 现状验证（2026-11-13）

### 1.1 版本与开关

| 项 | 事实 | 证据 |
| --- | --- | --- |
| DSH CLI | 0.2.1-rc.3（已安装，`dsh --version`） | `/usr/local/lib/node_modules/@deepseek-ai/dsh/package.json` |
| Agent Teams 包 | 随安装分发，实验性 optional bundle；三个包 `dsh-experimental-agent-team`、`-tool-agent-team`、`-profile` 版本同为 0.2.1-rc.3 | 同目录 `node_modules/@deepseek-ai/dsh-experimental-agent-team-profile/cordis.patch.yml` |
| 默认状态 | 关闭：shipped profile 模板不含该 bundle，插件管理器把它列为可开启项 | `@deepseek-ai/dsh-app-boot/lib/index.js` 的 `OPTIONAL_BUNDLES` |
| 本机启用 | profile bundles 已追加该 bundle | `/root/.dsh/profiles/superagent/package.json` |
| npm 最新 | 0.2.2-rc.1 / next 0.2.2-rc.3，仍是同一批实验包；升级不是启用前提 | `npm view @deepseek-ai/dsh version dist-tags` |
| teammate 提供者 | fresh=`spawn`，fork=`fork`，两个 provider 均由 dsh-base 注册 | profile dump：`subagent-spawn-in-process` / `subagent-fork-in-process` |

启用方式：在 Web 面板的插件/视图里打开「智能体团队」，或等价地在该 profile 的 `dsh.profile.bundles` 中加入 `@deepseek-ai/dsh-experimental-agent-team-profile`；重载后生效，无需重装或升级。

### 1.2 为什么 worker 会话能拿到 Team 工具

1. `tool-agent-team` 只在「Team 成员」的 Agent scope 安装工具（`dsh-experimental-tool-agent-team/lib/index.js` 的 `apply`/`install`）。
2. DSH 的 Team 是隐式的：顶层 Session（没有 `parentSession`，或父会话不是成员）自己就是 team root，`tryMembership` 返回 `role: 'lead'`（`dsh-experimental-agent-team/lib/index.js` 的 `tryMembership`）。SuperAgent 的 worker Session 由 `sessionController.create` 创建，是顶层 Session，因此自动成为 lead。
3. Team 工具注册在 Agent 自身 scope；SuperAgent 的 `tools.restrict` 只遮蔽继承工具（`src/app/sessions.ts` 的 `workOnly` 通过父 scope 取可用工具名），所以这些本地工具不被 `WORK_TOOLS` 名单遮蔽。
4. 主 Session 同样是顶层 Session（`src/app/sessions.ts` 创建 `orchestrator-*` 会话），按同一逻辑也应是 lead 并持有 Team 工具——这一点是代码推断，尚未在主 Session 上实测。

### 1.3 实机验证记录

- 工单 worker 会话内 `list_agents` 可见自身为 lead。
- `spawn_teammate` 创建 fork 分身（继承 lead 已完成轮次）成功；该分身确认自己能看到 lead 已完成上下文，且当前未完成轮次不在继承范围内。
- `spawn_teammate` 创建 fresh 队员（独立上下文）成功，二者均通过 `send_message` 向 lead 回报。
- 两个成员都出现在 `list_agents` 中；成员完成后转为 `inactive`，可被 `send_message` 再次唤醒（可续会话语义）。

### 1.4 当前能力边界

| 能做 | 不能做 |
| --- | --- |
| 工单内创建 fork/fresh 常驻队友，多次唤醒、互相发消息、共享任务板 | 队友跨工单存活：team root 是当前 worker 会话，工单结束即释放，工具随之收回（`src/app/sessions.ts` 的 ticket 结束守卫） |
| 队友与 lead 共享同一文件系统与工作目录，可并行读、按写域分工写 | 队友之间写同一文件没有锁，只有 advisory 的 `write_scopes` 提示 |
| fork 继承 lead 已完成轮次的上下文；fresh 只带初始任务 | fork 不包含「尚未完成」的当前轮内容，spawn 初始任务必须自包含 |
| 成员完成后转为 inactive，可被 `send_message` 再次唤醒（可续会话语义） | 队员生命周期随 team root；team root 所在的 worker 会话结束后，成员无法再被唤醒 |

## 2. 设计意图：为什么值得跨工单常驻

- **上下文成本**：现在每个工单一个独立 worker Session，同一项目要反复重读仓库、重复解释背景；跨工单经验只落在文件/PR 里，模型层面没有「同一个队友」的连续性。让一队常驻分身带着项目记忆长期存在，可降低重复读取与重复解释成本。
- **角色连续性**：人设、职责与项目知识可以挂在一个长期成员上（如架构看护、评审官、某子项目的长期负责人），而不是每个工单重新塑造。
- **与工单互补而非替代**：工单的价值在「按目标切分上下文 + 外部锚（thread/PR/CI）+ 完成判据 + 显式转交」；常驻队友补的是「跨目标连续、低延迟协作、fork 继承背景」。长任务与对外交付仍应走工单，短活/调研/评审可免工单。

## 3. 三种工作形态对比

| 维度 | 工单（ticket） | 免工单转交（Team teammate） | 常驻团队（目标形态） |
| --- | --- | --- | --- |
| 上下文 | 每工单独立、按目标切分；转交需显式给背景 | fork 继承主线已完成轮次；fresh 只带任务 | 主线会话常驻，成员带项目记忆；文件为真源 |
| 生命周期 | 目标完成即结束释放 | 随 lead 会话存活；成员可休眠/唤醒 | 跨工单长期存活，按角色持续存在 |
| 外部锚 | 有（thread/PR/CI/完成判定） | 无 | 工单仍是外部锚，成员是其执行者 |
| 授权 | 明确（Policy/accept） | 仅「对话中被要求」 | 需新设计：谁能派活、谁能对外发言 |
| 成本 | 会话引导 + 上下文转交 | 低延迟；fork 复制上下文有 token 成本 | 常驻上下文与压缩策略需调优 |
| 风险 | 跨单不记忆、重复读 | 无锚、失败无人接手、fork 继承偏差 | 注意力预算、成员上限、崩溃恢复 |

## 4. 分阶段计划

### P0（已完成）：启用与实机验证

- 启用 `@deepseek-ai/dsh-experimental-agent-team-profile`。
- 验证 worker 会话内的 fork/fresh 队友创建、消息往返、成员可见性。
- 验证记录见 §1.3。

### P1（低成本，不需要改 executor）：把工单内队友用起来

- 提示词：在 worker 的团队提示词里说明「需要并行调研/独立评审时可创建 teammate；默认 fork，评审用 fresh；spawn 任务必须自包含（fork 不含当前未完成轮次）」。
- 边界：写域划分、成员上限（默认每队 8）、共享任务板用法（`team_task_*` + `write_scopes` + `blocked_by`）。
- 守卫：worker 的 ticket 结束守卫保持不变；队友随工单释放。
- 验证：用一次真实工单做「fork 分身并行调研 + fresh 评审」的对照实验，记录 token 与耗时。

### P2（executor 层）：让 worker 成为长期 team root 的成员

两条路线二选一：

- **路线 A：主 Session 作为 team root**。executor 不再用 `sessionController.create` 直接建 worker，而用 Team/subagent 的创建路径（`agentTeams.spawnTeammate` 或等价 continuable subagent provider）创建 worker 成员，`parentSession`=主 Session。工单结束只停止该成员本轮工作、不销毁成员；下一次工单可复用或唤醒。
- **路线 B：专用常驻队长会话**。新增一个长期存在的「团队队长」Session 作为 team root，主 Session 保持瘦路由器职责；executor 把工单派给队长的 worker 成员。好处是路由与团队编排解耦，风险是再多一个常驻 Session 要管理。

两条路线都必须处理：

1. worker 会话 ID 约定（`worker-<ticketId>`）与成员身份的映射、重启后的恢复；
2. assignment/input 投递与报告回传仍走现有 Executor/Engine 链路；
3. 并发 worker slot 与 Team 成员上限的关系；
4. 权限/预设继承（worker preset、subagent 的 `standard` preset 与 Team 成员身份）；
5. ticket 结束后「工具收回」策略改为「停止本轮、保留成员但拒绝无工单授权的新工作」；
6. 崩溃/重启恢复：主 Session 或队长会话重启后，成员与工单的对应关系恢复。

### P3（产品形态）：常驻队长 + 工单退化为任务项

- 主/队长会话对人的对话入口保持单一（注意力预算），队友之间通过 `send_message` 协作。
- 人设与项目记忆：人设放团队提示词/成员描述；项目记忆以文件为真源，session 只做短期上下文（压缩会丢中间细节）。
- 面板展示 roster 与共享任务板；需要独立评审时强制 fresh。

## 5. 待拍板决策

1. **team root 形态**：主 Session（路线 A）还是专用常驻队长会话（路线 B）？
2. **免工单范围**：建议只读调研/评审免单；写仓库、对外交付必须走工单（保留授权与完成锚）。
3. **默认上下文**：是否默认 fork、fresh 仅用于评审？fork 的成本与假设继承偏差需要接受。
4. **成员上限与并发**：每队默认 8 个成员；常驻成员数量与 worker slot 如何配比？

## 6. 验证方法与限制

- 验证方式：静态核对相关代码/配置（行号见表与正文），加实机创建 teammate 与消息往返。
- 限制：只在 DSH 0.2.1-rc.3 + 实验性 Agent Teams 上验证；未做进程重启后的成员恢复测试；未量化 fork 的 token 成本；主 Session 持有 Team 工具是代码推断，尚未实测；跨工单常驻尚未实现。
