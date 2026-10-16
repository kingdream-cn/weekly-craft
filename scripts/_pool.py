"""素材池（single-file candidate pool）格式的解析与写入。Python 3.9+，仅标准库。

池子结构：frontmatter + 若干 `## 板块` + 若干 `### [ ] N. 标题` 条目，
条目下是 `- 键：值` 行（键为 链接/来源/类型/标签/时长 + 预设必填字段）。
"""

from __future__ import annotations

import re

import _common as c

SECTION_RE = re.compile(r"^##\s+(?P<heading>\S.*?)\s*$")
ENTRY_RE = re.compile(r"^###\s*\[(?P<mark>[ xX])\]\s*(?P<num>\d+)?\s*[.、]?\s*(?P<title>.*?)\s*$")
FIELD_RE = re.compile(r"^-\s*(?P<key>[^*\s][^:：]*?)\s*[:：]\s*(?P<value>.*?)\s*$")

BASE_KEYS = ["链接", "来源", "类型", "标签", "时长"]
SECTION_KEY = "板块"


def entry_keys(cfg: dict, extra=None) -> list:
    """Stable key order for a pool entry: base keys, then preset required fields, then extras."""
    keys = list(BASE_KEYS)
    for name in cfg.get("entry", {}).get("required_fields", []) or []:
        if name not in keys:
            keys.append(name)
    for name in extra or []:
        if name not in keys:
            keys.append(name)
    return keys


def parse(text: str, cfg: dict) -> dict:
    """Parse pool text into {frontmatter, sections:[{heading, entries:[{selected,title,fields}]}], loose}."""
    meta, body = c.parse_frontmatter(text)
    sections: list = []
    loose: list = []
    current = None
    in_comment = False
    for index, raw in enumerate(body.splitlines()):
        stripped = raw.strip()
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            in_comment = "-->" not in stripped
            continue
        if not stripped or stripped.startswith("# ") or stripped.startswith(">"):
            continue
        match = SECTION_RE.match(stripped)
        if match:
            current = {"heading": match.group("heading"), "entries": [], "line": index + 1}
            sections.append(current)
            continue
        match = ENTRY_RE.match(stripped)
        if match:
            if current is None:
                loose.append(stripped)
                continue
            current["entries"].append(
                {
                    "selected": match.group("mark").lower() == "x",
                    "title": match.group("title"),
                    "fields": {},
                    "line": index + 1,
                }
            )
            continue
        key = value = None
        match = FIELD_RE.match(stripped)
        if match:
            key, value = match.group("key").strip(), match.group("value")
        else:
            match = c.FIELD_BULLET_RE.match(stripped)
            if match:
                key, value = match.group("label").strip().rstrip("：:"), match.group("rest")
        if key is not None and current and current["entries"]:
            current["entries"][-1]["fields"][key] = value.strip()
            continue
        loose.append(stripped)
    return {"frontmatter": meta or {}, "sections": sections, "loose": loose}


def render_entry(index: int, title: str, fields: dict, cfg: dict) -> str:
    lines = [f"### [ ] {index}. {title or '待定标题'}"]
    for key in entry_keys(cfg, fields.keys()):
        lines.append(f"- {key}：{fields.get(key, '')}")
    return "\n".join(lines)


def find_section(text: str, heading: str):
    """Return (start_index, end_index) line indices of the section body, or None."""
    target = c.nfc(heading.strip())
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        match = SECTION_RE.match(line.strip())
        if match and c.nfc(match.group("heading")) == target:
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if SECTION_RE.match(lines[index].strip()):
            end = index
            break
    return start, end


def section_entry_count(text: str, cfg: dict, heading: str) -> int:
    parsed = parse(text, cfg)
    target = c.nfc(heading.strip())
    for section in parsed["sections"]:
        if c.nfc(section["heading"]) == target:
            return len(section["entries"])
    return 0


def insert_entry(text: str, heading: str, block: str) -> str:
    """Insert block at the end of the matching section. Returns None when the section is absent."""
    span = find_section(text, heading)
    if span is None:
        return None
    start, end = span
    lines = text.splitlines()
    cut = end
    while cut - 1 > start and not lines[cut - 1].strip():
        cut -= 1
    new_lines = lines[:cut] + ["", *block.splitlines()] + lines[cut:]
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(new_lines) + suffix
