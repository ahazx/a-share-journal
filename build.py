#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股每日复盘 · 期刊构建脚本

用法:
    python3 build.py                       # 默认从自动化 outputs 目录读取
    python3 build.py --src /path/to/mds    # 指定源目录

做三件事:
1. 扫描源目录里所有 "A股复盘_YYYYMMDD*.md"
2. 逐份渲染成期刊版式 HTML -> issues/YYYY-MM-DD.html
3. 重建 index.html 目录页（按日期倒序、自动编期号）+ README.md 索引
"""

import argparse
import html
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES = ROOT / "issues"
DEFAULT_SRC = Path("/Users/zhangxu/WorkBuddy/automation-2026-09-21-16-00-31/outputs")

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ---------------------------------------------------------------- 通用样式
BASE_CSS = """
:root{
  --paper:#f6f3ee; --card:#fffdf9; --ink:#1c1a17; --ink2:#413c35; --muted:#8a8279;
  --line:#e2dbd0; --line2:#cfc6b8; --red:#c0392b; --redbg:#fdf1ef;
  --green:#1a7f4b; --greenbg:#eef7f1; --gold:#8c6b2f;
  --serif:"Songti SC","Source Han Serif SC","Noto Serif CJK SC",Georgia,serif;
  --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:var(--sans); font-size:15.5px; line-height:1.85;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit;text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}

/* ---------- 报头 ---------- */
.masthead{border-bottom:3px double var(--ink);background:var(--card);padding:26px 0 18px}
.masthead .wrap{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}
.brand h1{
  font-family:var(--serif);font-size:34px;line-height:1.15;margin:0;
  letter-spacing:2px;font-weight:700;
}
.brand .sub{
  font-family:var(--sans);font-size:11px;letter-spacing:3.5px;color:var(--muted);
  text-transform:uppercase;margin-top:7px;
}
.masthead .meta{text-align:right;font-size:12.5px;color:var(--muted);line-height:1.9}
.masthead .meta b{color:var(--ink);font-family:var(--serif);font-size:22px;letter-spacing:1px}

/* ---------- 版面骨架 ---------- */
.layout{display:grid;grid-template-columns:210px minmax(0,1fr);gap:44px;padding:38px 0 80px}
@media(max-width:940px){.layout{grid-template-columns:1fr;gap:20px;padding-top:26px}}

/* ---------- 目录 ---------- */
.toc{position:sticky;top:24px;align-self:start;font-size:13px}
.toc .toc-t{font-size:10.5px;letter-spacing:2.5px;color:var(--muted);margin-bottom:12px}
.toc ol{list-style:none;margin:0;padding:0;border-left:2px solid var(--line)}
.toc li{margin:0}
.toc a{display:block;padding:6px 0 6px 12px;margin-left:-2px;border-left:2px solid transparent;color:var(--ink2);line-height:1.5}
.toc a:hover{color:var(--red);border-left-color:var(--red);background:var(--redbg)}
@media(max-width:940px){
  .toc{position:static;border:1px solid var(--line);background:var(--card);padding:14px 16px}
  .toc ol{columns:2;column-gap:18px}
  .toc a{font-size:12.5px}
}

/* ---------- 正文 ---------- */
article{max-width:820px}
.issue-head{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:8px}
.issue-head .kicker{font-size:11.5px;letter-spacing:2px;color:var(--red);margin-bottom:6px}
.issue-head h1{font-family:var(--serif);font-size:30px;line-height:1.3;margin:0 0 8px;letter-spacing:.5px}
.issue-head .dateline{font-size:12.5px;color:var(--muted)}

h2{
  font-family:var(--serif);font-size:21px;margin:44px 0 16px;padding-bottom:9px;
  border-bottom:1px solid var(--line2);letter-spacing:.5px;
}
h2::before{content:"";display:inline-block;width:5px;height:15px;background:var(--red);margin-right:10px;vertical-align:-2px}
h3{font-family:var(--serif);font-size:17px;margin:30px 0 10px;color:var(--ink)}
h4{font-size:14.5px;margin:22px 0 8px;color:var(--ink2)}
p{margin:0 0 13px;text-align:justify}
strong{font-weight:700;color:#000}
em{font-style:normal;background:linear-gradient(transparent 62%,#f3e2b8 62%);padding:0 1px}
hr{display:none}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.88em;background:#efe9df;padding:1px 5px;border-radius:3px}

/* 首段引言 */
blockquote{
  margin:0 0 26px;padding:14px 18px;background:var(--card);border-left:3px solid var(--line2);
  font-size:12.8px;line-height:1.8;color:var(--muted);
}
blockquote p{margin:0 0 6px;text-align:left}
blockquote p:last-child{margin:0}

/* 列表 */
ul,ol{margin:0 0 16px;padding-left:22px}
li{margin:0 0 9px;line-height:1.8}
li::marker{color:var(--muted)}
ul ul,ol ul,ul ol{margin:8px 0 0}

/* 表格 */
.tbl{overflow-x:auto;margin:16px 0 24px;border:1px solid var(--line);background:var(--card)}
table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.6;font-variant-numeric:tabular-nums}
thead th{
  background:#efe9df;color:var(--ink);font-weight:600;text-align:left;
  padding:9px 12px;border-bottom:1px solid var(--line2);white-space:nowrap;font-size:12.5px;
}
tbody td{padding:9px 12px;border-bottom:1px solid #f0ebe3;vertical-align:top}
tbody tr:nth-child(even){background:#fcfaf6}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fbf4ec}
td:first-child{font-weight:600;white-space:nowrap}
.num{font-variant-numeric:tabular-nums}

/* 数字着色（红涨绿跌） */
.up{color:var(--red);font-weight:600}
.down{color:var(--green);font-weight:600}
.flat{color:var(--muted)}

/* 章节内小节 */
article>b,article>strong{display:block}

/* 页脚 */
.foot{border-top:3px double var(--ink);margin-top:70px;padding:22px 0 60px;font-size:12px;color:var(--muted)}
.foot .wrap{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}

/* 上下期 */
.pager{display:flex;justify-content:space-between;gap:14px;margin-top:56px;padding-top:20px;border-top:1px solid var(--line)}
.pager a{flex:1;border:1px solid var(--line);background:var(--card);padding:12px 16px;font-size:13px;transition:.15s}
.pager a:hover{border-color:var(--red);color:var(--red)}
.pager .dir{display:block;font-size:10.5px;letter-spacing:2px;color:var(--muted);margin-bottom:3px}
.pager a.next{text-align:right}

@media print{
  body{background:#fff;font-size:11.5pt}
  .toc,.pager,.masthead .meta{display:none}
  .layout{grid-template-columns:1fr;padding:0}
  h2{break-after:avoid}
  .tbl{overflow:visible;break-inside:avoid}
}
"""

INDEX_CSS = """
.hero{margin:34px 0 10px}
.hero .tag{display:inline-block;font-size:11px;letter-spacing:2px;color:#fff;background:var(--red);padding:3px 9px;margin-bottom:14px}
.hero h2{font-family:var(--serif);font-size:30px;line-height:1.35;margin:0 0 14px;letter-spacing:.5px;display:block;border:none;padding:0}
.hero h2::before{display:none}
.hero .lead{font-size:15px;color:var(--ink2);line-height:1.9;margin:0 0 20px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px}
.chip{
  display:inline-flex;align-items:baseline;gap:6px;border:1px solid var(--line2);background:var(--card);
  padding:5px 11px;font-size:12.5px;font-variant-numeric:tabular-nums;
}
.chip .k{color:var(--muted);font-size:11.5px}
.hero .go{display:inline-block;background:var(--ink);color:#fff;padding:11px 26px;font-size:13.5px;letter-spacing:1px}
.hero .go:hover{background:var(--red)}

.sect-t{display:flex;align-items:center;gap:14px;margin:52px 0 22px;font-family:var(--serif);font-size:19px}
.sect-t::after{content:"";flex:1;height:1px;background:var(--line2)}

.year{margin:30px 0 12px;font-size:12px;letter-spacing:2.5px;color:var(--muted)}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:16px}
.card{
  border:1px solid var(--line);background:var(--card);padding:18px 18px 16px;display:flex;
  flex-direction:column;gap:9px;transition:.16s;position:relative;
}
.card:hover{border-color:var(--red);transform:translateY(-2px);box-shadow:0 8px 20px rgba(80,60,40,.07)}
.card .no{font-family:var(--serif);font-size:11px;color:var(--muted);letter-spacing:1.5px}
.card .date{font-family:var(--serif);font-size:19px;line-height:1.2}
.card .date small{font-family:var(--sans);font-size:11.5px;color:var(--muted);margin-left:7px;letter-spacing:0}
.card .hl{font-size:13.5px;line-height:1.7;color:var(--ink2);flex:1;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .chips{margin:0;gap:5px}
.card .chip{padding:3px 7px;font-size:11.5px}
.card.weekend .date{color:var(--muted)}
.card.weekend::after{content:"休市";position:absolute;top:0;right:0;background:#efe9df;color:var(--muted);font-size:10px;padding:2px 8px;letter-spacing:1px}
@media(max-width:640px){
  .hero h2{font-size:23px}
  .grid{grid-template-columns:1fr}
}
"""

# ---------------------------------------------------------------- Markdown 解析
NUM_RE = re.compile(r"(?<![\w.])[+\-]?\d+(?:\.\d+)?(?:%|亿|万|倍|pct)")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline(text: str, color_nums: bool = True) -> str:
    """行内格式：代码 / 加粗 / 数字着色"""
    out = esc(text)
    out = re.sub(r"`([^`]+?)`", lambda m: f"<code>{m.group(1)}</code>", out)
    out = re.sub(r"\*\*(.+?)\*\*", lambda m: f"<strong>{m.group(1)}</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", lambda m: f"<em>{m.group(1)}</em>", out)
    if color_nums:
        def repl(m):
            tok = m.group(0)
            if tok.startswith("+"):
                return f'<span class="up">{tok}</span>'
            if tok.startswith("-"):
                return f'<span class="down">{tok}</span>'
            return tok
        # 只对表格/普通文本里的正负号数字着色，避免污染纯数字
        out = NUM_RE.sub(repl, out)
    return out


def split_row(line: str):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_sep(line: str) -> bool:
    s = line.strip()
    return bool(re.fullmatch(r"\|?[\s:\-|]+\|?", s)) and "-" in s


def md_to_html(md: str):
    """返回 (html_body, toc_list)"""
    lines = md.split("\n")
    out, toc = [], []
    i, n = 0, len(lines)
    para_buf = []
    h2_idx = 0

    def flush_para():
        nonlocal para_buf
        if para_buf:
            txt = " ".join(x.strip() for x in para_buf).strip()
            if txt:
                out.append(f"<p>{inline(txt)}</p>")
            para_buf = []

    while i < n:
        line = lines[i]
        raw = line.rstrip()
        s = raw.strip()

        # 空行
        if not s:
            flush_para()
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush_para()
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para()
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                out.append(f'<h1 class="md-h1">{inline(text, False)}</h1>')
            elif level == 2:
                hid = f"sec{h2_idx}"
                h2_idx += 1
                toc.append((hid, text))
                out.append(f'<h2 id="{hid}">{inline(text, False)}</h2>')
            elif level == 3:
                out.append(f"<h3>{inline(text, False)}</h3>")
            else:
                out.append(f"<h4>{inline(text, False)}</h4>")
            i += 1
            continue

        # 表格
        if s.startswith("|") and i + 1 < n and is_sep(lines[i + 1]):
            flush_para()
            head = split_row(s)
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(split_row(lines[i]))
                i += 1
            th = "".join(f"<th>{inline(c, False)}</th>" for c in head)
            trs = []
            for r in body:
                r = (r + [""] * len(head))[:len(head)]
                tds = "".join(f"<td>{inline(c)}</td>" for c in r)
                trs.append(f"<tr>{tds}</tr>")
            out.append(
                f'<div class="tbl"><table><thead><tr>{th}</tr></thead>'
                f"<tbody>{''.join(trs)}</tbody></table></div>"
            )
            continue

        # 引用块
        if s.startswith(">"):
            flush_para()
            q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = "".join(
                f"<p>{inline(x)}</p>" for x in (y.strip() for y in q) if x
            )
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # 无序列表
        if re.match(r"^[-*+]\s+", s):
            flush_para()
            items = []
            while i < n and re.match(r"^[-*+]\s+", lines[i].strip()):
                item = re.sub(r"^[-*+]\s+", "", lines[i].strip())
                # 续行（缩进但不属于新列表项）
                i += 1
                while (
                    i < n
                    and lines[i].strip()
                    and not re.match(r"^[-*+]\s+", lines[i].strip())
                    and not re.match(r"^\d+[.)]\s+", lines[i].strip())
                    and not lines[i].strip().startswith(("#", "|", ">"))
                    and (lines[i].startswith("  ") or lines[i].startswith("\t"))
                ):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(item)}</li>")
            out.append(f"<ul>{''.join(items)}</ul>")
            continue

        # 有序列表
        if re.match(r"^\d+[.)]\s+", s):
            flush_para()
            items = []
            while i < n and re.match(r"^\d+[.)]\s+", lines[i].strip()):
                item = re.sub(r"^\d+[.)]\s+", "", lines[i].strip())
                i += 1
                while (
                    i < n
                    and lines[i].strip()
                    and not re.match(r"^[-*+]\s+", lines[i].strip())
                    and not re.match(r"^\d+[.)]\s+", lines[i].strip())
                    and not lines[i].strip().startswith(("#", "|", ">"))
                    and (lines[i].startswith("  ") or lines[i].startswith("\t"))
                ):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(item)}</li>")
            out.append(f"<ol>{''.join(items)}</ol>")
            continue

        para_buf.append(s)
        i += 1

    flush_para()
    return "\n".join(out), toc


# ---------------------------------------------------------------- 元信息提取
def cn_date(d: datetime) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


def parse_meta(md: str, path: Path):
    m = re.search(r"(\d{4})(\d{2})(\d{2})", path.name)
    date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else datetime.fromtimestamp(path.stat().st_mtime)

    # 标题：优先取「核心结论」里的核心判断句
    t = re.search(r"^#\s+(.+)$", md, re.M)
    raw_title = t.group(1).strip() if t else f"A股复盘 · {date:%Y-%m-%d}"
    raw_title = re.sub(r"^A股(深度)?复盘\s*[·・\-–]?\s*", "", raw_title).strip()
    raw_title = re.sub(r"（周[一二三四五六日]）", "", raw_title).strip()

    headline = ""
    sec1 = re.search(r"^##\s*一、[^\n]*\n(.+?)(?=\n##\s|\Z)", md, re.S | re.M)
    if sec1:
        body1 = sec1.group(1)
        q = re.search(r"「([^」\n]{6,60})」", body1)
        if q:
            headline = q.group(1).strip()
        else:
            b = re.search(r"\*\*([^*\n]{8,90})\*\*", body1)
            if b:
                headline = re.split(r"[—。；;]", b.group(1))[0].strip()[:38]
    title = headline or raw_title

    weekday = WEEKDAYS[date.weekday()]
    weekend = "休市" in path.name or "休市" in title

    # 导语：核心结论下第一段
    lead = ""
    sec = re.search(r"^##\s*一、[^\n]*\n(.+?)(?=\n##\s|\Z)", md, re.S | re.M)
    if sec:
        for line in sec.group(1).split("\n"):
            s = line.strip()
            if s and not s.startswith(("-", "*", "|", ">", "#")) and len(s) > 20:
                lead = s
                break
    lead = re.sub(r"\*\*(.+?)\*\*", r"\1", lead)
    lead = re.sub(r"[「」]", "", lead)
    lead = re.sub(r"\s+", " ", lead).strip()

    # 指数涨跌
    idx = {}
    idx_sec = re.search(r"^##\s*二、[^\n]*\n(.+?)(?=\n##\s|\Z)", md, re.S | re.M)
    if idx_sec:
        for line in idx_sec.group(1).split("\n"):
            if not line.strip().startswith("|"):
                continue
            cells = split_row(line)
            if len(cells) < 3:
                continue
            name = re.sub(r"\*|\s", "", cells[0])
            if name in ("上证指数", "深证成指", "创业板指", "科创50", "沪深300", "北证50"):
                pm = re.search(r"[+\-]?\d+(?:\.\d+)?%", cells[2])
                if pm:
                    idx[name] = pm.group(0)
    return dict(date=date, weekday=weekday, weekend=weekend, title=title, lead=lead, idx=idx)


def chip_html(k: str, v: str) -> str:
    v2 = v.replace("+", "")
    cls = "up" if v.startswith("+") else ("down" if v.startswith("-") else "flat")
    return f'<span class="chip"><span class="k">{esc(k)}</span><span class="{cls}">{esc(v2)}</span></span>'


# ---------------------------------------------------------------- 模板
MASTHEAD = """
<header class="masthead"><div class="wrap">
  <div class="brand">
    <h1>山哥 · A股每日复盘</h1>
    <div class="sub">Daily Market Review · A-Share Journal</div>
  </div>
  <div class="meta">{meta_right}</div>
</div></header>
"""

FOOT = """
<footer class="foot"><div class="wrap">
  <span>A股每日复盘期刊 · 由收盘数据自动生成</span>
  <span>数据口径：沪深A股全市场 · 红涨绿跌</span>
</div></footer>
"""


def render_issue(meta, body, toc, no, prev_m, next_m) -> str:
    meta_right = (
        f'<b>第 {no:03d} 期</b><br>'
        f"{meta['date']:%Y-%m-%d} · {meta['weekday']}"
    )
    toc_html = ""
    if toc:
        items = "".join(f'<li><a href="#{hid}">{esc(txt)}</a></li>' for hid, txt in toc)
        toc_html = f'<nav class="toc"><div class="toc-t">本期目录</div><ol>{items}</ol></nav>'

    date_label = f"{meta['date']:%Y-%m-%d} · {meta['weekday']}"
    if meta["weekend"]:
        date_label += " · 休市"

    pager = ""
    nav = []
    if prev_m:
        nav.append(
            f'<a class="prev" href="{prev_m["date"]:%Y-%m-%d}.html">'
            f'<span class="dir">← 上一期</span>{prev_m["date"]:%m-%d} {esc(prev_m["title"])}</a>'
        )
    if next_m:
        nav.append(
            f'<a class="next" href="{next_m["date"]:%Y-%m-%d}.html">'
            f'<span class="dir">下一期 →</span>{next_m["date"]:%m-%d} {esc(next_m["title"])}</a>'
        )
    if nav:
        pager = f'<div class="pager">{"".join(nav)}</div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{meta['date']:%Y-%m-%d} {esc(meta['title'])} · A股复盘第{no:03d}期</title>
<style>{BASE_CSS}</style>
</head><body>
{MASTHEAD.format(meta_right=meta_right)}
<div class="wrap"><div class="layout">
{toc_html}
<article>
  <div class="issue-head">
    <div class="kicker">第 {no:03d} 期 · NO.{no:03d}</div>
    <h1>{esc(meta['title'])}</h1>
    <div class="dateline">{date_label}</div>
  </div>
{body}
{pager}
</article>
</div></div>
{FOOT}
</body></html>"""


def render_index(metas) -> str:
    latest = metas[0]
    chips = "".join(chip_html(k, v) for k, v in latest["idx"].items())
    lead = latest["lead"][:200]

    # 按年份分组
    groups = {}
    for m in metas:
        groups.setdefault(m["date"].year, []).append(m)

    sections = []
    for year in sorted(groups, reverse=True):
        cards = []
        for m in groups[year]:
            cchips = "".join(chip_html(k, v) for k, v in list(m["idx"].items())[:4])
            cls = "card weekend" if m["weekend"] else "card"
            cards.append(
                f'<a class="{cls}" href="issues/{m["date"]:%Y-%m-%d}.html">'
                f'<div class="no">NO.{m["no"]:03d}</div>'
                f'<div class="date">{m["date"]:%m-%d}<small>{m["weekday"]}</small></div>'
                f'<div class="hl">{esc(m["title"])}</div>'
                + (f'<div class="chips">{cchips}</div>' if cchips else "")
                + "</a>"
            )
        sections.append(
            f'<div class="year">{year} 年 · 共 {len(groups[year])} 期</div>'
            f'<div class="grid">{"".join(cards)}</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A股每日复盘期刊 · 总目录</title>
<style>{BASE_CSS}{INDEX_CSS}</style>
</head><body>
{MASTHEAD.format(meta_right=f"<b>共 {len(metas)} 期</b><br>最新 {latest['date']:%Y-%m-%d}")}
<div class="wrap">
  <section class="hero">
    <div class="tag">最新一期 · NO.{latest['no']:03d}</div>
    <h2>{esc(latest['title'])}</h2>
    <p class="lead">{esc(lead)}</p>
    <div class="chips">{chips}</div>
    <a class="go" href="issues/{latest['date']:%Y-%m-%d}.html">阅读本期 →</a>
  </section>

  <div class="sect-t">往期存档</div>
  {''.join(sections)}
</div>
{FOOT}
</body></html>"""


def render_readme(metas) -> str:
    rows = "\n".join(
        f"| {m['no']:03d} | {m['date']:%Y-%m-%d} | {m['weekday']} | [{m['title']}](issues/{m['date']:%Y-%m-%d}.html) |"
        for m in metas
    )
    latest = metas[0]
    return f"""# A股每日复盘 · 期刊

收盘后自动生成的市场复盘存档，一期一份 HTML，**在线阅读：[https://ahazx.github.io/a-share-journal/](https://ahazx.github.io/a-share-journal/)**

## 每期包含

1. **核心结论** — 当日资金表现、领涨领跌板块、主线判定
2. **核心指数表现** — 上证/深成/创业板/科创50/沪深300/北证50 对照
3. **市场情绪** — 红盘率、涨跌停对比、题材持续性（涨了几天 / 龙头 / 后排 / 谁带不动谁）
4. **市场量能** — 成交额与环比
5. **连板梯队** — 高度、家数、封板质量、负反馈
6. **题材涨跌分析** — 领涨 3 个 + 领跌 3 个，含代表个股与涨跌逻辑

## 期号总览

| 期号 | 日期 | 星期 | 主题 |
|---|---|---|---|
{rows}

---
数据口径：沪深A股全市场，红涨绿跌。由 `build.py` 从每日复盘 Markdown 自动渲染。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    args = ap.parse_args()

    src = Path(args.src)
    files = sorted(src.glob("A股复盘_*.md"))
    if not files:
        print(f"[x] 未在 {src} 找到复盘 Markdown")
        return

    try:
        ISSUES.mkdir(exist_ok=True)
    except FileExistsError:
        pass
    metas = []
    for f in files:
        md = f.read_text(encoding="utf-8")
        meta = parse_meta(md, f)
        meta["src"] = f
        body, toc = md_to_html(md)
        meta["body"] = body
        meta["toc"] = toc
        metas.append(meta)

    metas.sort(key=lambda m: m["date"], reverse=True)
    for i, m in enumerate(metas, 1):
        m["no"] = i  # 越新期号越大 -> 修正为按时间正序
    total = len(metas)
    for i, m in enumerate(sorted(metas, key=lambda x: x["date"]), 1):
        m["no"] = i

    # 渲染各期
    asc = sorted(metas, key=lambda m: m["date"])
    for idx, m in enumerate(asc):
        prev_m = asc[idx - 1] if idx > 0 else None
        next_m = asc[idx + 1] if idx < len(asc) - 1 else None
        html_out = render_issue(m, m["body"], m["toc"], m["no"], prev_m, next_m)
        (ISSUES / f"{m['date']:%Y-%m-%d}.html").write_text(html_out, encoding="utf-8")

    (ROOT / "index.html").write_text(render_index(metas), encoding="utf-8")
    (ROOT / "README.md").write_text(render_readme(metas), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"[✓] 已生成 {total} 期，最新第 {metas[0]['no']:03d} 期 {metas[0]['date']:%Y-%m-%d} · {metas[0]['title']}")
    for m in metas[:3]:
        print(f"    NO.{m['no']:03d} {m['date']:%Y-%m-%d} {m['weekday']} {m['title'][:36]}")


if __name__ == "__main__":
    main()
