#!/usr/bin/env python3
"""Scaffold the next issue markdown file from the configured template.

Exit codes: 0 = ok, 1 = issue number conflict, 2 = environment/argument error.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date as date_cls
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402
import next_number  # noqa: E402

TEMPLATE_PATH = c.SKILL_ROOT / "assets" / "issue-template.md"


def render(cfg: dict, number: int, issue_date: str, description: str, topics: str, tags: list) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    title = c.title_for_number(number, cfg)
    quote_line = cfg.get("quote_line_template", "")
    quote_block = ""
    if quote_line:
        quote_block = quote_line.replace("{date}", issue_date).replace("{topics}", topics) + "\n\n"
    tags_block = "\n".join(f"  - {tag}" for tag in tags)
    placeholder = cfg["empty_section_placeholder"]
    separator = cfg.get("separator", "---")
    blocks = []
    for section in cfg["sections"]:
        blocks.append(f"## {section['heading']}\n\n{placeholder}")
    sections_block = f"\n\n{separator}\n\n".join(blocks)
    return (
        template.replace("{title}", title)
        .replace("{date}", issue_date)
        .replace("{description}", description)
        .replace("{tags_block}", tags_block)
        .replace("{quote_block}", quote_block)
        .replace("{separator}", separator)
        .replace("{sections_block}", sections_block)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成下一期 issue 脚手架")
    parser.add_argument("--number", type=int, help="指定期号（默认自动取号）")
    parser.add_argument("--date", help="发布日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--description", help="frontmatter description（默认占位文案）")
    parser.add_argument("--topics", help="引用行核心议题（默认占位文案）")
    parser.add_argument("--tags", help="逗号分隔的 tags（默认按配置下限占位）")
    parser.add_argument("--out", help="输出目录（默认 cwd 下 issues_subdir）")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    out_dir = Path(args.out) if args.out else Path.cwd() / cfg["issues_subdir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.number is not None:
        number = args.number
    else:
        number, _, _ = next_number.compute_next(cfg, out_dir.parent, None)

    target = out_dir / c.filename_for_number(number, cfg)
    if target.exists():
        print(f"[ERROR] 期号冲突：{target} 已存在", file=sys.stderr)
        return 1

    issue_date = args.date or date_cls.today().strftime("%Y-%m-%d")
    title = c.title_for_number(number, cfg)
    description = args.description or f"{title} 草稿骨架，导读待补充。"
    topics = args.topics or "待补充"
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    else:
        tags = ["待补充"] * max(cfg["frontmatter"].get("tags_min", 0), 1)
    content = render(cfg, number, issue_date, description, topics, tags)
    target.write_text(content, encoding="utf-8")
    if args.as_json:
        c.emit_json({"path": str(target.resolve()), "number": number, "date": issue_date})
    else:
        print(f"已创建 {target.resolve()}（第 {number} 期）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
