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
3. 重建 index.html 目录页（自动编期号）+ README.md 存档索引
"""

import argparse
import html
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES = ROOT / "issues"
ASSETS = ROOT / "assets"
DEFAULT_SRC = Path("/Users/zhangxu/WorkBuddy/automation-2026-09-21-16-00-31/outputs")

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

BASE_CSS = (ASSETS / "base.css").read_text(encoding="utf-8")
INDEX_CSS = (ASSETS / "index.css").read_text(encoding="utf-8")

# ---------------------------------------------------------------- Markdown 解析
NUM_RE = re.compile(r"(?<![\w.])[+\-]\d+(?:\.\d+)?(?:%|亿|万|倍|pct)")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline(text: str, color_nums: bool = True) -> str:
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
        s = lines[i].strip()

        if not s:
            flush_para()
            i += 1
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush_para()
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para()
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 2:
                hid = f"sec{h2_idx}"
                h2_idx += 1
                toc.append((hid, text))
                out.append(f'<h2 id="{hid}">{inline(text, False)}</h2>')
            elif level == 3:
                out.append(f"<h3>{inline(text, False)}</h3>")
            elif level >= 4:
                out.append(f"<h4>{inline(text, False)}</h4>")
            i += 1
            continue

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

        if s.startswith(">"):
            flush_para()
            q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = "".join(f"<p>{inline(x)}</p>" for x in (y.strip() for y in q) if x)
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        if re.match(r"^[-*+]\s+", s):
            flush_para()
            items = []
            while i < n and re.match(r"^[-*+]\s+", lines[i].strip()):
                item = re.sub(r"^[-*+]\s+", "", lines[i].strip())
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

        # 整行加粗的小标题（如 "**1. 个股层面普跌，情绪降至冰点**"）单独成段，
        # 否则会与下一行正文黏成一坨
        mb = re.fullmatch(r"\*\*([^*]+)\*\*", s)
        if mb and not para_buf:
            out.append(f'<p class="k">{inline(mb.group(1))}</p>')
            i += 1
            continue

        para_buf.append(s)
        i += 1

    flush_para()
    return "\n".join(out), toc

# ---------------------------------------------------------------- 元信息
def parse_meta(md: str, path: Path):
    m = re.search(r"(\d{4})(\d{2})(\d{2})", path.name)
    date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else datetime.fromtimestamp(path.stat().st_mtime)

    t = re.search(r"^#\s+(.+)$", md, re.M)
    h1 = t.group(1).strip() if t else f"A股复盘 · {date:%Y-%m-%d}"
    raw_title = re.sub(r"^A股(深度)?复盘\s*[·・\-–]?\s*", "", h1).strip()
    raw_title = re.sub(r"（周[一二三四五六日]）", "", raw_title).strip()

    weekday = WEEKDAYS[date.weekday()]
    weekend = "休市" in path.name or "休市" in h1

    # 只认「核心结论」这一节：休市日报告的第一节是"交易日判定"，
    # 里面全是命令行，抓错了标题就会变成 `westock quote …`
    sec1 = None
    for mm in re.finditer(r"^##\s*([^\n]*)\n(.+?)(?=\n##\s|\Z)", md, re.S | re.M):
        if "核心结论" in mm.group(1):
            sec1 = mm
            break
    if sec1 is None:
        sec1 = re.search(r"^##\s*一、[^\n]*\n(.+?)(?=\n##\s|\Z)", md, re.S | re.M)
    body1 = sec1.group(2) if sec1 and sec1.lastindex and sec1.lastindex >= 2 else (sec1.group(1) if sec1 else "")

    headline = ""
    if body1:
        q = re.search(r"「([^」\n]{6,60})」", body1)
        if q:
            headline = q.group(1).strip()
        else:
            b = re.search(r"\*\*([^*\n]{8,90})\*\*", body1)
            if b:
                headline = re.split(r"[—。；;]", b.group(1))[0].strip()[:38]
        headline = re.sub(r"\s+", " ", headline)

    lead = ""
    if body1:
        for line in body1.split("\n"):
            s2 = line.strip()
            if (
                s2
                and not s2.startswith(("-", "*", "|", ">", "#"))
                and "`" not in s2
                and not re.match(r"^\d+[.)]\s", s2)
                and len(s2) > 20
            ):
                lead = s2
                break
    lead = re.sub(r"\*\*(.+?)\*\*", r"\1", lead)
    lead = re.sub(r"[「」`]", "", lead)
    lead = re.sub(r"\s+", " ", lead).strip()

    if weekend:
        t2 = raw_title
        t2 = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", t2)             # 去开头日期
        t2 = re.sub(r"[（(]?周[一二三四五六日][）)]?", "", t2)        # 去星期
        t2 = re.sub(r"[（(]\d{4}-\d{2}-\d{2}[）)]", "", t2)        # 去结尾日期
        t2 = t2.replace("休市", "").replace("A股", "")
        t2 = re.sub(r"^[\s·\-—|:：,，、（）()）]+", "", t2)
        t2 = re.sub(r"[\s·\-—|:：,，、（）()）]+$", "", t2)
        title = t2 or "周末休市"
        lead = ""
    else:
        title = headline or raw_title

    # 去掉开头的口语化标签，避免目录里出现"一句话：…""资金表现（一句话）：…"
    title = re.sub(r"^(资金表现|核心结论|结论|一句话|判读|定性)\s*[（(]?一句话[）)]?\s*[：:]\s*", "", title)
    title = re.sub(r"^(资金表现|核心结论|结论|一句话|判读|定性)\s*[：:]\s*", "", title)
    title = title.strip("　 ：:，、")

    # 标题仍是一个光秃秃的日期（老报告没写判断句）→ 用导语首句顶上
    if (re.fullmatch(r"\d{4}-\d{2}-\d{2}", title or "") or not title) and lead:
        fallback = re.split(r"[。；]", lead)[0].strip(" ，、")
        if fallback:
            title = fallback[:30].rstrip("，、 ") + ("…" if len(fallback) > 30 else "")

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


def dek_of(meta):
    """导语：剥掉与标题重复的部分"""
    lead, title = meta["lead"], meta["title"]
    if not lead:
        return ""
    out = lead.replace(title, "")
    out = re.sub(r"^[的，、—\-：:\s]+", "", out).strip()
    return out if len(out) >= 16 else ""


def short_toc(t: str) -> str:
    """目录条目：去掉括注、冒号后的长解释，避免折行"""
    t2 = re.sub(r"[（(][^）)]*[）)]", "", t).strip()
    if len(t2) > 15 and "：" in t2:
        head = t2.split("：")[0].strip()
        if len(head) >= 5:
            t2 = head
    return t2 or t


# ---------------------------------------------------------------- 模板
MASTHEAD = """<header class="masthead"><div class="wrap">
  <a class="brand" href="{home}">A股每日复盘</a>
  <div class="mhmeta">{meta_right}</div>
</div></header>"""

FOOT = """<footer class="foot"><div class="wrap">
  <span>数据口径：沪深A股全市场 · 红涨绿跌 · 收盘数据</span>
  <span>每日收盘后自动生成</span>
</div></footer>"""


def render_issue(meta, body, toc, no, prev_m, next_m) -> str:
    mast = MASTHEAD.format(
        home="../index.html",
        meta_right=f"{meta['date']:%Y-%m-%d} · {meta['weekday']} · 第 {no:03d} 期",
    )
    toc_html = ""
    if toc:
        items = "".join(
            f'<li><a href="#{hid}">{esc(short_toc(txt))}</a></li>' for hid, txt in toc
        )
        toc_html = f'<nav class="toc"><div class="toc-t">目 录</div><ol>{items}</ol></nav>'

    dek_html = ""
    dek = ""

    nav = []
    if prev_m:
        nav.append(
            f'<a class="prev" href="{prev_m["date"]:%Y-%m-%d}.html">'
            f'<span class="dir">上一期</span>{prev_m["date"]:%m-%d}　{esc(prev_m["title"])}</a>'
        )
    if next_m:
        nav.append(
            f'<a class="next" href="{next_m["date"]:%Y-%m-%d}.html">'
            f'<span class="dir">下一期</span>{next_m["date"]:%m-%d}　{esc(next_m["title"])}</a>'
        )
    pager = f'<div class="pager">{"".join(nav)}</div>' if nav else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(meta['title'])}｜{meta['date']:%Y-%m-%d} A股复盘</title>
<meta name="description" content="{esc(dek or meta['title'])}">
<style>{BASE_CSS}</style>
</head><body>
{mast}
<div class="wrap"><div class="layout">
{toc_html}
<article>
  <div class="meta">{meta['date']:%Y年%-m月%-d日}　{meta['weekday']}</div>
  <h1 class="hl">{esc(meta['title'])}</h1>
  {dek_html}
{body}
{pager}
</article>
</div></div>
{FOOT}
</body></html>"""


def render_index(metas) -> str:
    latest = metas[0]
    mast = MASTHEAD.format(
        home="index.html",
        meta_right=f"共 {len(metas)} 期 · 最新 {latest['date']:%Y-%m-%d}",
    )

    idx_items = "".join(
        f'<span><b>{esc(k)}</b><span class="{"up" if v.startswith("+") else ("down" if v.startswith("-") else "flat")}">{esc(v)}</span></span>'
        for k, v in latest["idx"].items()
    )
    dek = dek_of(latest)
    dek_html = f'<p class="dek">{esc(dek)}</p>' if dek else ""

    groups = {}
    for m in metas:
        groups.setdefault(m["date"].year, []).append(m)

    sections = []
    for year in sorted(groups, reverse=True):
        rows = []
        for m in groups[year]:
            cls = ' class="closed"' if m["weekend"] else ""
            tag = ' <span class="tag">休市</span>' if (m["weekend"] and "休市" not in m["title"]) else ""
            chg = "" if m["weekend"] else m["idx"].get("上证指数", "")
            chg_cls = "up" if chg.startswith("+") else ("down" if chg.startswith("-") else "")
            rows.append(
                f'<li><a href="issues/{m["date"]:%Y-%m-%d}.html"{cls}>'
                f'<span class="d">{m["date"]:%m-%d}</span>'
                f'<span class="w">{m["weekday"]}</span>'
                f'<span class="t">{esc(m["title"])}{tag}</span>'
                f'<span class="c {chg_cls}">{esc(chg)}</span>'
                f"</a></li>"
            )
        sections.append(
            f'<div class="year">{year}<em>{len(groups[year])} 期</em></div>'
            f'<ul class="rows">{"".join(rows)}</ul>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A股每日复盘 · 存档</title>
<style>{BASE_CSS}{INDEX_CSS}</style>
</head><body>
{mast}
<main class="wrap">
  <section class="latest">
    <div class="meta">{latest['date']:%Y年%m月%d日}　{latest['weekday']}　第 {latest['no']:03d} 期</div>
    <h1><a href="issues/{latest['date']:%Y-%m-%d}.html">{esc(latest['title'])}</a></h1>
    {dek_html}
    <div class="indices">{idx_items}</div>
    <a class="more" href="issues/{latest['date']:%Y-%m-%d}.html">阅读本期</a>
  </section>

  <section class="archive">
    <div class="archive-h">存 档</div>
    {''.join(sections)}
  </section>
</main>
{FOOT}
</body></html>"""


def render_readme(metas) -> str:
    rows = "\n".join(
        f"| {m['no']:03d} | {m['date']:%Y-%m-%d} | {m['weekday']} | [{m['title']}](issues/{m['date']:%Y-%m-%d}.html) |"
        for m in metas
    )
    return f"""# A股每日复盘 · 存档

收盘后自动生成的市场复盘，一期一份 HTML。
在线阅读：**https://ahazx.github.io/a-share-journal/**

## 每期包含

1. **核心结论** — 当日资金表现、领涨领跌板块、主线判定
2. **核心指数表现** — 上证/深成/创业板/科创50/沪深300/北证50 对照
3. **市场情绪** — 红盘率、涨跌停对比、题材持续性（涨了几天 / 龙头 / 后排 / 谁带不动谁）
4. **市场量能** — 成交额与环比
5. **连板梯队** — 高度、家数、封板质量、负反馈
6. **题材涨跌分析** — 领涨 3 个 + 领跌 3 个，含代表个股与涨跌逻辑
7. **风险提示** — 当日领涨股中的退市 / ST 风险个股

## 存档

| 期号 | 日期 | 星期 | 主题 |
|---|---|---|---|
{rows}

---
数据口径：沪深A股全市场，红涨绿跌。由 `build.py` 从每日复盘 Markdown 渲染。
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
        meta["body"], meta["toc"] = md_to_html(md)
        metas.append(meta)

    metas.sort(key=lambda m: m["date"], reverse=True)
    for i, m in enumerate(sorted(metas, key=lambda x: x["date"]), 1):
        m["no"] = i

    asc = sorted(metas, key=lambda m: m["date"])
    for idx, m in enumerate(asc):
        prev_m = asc[idx - 1] if idx > 0 else None
        next_m = asc[idx + 1] if idx < len(asc) - 1 else None
        (ISSUES / f"{m['date']:%Y-%m-%d}.html").write_text(
            render_issue(m, m["body"], m["toc"], m["no"], prev_m, next_m), encoding="utf-8"
        )

    (ROOT / "index.html").write_text(render_index(metas), encoding="utf-8")
    (ROOT / "README.md").write_text(render_readme(metas), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"[✓] 已生成 {len(metas)} 期，最新第 {metas[0]['no']:03d} 期 {metas[0]['date']:%Y-%m-%d} · {metas[0]['title']}")


if __name__ == "__main__":
    main()
