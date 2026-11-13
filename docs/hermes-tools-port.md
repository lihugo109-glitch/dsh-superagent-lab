# SuperAgent 公用工具层与邮件转发交付（Hermes 工具端口）

> 工单：`hermes-tools-bridge-d28722e9ee55`（邮件转发交付与公用工具层）
> 环境：WSL2（Ubuntu-24.04，Windows 11 主机）上的 DSH SuperAgent 部署；Windows 盘挂载在 `/mnt/c`…`/mnt/h`
> 时间：2026-11-13

## 0. 结论

**可行，且已在本机部署并验证。**

- **跨文件系统共用 Hermes 工具可行**：WSL 里的 agent 会话可以直接运行 Windows 侧程序（Everything CLI、Windows Python 发信脚本）。固定开销是 WSL→Windows 进程互操作约 **0.07–0.09 s**；一次带真实查询的 Everything 检索端到端约 **0.22 s**，一次邮件发送端到端约 **1.1 s**（含 SMTP 往返）。不需要在 WSL 内装 Python/Node，也不依赖 `HOME`、`cwd`、`PATH`。
- **公用工具层已落地**：两个绝对路径端口 `hfind`（Everything 全盘检索）与 `hmail`（邮件发送，默认走 Hermes 的 HTML 排版、纯文本兜底），安装在 `<stateDir>/tools/hermes-port/`，并注册为团队技能 `hermes-tools`。
- **邮件转发交付已生效**：团队提示词 `delivery` 段新增「需要告诉用户的内容一律走邮件（邮箱看全文、IM 只作提示）」规则；Executor 在报告 `ready`、提出需要人决策的问题或说明阻塞时，把面向用户的内容用 `hmail` 发到用户邮箱（长文用 `--body-file` 发全文）。
- **不是 UI 改动**：没有改任何前端/面板代码，因此没有 Before/After 截图；面板设置页会因数据驱动自动多出 `skill/hermes-tools` 一行，这是既有通用渲染，不是 UI 代码改动。

## 1. 需求

用户（Feishu 侧）提出：

1. 不习惯目前以 GitHub 为主的交付形式，希望结果能**通过邮件转发**；IM 接收面太小，**需要看的内容走邮箱**。
2. SuperAgent 内部建立**公用工具层**，或给外部 Hermes 工具成品做一个**快捷使用端口**；典型例子是让 SuperAgent 使用 Windows 的 Everything（`D:\HermesTools\tools\es.exe`，CLI）。
3. Hermes 侧已有邮件脚本；邮件相关可以先用 Everything CLI 检索 Hermes 资产定位（本次已定位到发信脚本与排版模块）。
4. 后续补充：Hermes 有邮件排版工具和 HTML，要求邮件使用该排版。
5. 后续补充：需要告诉用户的东西都尽量通过邮件发送（例如既有长文档内容），IM 只当提示。

## 2. 跨文件系统评估

### 2.1 能力

- `es.exe`（Everything CLI，`D:\HermesTools\tools\es.exe`）与 Windows Python（`D:\hermes\tools\vizenv\Scripts\python.exe`）在 WSL bash 里可直接执行，参数给 Windows 路径即可。
- Everything 索引覆盖 Windows 盘（C–H）；**WSL 内部路径（`/root`、`/tmp` 等）不在索引内**，这些目录仍用 `glob`/`grep`。
- Hermes 的发信脚本（`D:\hermes\scripts\send-mail.py`、`D:\hermes\profiles\finance\scripts\send_mail.py`）自己读取本机凭据文件（凭据路径与内容不在本仓库公开），agent 只调脚本，不读、不打印、不落盘凭据。

### 2.2 实测数据（5 次中位数）

| 操作 | 耗时 | 说明 |
| --- | --- | --- |
| Windows Python 启动（基线） | 0.071 s | 互操作固定开销 |
| `es.exe` 直接查询（ASCII / 中文） | 0.096 / 0.099 s | 索引查询本身几乎不耗时 |
| `everything-search.py` 包装器（ASCII / 中文） | 0.176 / 0.179 s | 带 UTF-8 解码、实例探测 |
| `hfind` 端口（ASCII / 中文） | 0.215 / 0.223 s | 含 bash、路径转换、CR 过滤 |
| `hmail` 发信（纯文本 / HTML） | 1.143 / 1.108 s | 主要是 SMTP 往返 |

### 2.3 结论

可行，且开销可接受（检索亚秒级、发信约 1 秒）。需要注意的跨文件系统坑：

- **环境变量默认不过界**：WSL 环境变量不会自动传给 Windows 进程，需要用 `WSLENV` 显式透传（端口已处理，调用方无需关心）。
- **编码**：`es.exe` 原生输出是 GBK，中文在 bash 里会乱码；端口强制 Windows Python 用 `-X utf8`，中文路径/正文正常。不要在端口外直接 `cat` 裸 `es.exe` 输出再按 UTF-8 解码。
- **路径**：端口接受 `/mnt/d/...` 与 `D:\...`、`D:/...` 两种写法并自动转换；相对路径按调用时 PWD 先绝对化。
- **cwd**：WSL 的 Linux cwd 不是合法 Windows cwd，端口内部先切到 Windows 盘目录再启动 exe，避免 UNC 警告。
- **Windows 进程读不到 Linux 路径**：邮件正文一律由 WSL 侧读出后经 stdin 交给 Windows Python；`--body-file`、`--html`、`--attach` 的 WSL 内部文件会先复制到 `C:\Windows\Temp\hmail.XXXXXX` 再传入，结束（含失败）自动清理。

## 3. 公用工具层设计

### 3.1 位置与权限

```
/root/work/state/tools/hermes-port/        # <stateDir>/tools/hermes-port/
├── hfind   # Everything 检索端口，755
├── hmail   # 邮件发送端口，755
└── install.sh
```

- **不放 `worker-bin`**：`dsh-superagent` 启动时会重写 `<stateDir>/worker-bin`，发现非它写入的文件会停 setup；`<stateDir>/tools/` 是独立子目录，不受影响（部署只检查 `worker-bin` 与 `worker-gitconfig`）。
- 端口是绝对路径脚本，不依赖 `PATH`、`HOME`、`cwd`，在隔离环境（`HOME=stateDir`、`PATH` 只有 worker-bin）下同样可用。

### 3.2 `hfind` 契约

```bash
hfind <query> [-n N] [--path DIR] [--parent DIR] [--regex] [--dirs|--all] [--size]
        [--offset N] [--sort KEY] [--asc] [--count] [--total-size] [--json] [--case]
        [--instance NAME] [--es PATH] [--list-instances]
```

- `query` 用 Everything 语法（子串/通配）；正则加 `--regex`（端口转成 Everything 的 `regex:` 前缀，规避 es 1.1.0.38 的 `-regex` 失效）。
- 输出：默认每行一个 Windows 路径；`--size` 为 `human<TAB>bytes<TAB>path`；`--json` 单行 JSON；`--count` 一个整数。
- 退出码：`0` 成功；`2` 参数错误；`3` Everything 实例不可达；`4` es.exe 调用失败；`127` 依赖缺失。
- 常见用法：

```bash
hfind "口腔" -n 5
hfind "*.pdf" --path D:/hermes --count
hfind --parent /mnt/d/hermes --dirs --size -n 5
hfind "send-mail.py" --path D:/hermes
```

### 3.3 `hmail` 契约

```bash
hmail --subject <标题> [--body <正文> | --body-file <文件>]
      [--html auto|none|<文件>] [--attach <路径>]... [--test]
```

- 收件人固定为发件人本人（Hermes 脚本内置），**没有 `--to`**；凭据由 Hermes 脚本自读，端口不接触。
- 正文来源优先级：`--body` > `--body-file` > stdin；长文推荐 `--body-file` 或 stdin（绕开 Windows 命令行长度限制）。
- **默认 HTML 排版**：`--html auto` 调 Hermes 的 `send_mail.py`，用 `mail_html.py` 把纯文本包成统一 HTML 外观（结论条/表格，`multipart/alternative` 保留纯文本兜底）；含 `##` 标题或表格的 markdown 正文走等宽保真，结构不被美化破坏。`--html none` 发纯文本，`--html <文件>` 发自定义 HTML。
- **附件与 HTML 二选一**：Hermes 的 HTML 发信入口不支持附件；带 `--attach` 时自动改走纯文本通道并在 stderr 提示「附件模式跳过 HTML 排版」。
- 退出码：`0` 成功；`1` 发送失败（SMTP）；`2` 参数/正文问题；`127` 依赖缺失。

## 4. 复用的 Hermes 资产（只调用、不修改）

| 资产 | 用途 |
| --- | --- |
| `D:\HermesTools\tools\es.exe` | Everything CLI 本体 |
| `D:\hermes\scripts\everything-search.py` | UTF-8 包装（中文、实例探测、JSON/统计） |
| `D:\HermesTools\skills\file-search\everything-file-search\SKILL.md` | Everything 用法/坑的原始知识 |
| `D:\hermes\scripts\send-mail.py` | 纯文本发信入口（支持附件） |
| `D:\hermes\profiles\finance\scripts\send_mail.py` | 通用发信入口（`--html auto/none/<path>`） |
| `D:\hermes\profiles\finance\scripts\mail_html.py` | 邮件 HTML 排版（只用 table + 内联样式，邮箱客户端兼容） |

`hmail` 只是把「选通道 + 路径转换 + 编码 + stdin」封装起来，**不复制、不改写** Hermes 脚本，凭据纪律不变。

## 5. 邮件转发交付规则（团队提示词）

在团队提示词 `delivery` 段追加（当前部署 revision 5；config 为纯追加，`communication`/`scope` 未动）：

> 需要告诉用户的内容一律走邮件（用户明确要求：邮箱看全文，IM 只作提示）。Executor 在报告 ready，或用 human_action 提出需要人决策的问题、说明阻塞时，必须用 `/root/work/state/tools/hermes-port/hmail` 把面向用户的内容发到用户邮箱：短结果用 `--subject/--body`；长文（报告、文档、markdown、PR 说明）用 `--body-file <文件>` 发送全文，hmail 默认经 Hermes 排版成 HTML（含纯文本兜底），邮件里保留交付物/PR 链接与必要的下一步。收件人由 hmail 固定，不要指定收件人。同一内容只发一封，不要重复；主 Session 在 IM 只保留一句指针和链接，不再发同类邮件；普通进度、未完成草稿和内部排查不发邮件。Executor 的 bash 前台命令 5 秒后会转入后台任务：若 hmail 转入后台，等它的 job 结束并确认退出码 0，不要重复发送。

设计取舍：

- **由 Executor 发**：内容（长文档/报告）由 Executor 产出，它知道该发哪份、文件在哪；主 Session 保持「一句指针 + 链接」的 IM 交付，职责不重叠。
- **单点发送 + 同一内容一封**：避免主 Session 与 Executor 双发；ready 报告 relay 本身有幂等键，重试不会重复触发交付。
- **只发「需要用户阅读/决策」的内容**：普通进度、未完成草稿、内部排查不打扰邮箱。
- **行为验证**：提示词保存后不重启，下一次模型请求即生效（见 §7）；邮件通道本身已用真实测试邮件验证。

## 6. 安装与回滚

### 6.1 安装/复装

```bash
# 只读自检（依赖是否存在、端口能否运行；不发信）
tools/hermes-port/install.sh --check

# 安装（默认 /root/work/state，可用 --state-dir 或 DSH_SUPERAGENT_STATE_DIR 覆盖）
tools/hermes-port/install.sh
```

### 6.2 提示词配置的保存与回滚

管理 API 只允许 loopback + 同源（`Host: 127.0.0.1:3082`，请求头 `x-orchestrator-request: 1`）：

```bash
BASE=http://127.0.0.1:3082/orchestrator/api
H='x-orchestrator-request: 1'

# 读当前配置与 revision
curl -s -H "$H" "$BASE/prompts" -o /tmp/prompts-now.json

# 预览（只校验/组装，不保存；body 是裸 config）
curl -s -X POST -H "$H" -H 'content-type: application/json' \
  --data-binary @/tmp/new-config.json "$BASE/prompts/preview"

# 保存（新建 revision，不重启；409 = baseRevision 过期，重读后重放）
# body: {"config": <完整 config>, "baseRevision": <当前 revision>}
curl -s -X PUT -H "$H" -H 'content-type: application/json' \
  --data-binary @/tmp/prompts-save.json "$BASE/prompts"

# 回滚：GET /prompts?revision=N 取旧 config，再以当时 revision 为 baseRevision PUT
curl -s -H "$H" "$BASE/prompts?revision=2"
```

本工单的三次保存：revision 3（新增 `hermes-tools` 技能 + 首版邮件转发规则）、revision 4（按用户要求改为 Executor 发信 + 邮件优先内容交付）、revision 5（修正技能文本笔误）。回滚到任一旧 revision 即可，历史版本永久保留。

## 7. 验证记录

| 项目 | 结果 |
| --- | --- |
| `hfind` 功能 | 39 组用例：中文/ASCII 查询、`--json/--count/--total-size/--dirs/--parent/--size/--regex`、Linux↔Windows 路径一致、任意 cwd、隔离环境全部 rc=0 |
| `hfind` 性能 | 0.215 s（ASCII）/ 0.223 s（中文），见 §2.2 |
| `hmail` 组装 | 20 项假环境测试（`--html auto/none/<文件>`、stdin、`--body-file`、附件通道切换、退出码 0/1/2/127、临时目录清理）全部通过，零残留 |
| 真实发信 | 3 封测试邮件（2 封要求的验证 + 1 封测试期间误发，均已在工单内披露）；HTML 验证邮件 rc=0、HTML=有、端到端 1.108 s；用户确认收到纯文本与 HTML 排版邮件 |
| 配置校验 | `POST prompts/preview` HTTP 200；orchestrator/worker 两角色提示词均含新规则；5 个负例（保留技能名/非法名/未知键/超长/错误包体）均 400 |
| 生效机制 | 保存不重启；`GET /prompts` 显示编排会话与 worker 均绑定新 revision；本工单 worker 会话在保存后的下一次模型请求即获得 `dsh-superagent-hermes-tools` 技能（会话技能目录实测可见） |
| 部署一致性 | `<stateDir>/tools/hermes-port/{hfind,hmail}` 与本仓库副本 sha256 一致（hfind `4ebda355…`，hmail `7b7968…`） |

## 8. 风险与限制

1. **依赖 Windows 侧设施**：Everything 需在运行（实例名自动探测，失败退出码 3）；Windows Python 与 Hermes 脚本路径需存在（缺失时端口报 127）。WSL 内部路径不在 Everything 索引。
2. **`stateDir` 变化**：技能文本写死 `<stateDir>/tools/hermes-port/` 绝对路径；部署位置变化时需重装端口并重存技能文本（文本内已写「路径不存在先 ls 确认，仍无则说明未部署」的兜底）。
3. **HTML 与附件不可兼得**：附件模式自动降级纯文本并提示；需要 HTML 就不要附件。
4. **SMTP 成功 ≠ 进收件箱**：QQ 邮箱有限流/垃圾箱策略；`hmail` 只保证把信交给 SMTP。失败时保留错误类别（不含凭据），可重试一次，但**不要在「不确定是否已发」时重复发送**。
5. **提示词行为**：规则通过团队提示词生效，已验证配置组���、会话绑定和技能注册；单个工单实际发什么内容仍取决于模型判断（例如是否算「需要用户阅读」），本次未对每个未来工单逐一实测。
6. **邮件范围**：只发「需要用户阅读/决策」的内容；普通进度、未完成草稿、内部排查不占用邮箱。
7. **未修改 Hermes 侧**：端口只是调用；Hermes 脚本升级后若参数/输出变化，需要回归 `findings-tool-port.md` 中的契约测试。

## 9. 相关文件

- `tools/hermes-port/hfind`、`tools/hermes-port/hmail`、`tools/hermes-port/install.sh`
- `skills/hermes-tools/SKILL.md`（注册为团队技能 `hermes-tools` 的正文）
- 工单原始实测证据（本地 ticket 目录 `artifacts/`）：`findings-tool-port.md`（546 行实测）、`findings-bridge.md`（620 行机制调研）、`evidence/`（11 个原始日志）
