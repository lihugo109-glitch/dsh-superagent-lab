# 能力单元外部调研：报告评审与落地建议

> 状态：评审建议（2026-11-13）。输入为外部调研工作单的交付报告 `docs/capability-unit-research-report.md`（778 行；原文入库，便于评审、转发与引用）。
> 关联：本工单 PR #24 的 `docs/teammate-residency-plan.md` §5「能力型 Unit / 生成与更新机制」；公用工具层实现见 `docs/hermes-tools-port.md`（PR #25 已合入）。

## 0. 结论

外部报告的核心结论可以采纳：**能力型 Unit 应做成「带授权的确定性路由 + 少量可复用会话专家」，不是照搬神经 MoE**。推荐的 B 方案（Git 版控能力卡注册表 + 混合 gating + Decision 冻结 + observe 灰度）与本部署现状兼容；报告指出的最大风险——把共享任务板的 `writeScopes` 当权限、`TeamId` 绑 root SessionId 导致跨工单能力身份缺失——与本工单实测一致。

## 1. 采纳的结论

1. **能力卡是唯一事实源，工单是唯一授权源，Router 只选择、不授权。**
2. **能力卡字段**：对齐 A2A AgentCard / MCP Tool 的可读字段，并补齐 host 校验用字段（`side_effect_level`、`mandate_scope`、`permissions`、`limits`、`implementation`、`owner`、`status`、`policy_ref`、`checksum`）。
3. **路由三层**：硬过滤（Mandate / effect / 路径 / egress / 预算）→ 显式指定优先 → 候选集内语义 top-1；Decision 以 `(ticket_id, capability@version)` 冻结，抑制抖动。
4. **灰度**：先 observe（只记 would-route，不执行），A/B 对照后再切 auto；退出判据沿用报告 §3 的四个核心假设。
5. **硬边界五维**：能力契约、权限与副作用（0–3 级）、资源与注意力预算、版本与废弃、数据访问；由 host 执行点强制，不写进提示词。
6. **跨主机 L0 受控代理**：参数化调用、白名单、结构化输出、超时限流、逐调用审计；agent 不拿通用 shell。文件搜索与邮件应作为 L0 工具，不升 L2。
7. **「何时不该用」6 条退出条件**：低频一次性、能力数少且稳定、类别无法准确分类、无 owner/评审流程、host 无法强制边界、失败成本高于指派成本。

## 2. 与本地部署的映射（重点）

| 报告结论 | 本地现状 | 判断 |
| --- | --- | --- |
| 文件搜索/邮件是 L0 工具而非会话专家 | 另一工单已落地 `hfind`/`hmail` 公用工具端口（PR #25 已合入，见 `docs/hermes-tools-port.md`）：绝对路径、结构化输出、邮件走 Hermes HTML 排版 | 一致，可直接作为前两张能力卡的 `implementation` |
| 共享任务板 `writeScopes` 是 advisory，不是权限 | 本工单实测：Team 工具注册在 agent 本地 scope、`team_task_*` 无授权语义 | 一致，报告警告成立 |
| `TeamId` 绑 root SessionId，跨工单能力身份需新增 | 本工单实测：每个顶层 worker Session 自成 team root，teammate 严格工单内 | 一致，是跨工单复用的第一障碍 |
| 跨主机代理需要 host 受控执行点 | 本部署 `hfind`/`hmail` 是脚本端口，暂无 host 级参数校验与预算执行点 | 需补，但可先用「能力卡 + 提示词 + 人工确认」过渡 |

## 3. 需要调整或收敛的点

1. **MVP 的成本顺序**：报告 MVP 的 S3/S4（Registry + Router 硬过滤 + Decision 日志）需要 host 代码改动，是成本最高的一步。建议拆两档：
   - v0（零代码）：能力卡 JSON + 校验脚本 + 团队提示词写明「候选能力与硬过滤规则」+ 人工确认；observe 记录写文件。先用 3 张卡跑。
   - v1（少量代码）：Decision 持久化、硬过滤执行点、调用级预算。
2. **能力卡字段精简**：报告 schema 有 20+ 必填字段，本部署先收敛到核心子集（建议 12 个：`id`、`name`、`version`、`kind`、`description`、`inputs`、`outputs`、`applicable`、`inapplicable`、`side_effect_level`、`permissions`、`implementation`、`owner`、`status`、`policy_ref`、`checksum` 中按需取舍），跑通 3 张卡再扩。
3. **效果 2/3 级的人工确认入口**：本部署只有飞书 thread 与面板，需要明确落点（建议飞书回复确认 + 审计记录），报告未指定界面。
4. **能力身份跨 root 的方案**：报告列为必须新增；本部署若要跨工单复用，需要新机制（专属常驻 team root 或全局能力注册表服务），建议作为 P4 的前置决策。

## 4. 建议的下一步（P4，待拍板）

- S1：能力卡 schema + 校验器（v0 零代码：脚本 + 示例 3 张卡）。
- S2：三张卡：`hfind` 文件搜索（effect 0）、`hmail` 邮件发送（effect 2/3，人工确认）、代码评审 L2（effect 1，fork teammate）。
- S3：`registry.json` + 别名（stable/canary）回滚演练。
- S4：observe 模式跑 10 张真实工单，收集误路由率、token、人工指派次数，对照「工单 + skill + 人工指派」基线；满足四个核心假设再谈 auto。

## 5. 报告本身的限制

- R5 为第三方文档站，R15 官方原文未取得公开 URL；报告已自行标注，未作为结论依据。
- 公开原型仓库 `deepseek-ai/dsh-superagent-prototype` 已核实为 public、MIT（README 声明 research prototype）。
- 报告中的 token / 成本数字为示例或待实测；S4 前不得宣称收益。

## 6. 与 PR #24 的关系

PR #24 定义 Unit 边界与常驻队友计划；本报告是其 §5「能力型 Unit」的具体设计输入。建议 PR #24 合并后，把本评审的 P4（S1–S2 先行）作为下一个工单/计划推进。
