#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2mail.py —— 把 Markdown 报告转成「邮件客户端友好」的 HTML（只依赖标准库）。

背景（2026-11-18）：hmail 默认 `--html auto` 只把纯文本正文做启发式包装
（见 Hermes finance/scripts/mail_html.py）；长 Markdown 报告会被拆成若干 `<pre>`
文本块，阅读体验差。需要发长报告时，先用本脚本转成结构化 HTML，再：
    hmail --subject "标题" --body-file 摘要或纯文本版 --html 生成的.html --attach 可选

用法:
    python3 md2mail.py report.md -o report.html [--plain report.txt] [--title 标题]

输出:
  - `-o`   HTML 片段（`<div>` 包裹，样式全部内联；QQ / 网易 / Outlook 可读）
  - `--plain` 同时输出纯文本兜底版（multipart/alternative 的 text 部分）

支持: 标题、段落、无序/有序列表（含一层嵌套）、GFM 表格、围栏代码块、引用、
水平线、**粗体**、*斜体*、`行内代码`、[链接](url)、~~删除线~~。
不追求完整 CommonMark；报告类文档够用，且渲染失败会明确报错而不是静默丢内容。
"""
from __future__ import annotations

import argparse
import html
import re
import sys

# 邮件安全样式：全部内联；只用 table/div/pre，不用 flex/grid/外部 CSS。
S = {
    "wrap": ("font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',"
             "Arial,sans-serif;font-size:14px;color:#1f2328;line-height:1.65;max-width:900px"),
    "h1": "font-size:22px;margin:26px 0 10px;border-bottom:2px solid #e5e7eb;padding-bottom:6px",
    "h2": "font-size:18px;margin:24px 0 8px;border-bottom:1px solid #e5e7eb;padding-bottom:4px",
    "h3": "font-size:16px;margin:18px 0 6px",
    "h4": "font-size:14px;margin:14px 0 6px",
    "p": "margin:8px 0",
    "ul": "margin:6px 0 6px 22px;padding:0",
    "li": "margin:3px 0",
    "table": "border-collapse:collapse;width:100%;font-size:13px;margin:10px 0",
    "th": ("padding:6px 8px;background:#f2f4f7;border:1px solid #d8dde3;"
           "text-align:left;font-weight:600"),
    "td": "padding:6px 8px;border:1px solid #e6e8eb;vertical-align:top",
    "pre": ("background:#f8f9fa;border:1px solid #e6e8eb;padding:8px 10px;"
            "white-space:pre-wrap;word-break:break-word;"
            "font-family:ui-monospace,Consolas,monospace;font-size:12px;margin:8px 0"),
    "code": ("background:#f3f4f6;padding:1px 4px;border-radius:3px;"
             "font-family:ui-monospace,Consolas,monospace;font-size:12.5px"),
    "quote": ("border-left:3px solid #d1d5db;margin:8px 0;padding:4px 10px;color:#4b5563"),
    "hr": "border:none;border-top:1px solid #e5e7eb;margin:18px 0",
    "a": "color:#1d4ed8;text-decoration:none",
}


def inline(text: str) -> str:
    """行内标记 → HTML。先按反引号切分，代码段内不做格式化。"""
    parts = re.split(r"(`[^`]*`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            out.append(f'<code style="{S["code"]}">{html.escape(part[1:-1])}</code>')
            continue
        s = html.escape(part)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                   lambda m: f'<a href="{m.group(2)}" style="{S["a"]}">{m.group(1)}</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", s)
        out.append(s)
    return "".join(out)


def is_table_sep(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", line)) and "-" in line


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def render(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = [f'<div style="{S["wrap"]}">']
    i = 0
    list_stack: list[str] = []   # 'ul' / 'ol'
    list_indent: list[int] = []

    def close_lists() -> None:
        while list_stack:
            out.append(f"</{list_stack.pop()}>")
            list_indent.pop()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 围栏代码块
        if stripped.startswith("```"):
            close_lists()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append(f'<pre style="{S["pre"]}">{html.escape(chr(10).join(code))}</pre>')
            continue

        # 空行
        if not stripped:
            close_lists()
            i += 1
            continue

        # 水平线
        if re.match(r"^(\*{3,}|-{3,}|_{3,})$", stripped):
            close_lists()
            out.append(f'<hr style="{S["hr"]}">')
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            tag = f"h{min(level, 4)}"
            out.append(f'<{tag} style="{S.get(tag, S["h4"])}">{inline(m.group(2).strip())}</{tag}>')
            i += 1
            continue

        # 表格
        if "|" in stripped and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            close_lists()
            header = split_row(stripped)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(split_row(lines[i]))
                i += 1
            out.append(f'<table style="{S["table"]}"><tr>')
            out.extend(f'<th style="{S["th"]}">{inline(c)}</th>' for c in header)
            out.append("</tr>")
            for row in rows:
                out.append("<tr>")
                out.extend(f'<td style="{S["td"]}">{inline(c)}</td>' for c in row)
                out.append("</tr>")
            out.append("</table>")
            continue

        # 引用
        if stripped.startswith(">"):
            close_lists()
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].lstrip())
                i += 1
            out.append(f'<blockquote style="{S["quote"]}">{inline(" ".join(quote))}</blockquote>')
            continue

        # 列表（支持一层缩进）
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            indent = len(m.group(1))
            ordered = bool(re.match(r"\d", m.group(2)))
            kind = "ol" if ordered else "ul"
            if not list_stack:
                list_stack.append(kind)
                list_indent.append(indent)
                out.append(f'<{kind} style="{S["ul"]}">')
            elif indent > list_indent[-1] + 1:
                list_stack.append(kind)
                list_indent.append(indent)
                out.append(f'<{kind} style="{S["ul"]}">')
            elif indent < list_indent[-1] - 1:
                out.append(f"</{list_stack.pop()}>")
                list_indent.pop()
            out.append(f'<li style="{S["li"]}">{inline(m.group(3).strip())}</li>')
            i += 1
            continue

        # 段落（连续非空行合并）
        close_lists()
        para: list[str] = [stripped]
        i += 1
        while (i < len(lines) and lines[i].strip()
               and not re.match(r"^(#{1,6}\s|>|```|\s*([-*+]|\d+[.)])\s)", lines[i])
               and not (lines[i].strip().startswith("```"))
               and not (("|" in lines[i]) and (i + 1 < len(lines) and is_table_sep(lines[i + 1])))):
            para.append(lines[i].strip())
            i += 1
        out.append(f'<p style="{S["p"]}">{inline(" ".join(para))}</p>')

    close_lists()
    out.append("</div>")
    return "\n".join(out)


def to_plain(md: str) -> str:
    """Markdown → 可读纯文本（邮件 alt 部分）。表格按 | 分隔保留。"""
    out: list[str] = []
    in_code = False
    for line in md.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append("    " + line)
            continue
        s = line.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            text = m.group(2).strip()
            out.append("")
            out.append(text)
            out.append("=" * min(60, max(8, len(text) * 2)))
            continue
        s = re.sub(r"^\s*([-*+]|\d+[.)])\s+", "  - ", s)
        s = re.sub(r"^\s*>\s?", "  > ", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", s)
        s = re.sub(r"`([^`]*)`", r"\1", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", s)
        out.append(s)
    # 压缩连续空行
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Markdown → 邮件友好 HTML（内联样式）")
    ap.add_argument("input", help="输入 Markdown 文件")
    ap.add_argument("-o", "--output", help="输出 HTML 文件（默认 stdout）")
    ap.add_argument("--plain", help="同时输出纯文本兜底文件")
    ap.add_argument("--title", help="可选：写入 HTML 顶部标题（不参与转换）")
    args = ap.parse_args(argv)

    try:
        with open(args.input, encoding="utf-8") as f:
            md = f.read()
    except OSError as e:
        print(f"md2mail: 读取失败 {e}", file=sys.stderr)
        return 2

    body = render(md)
    if args.title:
        body = (f'<div style="{S["wrap"]}"><h1 style="{S["h1"]}">'
                f"{html.escape(args.title)}</h1></div>\n" + body)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"md2mail: HTML 已写入 {args.output}（{len(body)} 字符）", file=sys.stderr)
    else:
        sys.stdout.write(body)
    if args.plain:
        plain = to_plain(md)
        with open(args.plain, "w", encoding="utf-8") as f:
            f.write(plain)
        print(f"md2mail: 纯文本已写入 {args.plain}（{len(plain)} 字符）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
