#!/usr/bin/env python3
"""Render an issue markdown file to a standalone single-file HTML preview.

Only the constrained markdown subset produced by validate-passing issues is
rendered natively; anything else degrades to <pre> with a WARN.
Exit codes: 0 = ok, 1 = skipped blocks under --strict, 2 = input missing.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402

CSS_PATH = c.SKILL_ROOT / "assets" / "preview-style.css"
CODE_FENCE_RE = re.compile(r"^```")
FIELD_BULLET_RE = c.FIELD_BULLET_RE
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")


def inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = escaped.replace("&amp;nbsp;", "&nbsp;")
    codes: list = []

    def stash(match):
        codes.append(match.group(1))
        return f"\x00{len(codes) - 1}\x00"

    escaped = INLINE_CODE_RE.sub(stash, escaped)
    escaped = LINK_RE.sub(lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', escaped)
    escaped = BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = ITALIC_RE.sub(r"<em>\1</em>", escaped)
    for index, code in enumerate(codes):
        escaped = escaped.replace(f"\x00{index}\x00", f"<code>{html.escape(code, quote=False)}</code>")
    return escaped


def injected_colors(cfg: dict) -> str:
    colors = cfg.get("card", {}).get("colors", {}) or {}
    if not colors:
        return ""
    light = []
    dark = []
    for card_type, palette in colors.items():
        light.append(
            f".news-card.card-{card_type}{{--card-bg:{palette.get('bg', '#f7f8fa')};"
            f"--card-border:{palette.get('border', '#eceef2')}}}"
        )
        if palette.get("dark_bg") or palette.get("dark_border"):
            dark.append(
                f".news-card.card-{card_type}{{--card-bg:{palette.get('dark_bg', '#1f2228')};"
                f"--card-border:{palette.get('dark_border', '#2a2e36')}}}"
            )
    out = "\n".join(light)
    if dark:
        out += "\n@media (prefers-color-scheme: dark) {\n" + "\n".join(dark) + "\n}"
    return out


def render(text: str, cfg: dict):
    meta, body = c.parse_frontmatter(text)
    meta = meta or {}
    lines = body.splitlines()
    out: list = []
    warnings: list = []
    skipped = 0
    sections = 0
    cards = 0
    in_card = False
    in_pre = False
    pre_buffer: list = []
    paragraph: list = []
    placeholder = cfg["empty_section_placeholder"].strip()
    seen_h2 = False

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph = []

    def flush_pre(lineno):
        nonlocal in_pre, pre_buffer, skipped
        if in_pre:
            out.append(f'<pre class="skipped">{html.escape(chr(10).join(pre_buffer))}</pre>')
            warnings.append((lineno, "代码/未识别块降级为 <pre>"))
            skipped += 1
            in_pre = False
            pre_buffer = []

    for index, raw in enumerate(lines):
        lineno = index + 1
        stripped = raw.strip()
        if CODE_FENCE_RE.match(stripped):
            if in_pre:
                flush_pre(lineno)
            else:
                flush_paragraph()
                in_pre = True
            continue
        if in_pre:
            pre_buffer.append(raw)
            continue
        if not stripped:
            flush_paragraph()
            continue
        if stripped == "---":
            flush_paragraph()
            out.append("<hr>")
            continue
        if c.CARD_OPEN_RE.match(stripped):
            flush_paragraph()
            card_type = c.CARD_OPEN_RE.match(stripped).group("type")
            out.append(f'<div class="news-card card-{html.escape(card_type, quote=True)}">')
            in_card = True
            cards += 1
            continue
        if c.CARD_CLOSE_RE.match(stripped):
            flush_paragraph()
            if in_card:
                out.append("</div>")
                in_card = False
            continue
        if stripped.startswith(":::"):
            flush_paragraph()
            in_pre = True
            pre_buffer = [raw]
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            out.append(f"<h1>{inline(stripped[2:])}</h1>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            seen_h2 = True
            sections += 1
            out.append(f"<h2>{inline(stripped[3:])}</h2>")
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            out.append(f"<h3>{inline(stripped[4:])}</h3>")
            continue
        field = FIELD_BULLET_RE.match(stripped)
        if field:
            flush_paragraph()
            label = field.group("label").strip().rstrip("：:")
            out.append(f'<p class="field"><strong>{html.escape(label)}：</strong> {inline(field.group("rest"))}</p>')
            continue
        if stripped == placeholder:
            flush_paragraph()
            out.append(f'<blockquote class="empty"><em>{inline(stripped[2:].strip())}</em></blockquote>')
            continue
        if stripped.startswith("> "):
            flush_paragraph()
            css_class = "" if seen_h2 else ' class="quote-line"'
            out.append(f"<blockquote{css_class}>{inline(stripped[2:])}</blockquote>")
            continue
        if stripped.startswith(("- ", "* ", "1. ")) or stripped.startswith("|"):
            flush_paragraph()
            in_pre = True
            pre_buffer = [raw]
            continue
        paragraph.append(stripped)
    flush_paragraph()
    flush_pre(len(lines))
    if in_card:
        out.append("</div>")
        warnings.append((len(lines), "card 容器未闭合"))
    header = []
    if meta.get("date"):
        header.append(f'<div class="meta">📅 {html.escape(str(meta["date"]))}</div>')
    if isinstance(meta.get("tags"), list) and meta["tags"]:
        tags = "".join(f'<span class="tag">{html.escape(str(t))}</span>' for t in meta["tags"])
        header.append(f'<div class="meta">{tags}</div>')
    if meta.get("description"):
        header.append(f'<div class="meta">{inline(str(meta["description"]))}</div>')
    css = CSS_PATH.read_text(encoding="utf-8") + "\n" + injected_colors(cfg)
    title = html.escape(str(meta.get("title") or "周刊预览"))
    document = (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        f"<title>{title}</title>\n<style>\n{css}\n</style>\n</head>\n<body>\n<div class=\"page\">\n"
        + "\n".join(header)
        + "\n"
        + "\n".join(out)
        + '\n<div class="footer">weekly-craft 本地预览 · 最终效果以站点构建为准</div>\n</div>\n</body>\n</html>\n'
    )
    return document, {"sections": sections, "cards": cards, "skipped": skipped, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="单文件 HTML 预览")
    parser.add_argument("file")
    parser.add_argument("--out", default="preview.html")
    parser.add_argument("--open", action="store_true", help="生成后用系统浏览器打开")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--strict", action="store_true", help="存在降级块时退出 1")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        c.die(f"输入文件不存在: {path}")
    cfg = c.load_config(args.config)
    document, stats = render(path.read_text(encoding="utf-8"), cfg)
    out = Path(args.out)
    out.write_text(document, encoding="utf-8")
    for lineno, message in stats["warnings"]:
        print(f"[WARN] preview: {message} (line {lineno})")
    print(f"已生成 {out.resolve()} — {stats['sections']} sections, {stats['cards']} cards, {stats['skipped']} skipped blocks")
    if args.open:
        subprocess.Popen(["xdg-open", str(out.resolve())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if args.strict and stats["skipped"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
