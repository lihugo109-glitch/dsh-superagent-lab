#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""superagent-dashboard.py —— 从 SuperAgent 状态库生成单文件只读工作看板（HTML）。

背景：SuperAgent 现有面板（docs/005-panel.md）偏「管理/审计视角」：Source、Trigger、
Eval、Ticket 的完整流水都在，但不回答「我今天要推什么/卡在哪/下一步等谁」。本脚本
用只读方式读 `<stateDir>/orchestrator.sqlite`，生成一页「工作节拍」看板，可直接用
浏览器打开、或作为附件/邮件内容发送。它不写库、不调用 SuperAgent API、不改任何状态。

用法:
    python3 tools/superagent-dashboard.py \
        --db /root/work/state/orchestrator.sqlite \
        --out /tmp/superagent-dashboard.html
    python3 tools/superagent-dashboard.py --demo --out /tmp/demo.html   # 假数据演示

看板内容（全部来自本地库）:
    - 顶部统计：未结束工单数 / 进行中 / 等待人处理 / 24h 事件数
    - 需要你：报告 waiting/blocked、有 human_action 或 undelivered 输入的工单
    - 进行中：仍 open 且最近 Assignment 在跑/刚交报告的工单
    - 最近结束：已结束工单及其结果（PR 号、结束原因）
    - 最近事件：最近 10 条 Trigger（来源/时间/摘要）
    - 页脚：数据来源、生成时间、只读声明

只依赖标准库；HTML 全部内联样式（QQ/网易/Outlook/浏览器可读）。隐私：输出包含工单标题
与报告摘要，属于本机状态，不要把生成文件提交到公开仓库或发给无关人员。
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sqlite3
import sys

TIMEOUT = 10
CST = dt.timezone(dt.timedelta(hours=8))


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def local_time(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return t.astimezone(CST).strftime("%m-%d %H:%M")
    except ValueError:
        return iso[:16]


def report_of(assignments: list[dict]) -> dict:
    for assignment in reversed(assignments or []):
        report = assignment.get("report")
        if isinstance(report, dict) and report.get("state"):
            return report
    return {}


def last_assignment_state(assignments: list[dict]) -> str:
    if not assignments:
        return ""
    return str(assignments[-1].get("state") or "")


def source_of(ticket: dict) -> str:
    basis = (ticket.get("mandate") or {}).get("basis") or {}
    return str(basis.get("source") or "?")


def needs_person(ticket: dict) -> bool:
    report = report_of(ticket.get("assignments") or [])
    if report.get("state") in ("waiting", "blocked"):
        return True
    if report.get("human_action"):
        return True
    return bool(ticket.get("undelivered"))


def days_since(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max(0.0, (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 86400)


def classify(ticket: dict) -> str:
    if ticket.get("ended"):
        return "ended"
    if needs_person(ticket):
        return "attention"
    if days_since(ticket.get("updatedAt")) > 7:
        return "stale"
    if last_assignment_state(ticket.get("assignments") or []) in ("running", "pending"):
        return "active"
    return "stale"


def summary_line(report: dict, limit: int = 220) -> str:
    text = str(report.get("summary") or "")
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def pr_of(report: dict) -> str:
    number = report.get("pr_number")
    return f"PR #{number}" if number else ""


def load(db_path: str) -> dict:
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=TIMEOUT)
    con.row_factory = sqlite3.Row
    try:
        tickets = [json.loads(row["value"]) for row in con.execute("select value from ticket")]
        triggers = [json.loads(row["value"]) for row in con.execute("select value from trigger order by at desc limit 30")]
    finally:
        con.close()
    return {"tickets": tickets, "triggers": triggers}


def demo_data() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    iso = lambda minutes: (now - dt.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def ticket(tid, title, source, state, report_state, summary, minutes, pr=None, human_action=None, ended=None):
        report = {"state": report_state, "summary": summary}
        if pr:
            report["pr_number"] = pr
        if human_action:
            report["human_action"] = human_action
        item = {
            "id": tid, "title": title, "createdAt": iso(minutes + 30), "updatedAt": iso(minutes),
            "mandate": {"basis": {"source": source}},
            "assignments": [{"state": "running" if not ended else "ended", "report": report}],
            "inputs": [], "undelivered": [],
        }
        if ended:
            item["ended"] = {"at": iso(minutes), "reason": ended}
        return item

    return {"tickets": [
        ticket("demo-1", "示例：把报告邮件的长文改为 HTML 正文", "feishu", "running", "ready",
               "报告已用 HTML 正文重发；PR 等待人工审阅合并。", 12, pr=30),
        ticket("demo-2", "示例：为某个插件做兼容性评估", "feishu", "running", "waiting",
               "已定位到「半挂载」故障，需要你决定是否恢复挂载行并重启。", 45,
               human_action="是否恢复 dsh-harness-one 的挂载行并重启 DSH？"),
        ticket("demo-3", "示例：整理历史调研报告索引", "github", "ended", "ready",
               "索引已提交，PR 已合并。", 180, pr=29, ended="merged"),
    ], "triggers": [
        {"id": "t1", "at": iso(10), "text": "示例事件：继续把可视化方案写细一点"},
        {"id": "t2", "at": iso(60), "text": "示例事件：确认邮件格式改用 HTML"},
    ]}


def render(data: dict, db_label: str) -> str:
    tickets = data["tickets"]
    triggers = data["triggers"]
    now = dt.datetime.now(CST)
    day_ago = (now - dt.timedelta(hours=24)).astimezone(dt.timezone.utc)

    attention = [t for t in tickets if classify(t) == "attention"]
    active = [t for t in tickets if classify(t) == "active"]
    stale = [t for t in tickets if classify(t) == "stale"]
    open_tickets = [t for t in tickets if not t.get("ended")]
    ended = sorted([t for t in tickets if t.get("ended")],
                   key=lambda t: str(t.get("updatedAt") or ""), reverse=True)[:10]
    try:
        recent = [t for t in triggers
                  if dt.datetime.fromisoformat(str(t.get("at", "")).replace("Z", "+00:00")) >= day_ago]
    except ValueError:
        recent = triggers

    def stat(label: str, value, tone: str = "") -> str:
        color = {"warn": "#b45309", "ok": "#15803d", "info": "#1d4ed8"}.get(tone, "#1f2328")
        return (f'<div style="flex:1;min-width:150px;border:1px solid #e6e8eb;border-radius:8px;'
                f'padding:10px 12px;background:#fff">'
                f'<div style="font-size:11px;color:#6b7280">{esc(label)}</div>'
                f'<div style="font-size:22px;font-weight:600;color:{color}">{esc(value)}</div></div>')

    def ticket_rows(items: list[dict], show_next: bool) -> str:
        if not items:
            return '<p style="margin:10px 0;color:#6b7280;font-size:13px">（无）</p>'
        rows = []
        for t in items:
            report = report_of(t.get("assignments") or [])
            extra = " ".join(x for x in [pr_of(report), "等待输入" if needs_person(t) else ""] if x)
            next_text = summary_line(report) if show_next else esc(str((t.get("ended") or {}).get("reason") or report.get("state") or ""))
            rows.append(
                "<tr>"
                f'<td style="padding:7px 8px;border-bottom:1px solid #eef0f2;vertical-align:top">'
                f'{esc(t.get("title") or "(无标题)")}<div style="font-size:11px;color:#9ca3af">'
                f'{esc(source_of(t))} · {esc(t.get("id", "")[:8])} · {esc(local_time(t.get("updatedAt")))}</div></td>'
                f'<td style="padding:7px 8px;border-bottom:1px solid #eef0f2;font-size:12px;color:#374151;vertical-align:top">'
                f'{next_text}</td>'
                f'<td style="padding:7px 8px;border-bottom:1px solid #eef0f2;font-size:12px;color:#6b7280;vertical-align:top;white-space:nowrap">'
                f'{esc(extra)}</td>'
                "</tr>")
        head = ('<tr>'
                '<th style="padding:6px 8px;text-align:left;background:#f2f4f7;font-size:12px;border-bottom:2px solid #d8dde3">工单</th>'
                '<th style="padding:6px 8px;text-align:left;background:#f2f4f7;font-size:12px;border-bottom:2px solid #d8dde3">'
                + ("下一步 / 最新报告" if show_next else "结果") +
                '</th>'
                '<th style="padding:6px 8px;text-align:left;background:#f2f4f7;font-size:12px;border-bottom:2px solid #d8dde3">标记</th>'
                "</tr>")
        return ('<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;'
                'font-size:13px;margin-top:8px">' + head + "".join(rows) + "</table>")

    def section(title: str, body: str, note: str = "") -> str:
        note_html = f'<div style="font-size:11px;color:#9ca3af;margin:-2px 0 4px">{esc(note)}</div>' if note else ""
        return (f'<h2 style="font-size:17px;margin:26px 0 4px;border-bottom:1px solid #e5e7eb;padding-bottom:4px">{esc(title)}</h2>'
                f"{note_html}{body}")

    recent_rows = "".join(
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #eef0f2;font-size:12px;color:#6b7280;white-space:nowrap">'
        f'{esc(local_time(t.get("at")))}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eef0f2;font-size:12.5px;color:#374151">'
        f'{esc(" ".join(str(t.get("text") or "").split())[:180])}</td></tr>'
        for t in triggers[:10])
    recent_table = ('<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;margin-top:8px">'
                    + recent_rows + "</table>") if recent_rows else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SuperAgent 工作看板</title></head>
<body style="margin:0;padding:24px;background:#f7f8fa">
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',Arial,sans-serif;
            font-size:14px;color:#1f2328;line-height:1.6;max-width:1000px;margin:0 auto;
            background:#fff;border:1px solid #e6e8eb;border-radius:10px;padding:22px 24px">
  <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">
    <h1 style="font-size:21px;margin:0">SuperAgent 工作看板</h1>
    <div style="font-size:12px;color:#6b7280">生成于 {esc(now.strftime('%Y-%m-%d %H:%M'))} · 只读</div>
  </div>
  <p style="font-size:12.5px;color:#6b7280;margin:6px 0 14px">
    回答三个问题：<b>需要你处理什么</b>、<b>正在推进什么</b>、<b>最近发生了什么</b>。
    数据来自本机状态库（{esc(db_label)}），不含操作按钮，不会改任何状态。</p>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 4px">
    {stat("未结束工单", len(open_tickets), "info")}
    {stat("进行中", len(active))}
    {stat("需要你", len(attention), "warn")}
    {stat("长期未动", len(stale))}
    {stat("24h 事件", len(recent), "ok")}
  </div>
  {section("需要你", ticket_rows(attention, show_next=True), "报告 waiting/blocked、带 human_action 或还有未投递输入")}
  {section("进行中", ticket_rows(active, show_next=True), "最近 Assignment 在跑或刚交报告；「下一步」取最新报告摘要")}
  {section("长期未动", ticket_rows(stale, show_next=True), "未结束但超过 7 天没更新：建议清理、重开或结束")}
  {section("最近结束", ticket_rows(ended, show_next=False), "已结束工单；「结果」取结束原因/报告状态")}
  {section("最近事件", recent_table, "最近 10 条 Trigger（即你的消息或外部事件）")}
  <p style="font-size:11px;color:#9ca3af;margin:22px 0 0;border-top:1px solid #eef0f2;padding-top:10px">
    只读看板 · 数据源 <code>{esc(db_label)}</code> · 由 tools/superagent-dashboard.py 生成。
    输出含工单标题与报告摘要，请勿提交到公开仓库或转发给无关人员。</p>
</div>
</body></html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="从 SuperAgent 状态库生成单文件只读工作看板")
    ap.add_argument("--db", default="/root/work/state/orchestrator.sqlite",
                    help="orchestrator.sqlite 路径（只读打开）")
    ap.add_argument("--out", help="输出 HTML 路径（默认 stdout）")
    ap.add_argument("--demo", action="store_true", help="使用内置假数据生成演示看板")
    args = ap.parse_args(argv)

    if args.demo:
        data, label = demo_data(), "demo（假数据）"
    else:
        try:
            data, label = load(args.db), args.db
        except (OSError, sqlite3.Error, json.JSONDecodeError) as e:
            print(f"superagent-dashboard: 读取 {args.db} 失败：{e}", file=sys.stderr)
            return 2
    page = render(data, label)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"superagent-dashboard: 已写入 {args.out}（{len(page)} 字符）", file=sys.stderr)
    else:
        sys.stdout.write(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
