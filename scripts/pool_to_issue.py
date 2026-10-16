#!/usr/bin/env python3
"""Convert a material pool into an issue skeleton (deterministic; the agent fills the prose).

Only entries marked `[x]` are carried over. Missing fields are reported, not invented:
the skeleton keeps their lines out so validate_issue.py flags them until they are filled.

Exit codes: 0 = skeleton written, 1 = structural problem (nothing selected / unclassified
entries / missing frontmatter), 2 = usage/environment error.
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
import new_issue  # noqa: E402

META_KEYS = {"链接", "来源", "类型", _pool.SECTION_KEY, "时长", "标题"}


def resolve_section(entry: dict, section_heading: str, cfg: dict):
    """Return the target section dict for an entry, or None when it cannot be classified."""
    heading = entry["fields"].get(_pool.SECTION_KEY, "").strip() or section_heading
    for section in cfg["sections"]:
        if c.nfc(section["heading"]) == c.nfc(heading):
            return section
    return None


def prepare_entry(entry: dict, cfg: dict, section: dict) -> dict:
    allowed = list(section.get("card_types", []) or [])
    raw_type = entry["fields"].get("类型", "").strip()
    card_type = None
    fallback = False
    if allowed:
        match = next((t for t in allowed if t.lower() == raw_type.lower()), None)
        card_type = match or allowed[0]
        fallback = match is None and bool(raw_type)
    fields = c.apply_field_aliases(entry["fields"], cfg)
    required = cfg.get("entry", {}).get("required_fields", []) or []
    present = {name: fields.get(name, "").strip() for name in required}
    return {
        "title": entry["title"].strip(),
        "tag": fields.get("标签", "").strip(),
        "url": fields.get("链接", "").strip(),
        "card_type": card_type,
        "fields": present,
        "missing_fields": [name for name, value in present.items() if not value],
        "fallback_type": fallback,
        "raw_type": raw_type,
    }


def render_entry(number: int, item: dict, cfg: dict) -> str:
    tag = f"[{item['tag']}] " if item["tag"] else ""
    lines = [f"### {number}. {tag}[{item['title']}]({item['url']})", ""]
    for name, value in item["fields"].items():
        if value:
            lines.append(f"- **{name}：** {value}")
    return "\n".join(lines)


def build_issue(pool: dict, cfg: dict, number: int, issue_date: str, topics: str) -> tuple:
    """Return (markdown, report). markdown is None when a structural problem blocks the write."""
    title = c.title_for_number(number, cfg)
    meta = pool["frontmatter"]
    description = str(meta.get("description", "") or "").strip()
    tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
    tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    fm_cfg = cfg.get("frontmatter", {})
    quote_template = cfg.get("quote_line_template", "")
    separator = cfg.get("separator", "---")
    placeholder = cfg["empty_section_placeholder"]

    report = {"warnings": [], "unclassified": [], "skipped": 0, "prepared": 0, "structural": []}
    buckets = {c.nfc(section["heading"]): [] for section in cfg["sections"]}
    section_by_nfc = {c.nfc(section["heading"]): section for section in cfg["sections"]}

    for section in pool["sections"]:
        for entry in section["entries"]:
            if not entry["selected"]:
                report["skipped"] += 1
                continue
            target = resolve_section(entry, section["heading"], cfg)
            if target is None:
                report["unclassified"].append(entry["title"] or entry["fields"].get("链接", "?"))
                continue
            if not entry["title"].strip() or not entry["fields"].get("链接", "").strip():
                report["structural"].append(f"条目『{entry['title'] or '未命名'}』缺标题或链接")
                continue
            buckets[c.nfc(target["heading"])].append(entry)
            report["prepared"] += 1

    if not any(buckets.values()):
        report["structural"].append("池里没有任何 [x] 入选条目")
    if quote_template and not topics.strip():
        report["structural"].append("缺少 topics（池 frontmatter 的 topics 或 --topics），引用行无法生成")
    if fm_cfg.get("tags_min") and len(tags) < fm_cfg["tags_min"]:
        report["structural"].append(f"tags 只有 {len(tags)} 个，少于下限 {fm_cfg['tags_min']}")
    if fm_cfg.get("tags_max") and len(tags) > fm_cfg["tags_max"]:
        report["structural"].append(f"tags 有 {len(tags)} 个，超过上限 {fm_cfg['tags_max']}")
    if fm_cfg.get("description_max_chars") and len(description) > fm_cfg["description_max_chars"]:
        report["structural"].append(f"description {len(description)} 字，超过上限 {fm_cfg['description_max_chars']}")

    if report["structural"]:
        return None, report

    blocks = []
    for section in cfg["sections"]:
        items = []
        for entry in buckets[c.nfc(section["heading"])]:
            items.append(prepare_entry(entry, cfg, section_by_nfc[c.nfc(section["heading"])]))
        if not items:
            blocks.append(f"## {section['heading']}\n\n{placeholder}")
            continue
        rendered = []
        for index, item in enumerate(items, start=1):
            if item["missing_fields"]:
                report["warnings"].append(f"条目『{item['title']}』缺字段: {', '.join(item['missing_fields'])}")
            if cfg.get("entry", {}).get("tag_required") and not item["tag"]:
                report["warnings"].append(f"条目『{item['title']}』缺 [标签]（tag_required=true）")
            if item["fallback_type"]:
                report["warnings"].append(
                    f"条目『{item['title']}』类型『{item['raw_type']}』不是该板块允许的 card type，已用 {item['card_type']}"
                )
            body = render_entry(index, item, cfg)
            if cfg.get("card", {}).get("containers") and item["card_type"]:
                body = f"::: card {item['card_type']}\n{body}\n:::"
            rendered.append(body)
        blocks.append(f"## {section['heading']}\n\n" + "\n\n".join(rendered))

    sections_block = f"\n\n{separator}\n\n".join(blocks)
    document = new_issue.render_document(cfg, title, issue_date, description, topics.strip(), tags, sections_block)
    return document, report


def main() -> int:
    parser = argparse.ArgumentParser(description="素材池 → issue 骨架（确定性搬运）")
    parser.add_argument("pool", help="素材池文件")
    parser.add_argument("--number", type=int, help="期号（默认取池 frontmatter 的 number）")
    parser.add_argument("--date", help="发布日期（默认取池 frontmatter 的 date）")
    parser.add_argument("--topics", help="引用行核心议题（默认取池 frontmatter 的 topics）")
    parser.add_argument("--out", help="输出文件（默认 cwd 下 issues_subdir/issue-N.md）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 issue 文件")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    pool_path = Path(args.pool)
    if not pool_path.exists():
        c.die(f"素材池不存在: {pool_path}")
    pool = _pool.parse(pool_path.read_text(encoding="utf-8"), cfg)
    if not pool["sections"]:
        c.die(f"这不像是素材池（没有 ## 板块）: {pool_path}")

    meta = pool["frontmatter"]
    number = args.number or int(str(meta.get("number") or 0) or 0)
    if not number:
        found = re.search(r"issue-(\d+)-pool", pool_path.name)
        if not found:
            c.die("无法确定期号，请用 --number 指定")
        number = int(found.group(1))
    issue_date = args.date or str(meta.get("date") or "") or date_cls.today().strftime("%Y-%m-%d")
    topics = args.topics if args.topics is not None else str(meta.get("topics") or "")
    out_path = Path(args.out) if args.out else Path.cwd() / cfg["issues_subdir"] / c.filename_for_number(number, cfg)

    document, report = build_issue(pool, cfg, number, issue_date, topics)
    if document is None:
        for problem in report["structural"]:
            print(f"[ERROR] {problem}", file=sys.stderr)
        if report["unclassified"]:
            print(f"[ERROR] 未归类条目（填 `- {_pool.SECTION_KEY}：<板块名>` 或移到对应板块）: {', '.join(report['unclassified'])}", file=sys.stderr)
        return 1
    if out_path.exists() and not args.force:
        print(f"[ERROR] 目标已存在：{out_path}（确认要覆盖加 --force）", file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")

    for warning in report["warnings"]:
        print(f"[WARN] {warning}")
    if report["unclassified"]:
        print(f"[WARN] 未归类条目已跳过: {', '.join(report['unclassified'])}")
    print(f"已生成 {out_path.resolve()} · 入选 {report['prepared']} 条 · 未勾选 {report['skipped']} 条")
    if report["warnings"]:
        print("缺字段条目先跑 validate_issue.py，再把报错交给 agent 补写")
    if args.as_json:
        c.emit_json({"path": str(out_path.resolve()), "number": number, "prepared": report["prepared"], "warnings": report["warnings"], "skipped": report["skipped"], "unclassified": report["unclassified"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
