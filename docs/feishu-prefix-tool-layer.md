# 飞书消息身份前缀：改为交付层确定性注入

> 状态：待人工审阅（2026-11-13）。从 PR #24 §5「未来方向」拆出的第一项落地改动。
> 结论：说话方前缀不再写在提示词里让模型每次生成，而是由交付层在发送飞书消息时确定性注入；模型层的前缀要求已从部署态提示词配置中移除。

## 1. 背景

飞书是多单元共用的对话面：同一条线程里，既有主 Session（Orchestrator）直接说话，也有各工单 worker 的结果被转述。为了让用户分得清「哪个层级、哪个单元在说话」，此前的临时做法是在提示词里要求模型在每条 IM 消息前手写 `[Orchestrator]` 或 `[<工单短名>]`。

这个做法是 stopgap：

- 占用模型注意力，且每条消息都要重新生成，容易漏、写错名或写错层级；
- 前缀属于「消息从哪个单元发出」的确定性信息，模型没有比交付层更可靠的信息来源；
- 无法在提示词外统一校验格式（例如短名与工单实际名不一致）。

因此本次把该机制下沉到工具/交付层：**模型只写消息正文，交付层知道说话方并负责渲染前缀**。

## 2. 设计

### 2.1 说话方的语义

消息在领域模型里本来就带 `ticketId`（这条消息属于哪个工单，可缺省）与 `kind`（acknowledgement / reply / notice）。据此可以确定性得到说话方：

| 消息 | 说话方 | 渲染 |
| --- | --- | --- |
| 工单相关的 acknowledgement / reply（受理回执、答复、结果、待人工决定） | 该工单的 worker | `[<工单短名>] ` |
| 无工单归属的消息（主 Session 自己的答复、通知等） | 主 Session | `[Orchestrator] ` |
| GitHub 渠道消息 | 不适用（GitHub 评论有自己的自动代理声明行） | 不渲染 |

「工单短名」= 工单执行名去掉目录唯一化用的 `-<12 位工单 id>` 后缀，例如 `im-prefix-tooling-2e3625c36cd2` → `im-prefix-tooling`，与工单工作树名一致，便于和面板、目录对应。

### 2.2 注入位置：交付层，而不是提示词或渠道脚本

- `src/core/ports.ts`：`OutboundMessage` 增加可选 `speaker` 字段，语义是「这条消息由谁说出」，渠道可以选择渲染或忽略。
- `src/core/replies.ts`：`Replies` 在排队 acknowledgement / reply 时按消息归属标注 speaker（`speakerOf(ticket)`，工单短名或 `Orchestrator`），并导出 `ORCHESTRATOR` 常量。
- `src/sources/feishu-channel.ts`：发送飞书消息时渲染 `[speaker] ` 前缀。三点约束：
  1. **只装饰正文，不改回执**：前缀在 delivery 时加，outbox 回执里保存的仍是模型写的正文，重试语义不变；
  2. **不占 IM 字数预算**：飞书 100 词上限只统计正文（先 `checkedImText(message.text)` 再拼前缀），前缀不会把合法消息推成超限；
  3. **不重复**：正文若已带相同前缀（过渡期或旧提示词残留），不再二次拼接。
- 其余渠道（GitHub 评论、GitHub review 回复）不读 `speaker`，行为不变。

### 2.3 为什么不放在提示词或「让模型传 speaker 参数」

- 放在提示词 = 继续占用注意力，且模型仍然可能写错——本次要消除的正是这一点。
- 让模型显式传 speaker 给 reply 工具 = 把确定性信息重新交给模型判断，同样不可靠，还增加工具参数。
- 放在渠道脚本/Shell 包装层 = 渠道拿不到工单归属；`Feishu Channel` 是第一个能同时看到「消息 + 归属 + 正文」的层。

## 3. 改动清单

| 文件 | 改动 |
| --- | --- |
| `src/core/ports.ts` | `OutboundMessage` 增加可选 `speaker` 字段及文档 |
| `src/core/replies.ts` | 导出 `ORCHESTRATOR`、`speakerOf`；受理回执、acknowledgement、reply 排队时标注 speaker |
| `src/sources/feishu-channel.ts` | 发送时渲染 `[speaker] `；只统计正文字数；相同前缀不重复 |
| `tests/feishu-channel.spec.ts` | 新增：前缀渲染、无 speaker 不渲染、不重复、字数只算正文 |
| `tests/core-engine.spec.ts` | 新增：工单消息带工单短名、无工单消息带 `Orchestrator`；更新受理回执断言 |
| `tests/runtime.spec.ts` | 端到端断言 Feishu 受理回执的 markdown 带 `[<工单短名>]` |
| `docs/007-architecture.md` | 架构文档：交付层负责前缀、字数限制只算正文；测试表登记新测试 |

实际代码改动见同 PR 的 `patches/feishu-prefix-tool-layer.patch`（对 `deepseek-ai/dsh-superagent-prototype` 当前 `main`（`8c32a9d`）的完整补丁）。

## 4. 行为对照

假设工单短名为 `im-prefix-tooling`、受理回执文本为「收到，开始处理。」

| 场景 | 改动前（提示词版） | 改动后（交付层版） |
| --- | --- | --- |
| 工单受理回执 | 模型需自己写 `[im-prefix-tooling] 收到，开始处理。` | 模型只写「收到，开始处理。」，交付层发成 `[im-prefix-tooling] 收到，开始处理。` |
| 主 Session 答复 | 模型需自己写 `[Orchestrator] …` | 模型只写正文，交付层发成 `[Orchestrator] …` |
| 漏写/写错前缀 | 可能发生，且难以校验 | 不可能漏写；短名直接取自工单执行名 |
| 100 词上限 | 前缀占用预算 | 前缀不占预算 |
| GitHub 评论 | 无前缀 | 无前缀（行为不变） |

## 5. 验证

- `pnpm typecheck`：通过。
- `pnpm test`（针对性）：`tests/feishu-channel.spec.ts`、`tests/core-engine.spec.ts`、`tests/runtime.spec.ts` 通过。
- `pnpm build`：通过，构建产物为下次重启后实际加载的代码。
- 代码在部署检出（`/root/work/dsh-superagent-prototype`）直接应用并验证；本 PR 的补丁与当前上游 `main`（`8c32a9d`）逐文件对应，可在干净检出上 `git apply` 复现。

## 6. 部署步骤

1. 重启 dsh-superagent 以加载新构建（当前进程仍运行旧代码）：`scripts/dsh-superagent --profile superagent restart`。重启会中断正在执行的工单轮次，应在没有活动工单/合适时机执行。
2. 提示词配置：移除 `communication` 段末「让模型写前缀」的段落（部署态 revision 6 已保存）。移除后模型不再在前缀上花注意力；即使旧版本残留了相同前缀，交付层也不会重复拼接。

## 7. 限制与未验证

- 本工单会话内无法重启服务验证真实飞书消息（重启会中断本工单自身的执行会话），线上渲染需在重启后抽查一条工单回执确认。
- 说话方按「消息归属」判定：若主 Session 用自己的话直接答复一个已关联工单的问题，会显示为 `[<工单短名>]`。这是确定性规则的已知边界；若需要更细的「层级」区分，应作为后续 UX 项单独立项。
- 工单短名去掉了 id 后缀：两个不同工单的理论撞名会显示相同前缀（概率低；撞名时可再讨论是否保留后缀）。
- 全量测试在本机存在与本次改动无关的既有环境失败（测试进程继承部署环境变量 `GIT_CONFIG_GLOBAL` 等），未在本 PR 处理；本次改动相关测试在清理该环境变量后通过。
- 不涉及面板 UI，因此没有 Before/After 截图；消息格式的前后对照见 §4，隐私要求下不引用真实飞书会话内容。
