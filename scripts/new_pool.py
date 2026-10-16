#!/usr/bin/env python3
"""Create a weekly material pool (素材池) — the local file you hand-edit before converting.

Exit codes: 0 = ok, 1 = pool already exists, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date as date_cls
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402
import _pool  # noqa: E402
import next_number  # noqa: E402

URL_RE = re.compile(r"https?://\S+")
ARXIV_LINE_RE = re.compile(r"^\[(?P<date>\d{4}-\d{2}-\d{2})\]\s*(?P<title>.+)$")

TEMPLATE_COMMENT = """<!--
条目模板（手搓时复制到板块下）：
### [ ] 1. 标题
- 链接：https://...
- 来源：平台 · 作者
- 类型：该板块允许的 card type，如 insight / tutorial / opensource / practice / review / paper
- 标签：条目 H3 里的 [标签]
- 时长：15 分钟（视频条目填，写载体时用）
- 核心亮点：
- 团队参考：
- 载体：
-->"""

STAGING_HEADING = "待归类"


def read_candidates(text: str):
    """Tolerate the plain output of dedup_urls / fetch_arxiv / fetch_github_trends."""
    items: list = []
    skipped_dup = 0
    pending_title = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("DUP"):
            skipped_dup += 1
            continue
        if line.startswith("NEW"):
            line = line[3:].strip()
        if line.startswith("- "):
            line = line[2:].strip()
        arxiv = ARXIV_LINE_RE.match(line)
        if arxiv and "http" not in line:
            pending_title = re.split(r"\s+—\s+", arxiv.group("title"))[0].strip()
            continue
        if "\t" in line:
            url, title = line.split("\t", 1)
        else:
            found = URL_RE.search(line)
            if not found:
                continue
            url = found.group(0).rstrip("，。,)")
            prefix = line[: found.start()].strip(" -—")
            title = re.split(r"\s*★", prefix)[0].strip() if prefix else pending_title
        pending_title = ""
        items.append({"url": url.strip(), "title": title.strip()})
    return items, skipped_dup


def build_pool(cfg: dict, number: int, issue_date: str, items: list) -> str:
    title = c.title_for_number(number, cfg)
    tags = ["待补充"] * max(cfg["frontmatter"].get("tags_min", 0), 1)
    frontmatter = [
        "---",
        f"pool: issue-{number}",
        f"number: {number}",
        f"date: {issue_date}",
        "topics: 待补充",
        f'description: "{title} 草稿骨架，导读待补充。"',
        "tags:",
        *[f"  - {tag}" for tag in tags],
        "---",
    ]
    blocks = [
        f"# 素材池 · {title}",
        "",
        "> 用法：把入选条目的 `[ ]` 改成 `[x]`；补齐字段后跑",
        "> `python3 scripts/pool_to_issue.py <本文件>` 生成 issue 骨架（缺什么会列出来）。",
        f"> `类型` 填该板块允许的 card type（留空取该板块第一个）；`{_pool.SECTION_KEY}` 填了就以它为准。",
        "",
        TEMPLATE_COMMENT,
    ]
    for section in cfg["sections"]:
        blocks += ["", f"## {section['heading']}"]
    if items:
        blocks += [
            "",
            f"## {STAGING_HEADING}",
            "",
            f"> 导入的候选先落这里：把它们移到上面板块，或填 `- {_pool.SECTION_KEY}：<板块名>`。",
        ]
        for index, item in enumerate(items, start=1):
            fields = {"链接": item["url"], _pool.SECTION_KEY: ""}
            blocks += ["", _pool.render_entry(index, item["title"], fields, cfg)]
    return "\n".join(frontmatter) + "\n\n" + "\n".join(blocks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/导入周刊素材池")
    parser.add_argument("--number", type=int, help="期号（默认自动取号）")
    parser.add_argument("--date", help="发布日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--from", dest="source", help="候选清单文件（dedup_urls / fetch_arxiv 的纯文本输出）")
    parser.add_argument("--out", help="输出目录（默认 cwd 下 pool_dir）")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    out_dir = Path(args.out) if args.out else Path.cwd() / cfg["pool_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.number is not None:
        number = args.number
    else:
        number, _, _ = next_number.compute_next(cfg, Path.cwd(), None)

    items: list = []
    skipped_dup = 0
    if args.source:
        source = Path(args.source)
        if not source.exists():
            c.die(f"候选文件不存在: {source}")
        items, skipped_dup = read_candidates(source.read_text(encoding="utf-8"))

    target = out_dir / c.pool_filename_for_number(number, cfg)
    if target.exists():
        print(f"[ERROR] 素材池已存在：{target}", file=sys.stderr)
        return 1
    issue_date = args.date or date_cls.today().strftime("%Y-%m-%d")
    target.write_text(build_pool(cfg, number, issue_date, items), encoding="utf-8")

    if args.as_json:
        c.emit_json({"path": str(target.resolve()), "number": number, "imported": len(items), "skipped_dup": skipped_dup})
    else:
        print(f"已创建 {target.resolve()}（第 {number} 期）· 导入候选 {len(items)} 条，跳过 DUP {skipped_dup} 条")
        if items:
            print(f"提示：候选落在「{STAGING_HEADING}」板块，勾选并归类后再跑 pool_to_issue.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
