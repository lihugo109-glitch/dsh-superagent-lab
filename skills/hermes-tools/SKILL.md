本机 Hermes 公用工具端口：在 WSL2 里直接使用 Windows 侧的 Everything 全盘文件检索（hfind）和邮件发送（hmail）。两者都是绝对路径脚本，在 bash 里直接用绝对路径调用，不依赖 PATH、cwd 或 HOME。

工具与绝对路径
- 文件检索：/root/work/state/tools/hermes-port/hfind
- 邮件发送：/root/work/state/tools/hermes-port/hmail

hfind 用法
  /root/work/state/tools/hermes-port/hfind <query> [-n N] [--path DIR] [--dirs|--all] [--size] [--json] [--count]
- query 用 Everything 语法（子串/通配，不按正则；正则加 --regex）；默认只列文件，默认 50 条。
- --path 可用 Linux 形式（/mnt/d/...）或 Windows 形式（D:\...、D:/...），自动转换；--size 输出 human<TAB>bytes<TAB>path；--json 输出单行 JSON。
- 输出是 Windows 路径（如 D:\hermes\...）；需要 POSIX 路径时用 wslpath -u 转换。
- 适合：跨盘找文件/资料/日志/仓库、按文件名或扩展名清点，比仓库内 find/glob 更快更全。不适合：按内容检索（用 grep/ripgrep）。
- WSL 内部路径（/root、/tmp 等）不在 Everything 索引，检索这些目录直接用 glob/grep，不要用 hfind（会 0 命中）。
- 退出码：0 成功；3 Everything 实例不可达；4 es.exe 调用失败；127 依赖缺失。长检索外层可套 timeout 60。

hmail 用法
  /root/work/state/tools/hermes-port/hmail --subject <标题> --body <正文>
  printf '%s' "$body" | /root/work/state/tools/hermes-port/hmail --subject <标题>
  /root/work/state/tools/hermes-port/hmail --subject <标题> --body-file <文件> [--html auto|none|<文件>] [--attach <文件>]...
- 收件人固定为脚本内置的用户邮箱，没有 --to 参数；正文优先 --body，其次 --body-file，最后 stdin。
- 默认 --html auto：正文经 Hermes 的 mail_html 排版成统一 HTML 外观（表格/结论条，纯文本版兜底），正文写简短中文摘要即可；--html none 发纯文本；--html <文件> 发现成 HTML。
- 长文（报告、文档、markdown、PR 说明）用 --body-file 发送全文；脚本从 WSL 侧读文件、经 UTF-8 stdin 交给 Windows Python，Linux 或 Windows 路径都支持。
- 附件模式（--attach）会改走 Hermes 纯文本通道（HTML 发信入口不支持附件），此时 --html 被忽略并在 stderr 提示。
- 退出码：0 成功；1 发送失败（SMTP）；2 参数/正文问题；127 依赖缺失；错误输出以 "hmail: " 开头。
- 不要用邮件发送凭据、私密 Feishu 内容或未脱敏日志。

何时使用
- 需要在本机找文件（尤其 D:/G: 等 Windows 盘）时先用 hfind 定位，再用 read/grep 细看。
- 交付结果、提出需要用户决策的问题或说明阻塞时，按 Delivery requirements 的邮件规则，由 Executor 用 hmail 把面向用户的内容发到邮箱（含 PR/交付物链接、用户可见结果、必要的下一步；长文发全文）；同一内容只发一封。普通进度、未完成草稿、内部排查一律不发邮件。
- 这两个绝对路径由部署确定；若路径不存在，先 ls /root/work/state/tools/hermes-port/ 确认，仍无则向用户说明公用工具层尚未部署，不要自行猜测或改用其他路径。
