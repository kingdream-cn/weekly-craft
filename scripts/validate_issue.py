#!/usr/bin/env python3
"""Validate a weekly issue markdown file against the configured format.

Exit codes: 0 = pass, 1 = validation errors, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402

QUOTE_RE = re.compile(r'"([^"]*)"|「([^」]*)」|“([^”]*)”')
BAD_LINK_RE = re.compile(r"\]\((?!https?://)")


def title_pattern(cfg: dict) -> re.Pattern:
    pattern = re.escape(cfg["title_template"])
    pattern = pattern.replace(re.escape("{site_name}"), re.escape(cfg["site_name"]))
    pattern = pattern.replace(re.escape("{number}"), r"(?P<number>\d+)")
    return re.compile(pattern + r"\Z")


def quote_line_pattern(cfg: dict, date: str):
    template = cfg.get("quote_line_template", "")
    if not template:
        return None
    pattern = re.escape(template)
    pattern = pattern.replace(re.escape("{date}"), r"(?P<date>\d{4}-\d{2}-\d{2})")
    pattern = pattern.replace(re.escape("{topics}"), r".+")
    return re.compile(pattern + r"\Z"), date


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, rule, message, line=0):
        self.errors.append({"rule": rule, "line": line, "message": message})

    def warn(self, rule, message, line=0):
        self.warnings.append({"rule": rule, "line": line, "message": message})


def load_history(issues_dir: Path, cfg: dict, skip: Path):
    urls: dict = {}
    tags: set = set()
    numbers: set = set()
    for path in sorted(issues_dir.glob("*.md")):
        if path.resolve() == skip.resolve():
            continue
        number = c.issue_number_from_filename(path.name, cfg)
        if number is not None:
            numbers.add(number)
        text = path.read_text(encoding="utf-8")
        for url in c.extract_urls(text):
            urls.setdefault(url, path.name)
        meta, _ = c.parse_frontmatter(text)
        if isinstance(meta, dict) and isinstance(meta.get("tags"), list):
            tags.update(meta["tags"])
    return urls, tags, numbers


def validate(path: Path, cfg: dict, report: Report, history=None) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error("E00", f"文件不可读: {exc}")
        return
    issue = c.parse_issue(text, placeholder=cfg["empty_section_placeholder"])
    meta = issue["frontmatter"]
    fm_cfg = cfg["frontmatter"]

    if meta is None:
        report.error("E01", "缺少 frontmatter（文件需以 --- 开头）", 1)
        meta = {}
    else:
        for field in fm_cfg.get("required", []):
            if field not in meta or meta[field] in (None, "", []):
                report.error("E01", f"frontmatter 缺少字段: {field}", 1)

    title = meta.get("title", "")
    number = None
    if title:
        match = title_pattern(cfg).match(str(title))
        if not match:
            report.error("E02", f"title 不符合模板 '{cfg['title_template']}': {title}", 1)
        else:
            number = int(match.group("number"))
    file_number = c.issue_number_from_filename(path.name, cfg)
    if file_number is not None and number is not None and file_number != number:
        report.error("E02", f"文件名期号 {file_number} 与 title 期号 {number} 不一致", 1)

    date = str(meta.get("date", ""))
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        report.error("E03", f"date 不是合法 YYYY-MM-DD: {date!r}", 2)

    tags = meta.get("tags")
    tags_min = fm_cfg.get("tags_min", 0)
    tags_max = fm_cfg.get("tags_max", 0)
    if tags_min or tags_max:
        if not isinstance(tags, list):
            report.error("E04", "tags 必须是列表", 2)
        else:
            if tags_min and len(tags) < tags_min:
                report.error("E04", f"tags 数量 {len(tags)} 少于下限 {tags_min}", 2)
            if tags_max and len(tags) > tags_max:
                report.error("E04", f"tags 数量 {len(tags)} 超过上限 {tags_max}", 2)
            if any(not isinstance(t, str) or not t.strip() for t in tags):
                report.error("E04", "tags 含空元素", 2)

    description = meta.get("description", "")
    desc_max = fm_cfg.get("description_max_chars", 0)
    if desc_max:
        if not str(description).strip():
            report.error("E15", "description 不能为空", 3)
        elif len(str(description)) > desc_max:
            report.error("E15", f"description 长度 {len(str(description))} 超过上限 {desc_max}", 3)

    if issue["h1"] is None:
        report.error("E05", "缺少 H1 标题", issue["h1_line"] or 1)
    elif str(title) and issue["h1"] != str(title):
        report.error("E05", f"H1 与 title 不一致: {issue['h1']!r} != {title!r}", issue["h1_line"])

    quote_spec = quote_line_pattern(cfg, date)
    if quote_spec:
        pattern, _ = quote_spec
        if issue["quote_line"] is None:
            report.error("E06", "缺少引用行（quote_line_template 已配置）", issue["h1_line"] or 1)
        else:
            match = pattern.match(issue["quote_line"])
            if not match:
                report.error("E06", "引用行不符合 quote_line_template", issue["quote_line_line"])
            elif match.group("date") != date:
                report.error("E06", f"引用行日期 {match.group('date')} 与 frontmatter date {date} 不一致", issue["quote_line_line"])

    expected = [c.nfc(s["heading"]) for s in cfg["sections"]]
    actual = [s["heading"] for s in issue["sections"]]
    if actual != expected:
        report.error("E07", f"板块标题/顺序不符: 期望 {expected}，实际 {actual}", issue["sections"][0]["line"] if issue["sections"] else 0)

    separator = cfg.get("separator", "---")
    if separator:
        separators = set(issue["separators"])
        for index, section in enumerate(issue["sections"]):
            start = issue["quote_line_line"] or issue["h1_line"] if index == 0 else issue["sections"][index - 1]["line"]
            if not any(start < sep < section["line"] for sep in separators):
                report.error("E08", f"板块 '{section['heading']}' 前缺少分隔行 '{separator}'", section["line"])

    containers_on = cfg["card"]["containers"]
    allowed_by_heading = {c.nfc(s["heading"]): set(s.get("card_types", [])) for s in cfg["sections"]}
    for line, content in issue["unknown_containers"]:
        report.error("E09", f"不支持的容器语法: {content}", line)
    for container in issue["containers"]:
        if container["close_line"] is None:
            report.error("E09", f"::: card {container['type']} 容器未闭合", container["open_line"])
    if containers_on:
        for section in issue["sections"]:
            allowed = allowed_by_heading.get(section["heading"], set())
            for entry in section["entries"]:
                if entry["card_type"] is None:
                    report.error("E09", f"条目未包在 ::: card 容器中（card.containers=true）", entry["line"])
                elif allowed and entry["card_type"] not in allowed:
                    report.error("E09", f"card 类型 '{entry['card_type']}' 不在板块 '{section['heading']}' 允许集合 {sorted(allowed)}", entry["line"])
    else:
        for section in issue["sections"]:
            for entry in section["entries"]:
                if entry["card_type"] is not None:
                    report.error("E09", "配置未开启 card.containers，但条目使用了 card 容器", entry["line"])

    entry_cfg = cfg["entry"]
    required_fields = entry_cfg.get("required_fields", [])
    for section in issue["sections"]:
        for position, entry in enumerate(section["entries"], start=1):
            parsed = entry["parsed"]
            if parsed is None:
                report.error("E10", f"条目 H3 不符合 '### N. [标签] [标题](url)' 模式: {entry['heading']}", entry["line"])
                continue
            if entry_cfg.get("tag_required") and not parsed["tag"]:
                report.error("E10", "条目缺少 [标签]（entry.tag_required=true）", entry["line"])
            if parsed["number"] != position:
                report.error("E11", f"条目编号 {parsed['number']} 不连续（应为 {position}）", entry["line"])
            fields = c.apply_field_aliases(entry["fields"], cfg)
            for field in required_fields:
                if not fields.get(field, "").strip():
                    report.error("E12", f"条目缺少字段: {field}", entry["line"])
            carrier_field = entry_cfg.get("carrier_field", "")
            carrier_pattern = entry_cfg.get("carrier_pattern", "")
            if carrier_field and carrier_pattern and carrier_field in fields:
                if not re.match(carrier_pattern, fields[carrier_field]):
                    report.warn("W03", f"字段 '{carrier_field}' 不符合惯用格式: {fields[carrier_field]}", entry["field_lines"].get(carrier_field, entry["line"]))
            if cfg.get("quote_max_chars", 0):
                for name, value in fields.items():
                    for match in QUOTE_RE.finditer(value):
                        quoted = next(g for g in match.groups() if g is not None)
                        if len(quoted) > cfg["quote_max_chars"]:
                            report.warn("W01", f"直接引文 {len(quoted)} 字超过上限 {cfg['quote_max_chars']}", entry["field_lines"].get(name, entry["line"]))
            persona = cfg.get("persona", "")
            if persona and "团队参考" in fields and persona not in fields["团队参考"]:
                report.warn("W04", f"团队参考未体现人设 '{persona}'", entry["field_lines"].get("团队参考", entry["line"]))

    for section in issue["sections"]:
        if not section["entries"] and not section["placeholder"]:
            report.error("E14", f"板块 '{section['heading']}' 既无条目也无空板块占位 '{cfg['empty_section_placeholder']}'", section["line"])
        if section["entries"] and section["placeholder"]:
            report.error("E14", f"板块 '{section['heading']}' 同时含条目与空板块占位", section["line"])

    for lineno, line in enumerate(text.splitlines(), start=1):
        if BAD_LINK_RE.search(line):
            report.error("E13", f"存在非 http(s) 或括号不闭合的链接: {line.strip()[:60]}", lineno)

    all_urls = c.extract_urls(text)
    seen = set()
    for url in all_urls:
        if url in seen:
            report.warn("W02", f"URL 在文件内重复: {url}", 0)
        seen.add(url)

    if history is not None:
        hist_urls, hist_tags, hist_numbers = history
        for url in seen:
            if url in hist_urls:
                report.error("E16", f"URL 与历史期刊重复（{hist_urls[url]}）: {url}", 0)
        if number is not None and (number - 1) not in hist_numbers and number != min(hist_numbers | {number}):
            report.error("E16", f"期号 {number} 不连续（缺少第 {number - 1} 期），如需跳号请加 --allow-gap", 0)
        if isinstance(tags, list):
            for tag in tags:
                if hist_tags and tag not in hist_tags:
                    report.warn("W05", f"标签 '{tag}' 为历史未用过的新标签", 2)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验周刊 issue markdown 格式")
    parser.add_argument("files", nargs="+", metavar="FILE")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--strict", action="store_true", help="警告也视为失败")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON 输出")
    parser.add_argument("--with-history", action="store_true", help="启用 E16/W05 历史比对")
    parser.add_argument("--issues-dir", help="历史期刊目录（默认 cwd 下 issues_subdir）")
    parser.add_argument("--allow-gap", action="store_true", help="允许期号跳号")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    results = []
    failed = False
    for raw in args.files:
        path = Path(raw)
        report = Report()
        hist = None
        if args.with_history:
            if args.issues_dir:
                issues_dir = Path(args.issues_dir)
            elif path.parent.name == cfg["issues_subdir"]:
                issues_dir = path.parent
            else:
                issues_dir = c.find_issues_dir(cfg)
            if issues_dir is None or not issues_dir.is_dir():
                c.die(f"历史期刊目录不存在: {issues_dir}")
            urls, tags, numbers = load_history(issues_dir, cfg, path)
            if args.allow_gap:
                numbers = set(range(1, max(numbers | {1}) + 2))
            hist = (urls, tags, numbers)
        validate(path, cfg, report, history=hist)
        ok = not report.errors and not (args.strict and report.warnings)
        failed = failed or not ok
        results.append({"file": str(path), "ok": ok, "errors": report.errors, "warnings": report.warnings})
        if not args.as_json:
            for item in report.errors:
                suffix = f" (line {item['line']})" if item["line"] else ""
                print(f"[ERROR] {item['rule']}: {item['message']}{suffix}")
            for item in report.warnings:
                suffix = f" (line {item['line']})" if item["line"] else ""
                print(f"[WARN] {item['rule']}: {item['message']}{suffix}")
            status = "PASS" if ok else "FAIL"
            print(f"{status}: {path} — {len(report.errors)} errors, {len(report.warnings)} warnings")
    if args.as_json:
        c.emit_json({"results": results, "ok": not failed})
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
