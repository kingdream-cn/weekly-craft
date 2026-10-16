"""Shared helpers for weekly-craft scripts. Python 3.9+, standard library only."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PRESETS_DIR = SKILL_ROOT / "presets"

DEFAULTS = {
    "site_name": "周刊",
    "title_template": "{site_name} - 第 {number} 期",
    "issue_filename": "issue-{number}.md",
    "issues_subdir": "issues",
    "pool_dir": "sources",
    "pool_filename": "issue-{number}-pool.md",
    "sections": [
        {"heading": "本周要点", "card_types": []},
        {"heading": "内容精选", "card_types": []},
        {"heading": "工具与项目", "card_types": []},
    ],
    "separator": "---",
    "empty_section_placeholder": "> *本期暂无收录。*",
    "quote_line_template": "",
    "entry": {
        "required_fields": ["摘要"],
        "field_aliases": {},
        "tag_required": False,
        "carrier_field": "",
        "carrier_pattern": "",
    },
    "card": {"containers": False, "colors": {}},
    "frontmatter": {
        "required": ["title", "date", "description", "tags"],
        "tags_min": 0,
        "tags_max": 0,
        "description_max_chars": 0,
    },
    "quote_max_chars": 0,
    "persona": "",
    "dedup": {
        "title_threshold": 0.85,
        "url_strip_params": ["utm_*", "spm", "vd_source"],
    },
    "sources": {"arxiv_categories": [], "github_topics": [], "sites": []},
    "repo": {"remote": "", "branch": "main", "workdir": ""},
}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_json_file(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        die(f"配置文件不存在: {path}")
    except json.JSONDecodeError as exc:
        die(f"配置文件 JSON 解析失败: {path}: {exc}")
    if not isinstance(data, dict):
        die(f"配置文件顶层必须是对象: {path}")
    return data


def _resolve_extends(value, origin: Path, visited: set) -> dict:
    if isinstance(value, str):
        candidate = PRESETS_DIR / f"{value}.json"
        if not candidate.exists():
            candidate = (origin.parent / value).resolve()
        target = candidate
    else:
        target = Path(value)
        if not target.is_absolute():
            target = (origin.parent / target).resolve()
    key = str(target)
    if key in visited:
        die(f"extends 循环引用: {key}")
    visited.add(key)
    return _load_config_file(target, visited)


def _load_config_file(path: Path, visited: set) -> dict:
    data = load_json_file(path)
    extends = data.pop("extends", None)
    base = {}
    if extends:
        base = _resolve_extends(extends, path, visited)
    return deep_merge(base, data)


def load_config(explicit: str | None = None) -> dict:
    """Resolution chain: --config > $WEEKLY_CONFIG > cwd/weekly.config.json > built-in defaults."""
    visited: set = set()
    user: dict = {}
    path: Path | None = None
    if explicit:
        path = Path(explicit).resolve()
    elif os.environ.get("WEEKLY_CONFIG"):
        path = Path(os.environ["WEEKLY_CONFIG"]).resolve()
    else:
        cwd_candidate = Path.cwd() / "weekly.config.json"
        if cwd_candidate.exists():
            path = cwd_candidate
    if path is not None:
        user = _load_config_file(path, visited)
    return deep_merge(DEFAULTS, user)


def die(message: str, code: int = 2) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    sys.exit(code)


def emit_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def parse_frontmatter(text: str):
    """Parse the YAML subset used by weekly issues: scalars and flat lists."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return None, text
    meta: dict = {}
    current_key = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            current_key, value = match.group(1), match.group(2).strip()
            if value == "":
                meta[current_key] = []
            else:
                meta[current_key] = _scalar(value)
                current_key = None
        elif line.strip().startswith("- ") and current_key is not None:
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(_scalar(line.strip()[2:]))
        elif line.startswith((" ", "\t")) and current_key is not None:
            if isinstance(meta.get(current_key), str):
                meta[current_key] += " " + line.strip()
    return meta, "\n".join(lines[end + 1:])


ENTRY_HEADING_RE = re.compile(
    r"^###\s+(?P<num>\d+)\.\s*(?:\[(?P<tag>[^\]]+)\]\s*)?\[(?P<title>[^\]]+)\]\((?P<url>https?://[^)\s]+)\)\s*$"
)
FIELD_BULLET_RE = re.compile(r"^-\s+\*\*(?P<label>[^*]+?)\*\*\s*[:：]?\s*(?P<rest>.*)$")
URL_RE = re.compile(r"\]\((https?://[^)\s]+)\)")
CARD_OPEN_RE = re.compile(r"^:::\s*card\s+(?P<type>\S+)\s*$")
CARD_CLOSE_RE = re.compile(r"^:::\s*$")


def parse_entry_heading(line: str):
    match = ENTRY_HEADING_RE.match(line.strip())
    if not match:
        return None
    return {
        "number": int(match.group("num")),
        "tag": match.group("tag"),
        "title": match.group("title"),
        "url": match.group("url"),
    }


def parse_issue(text: str, placeholder: str | None = None) -> dict:
    """Parse an issue markdown file into a structured dict (line numbers are 1-based)."""
    meta, body = parse_frontmatter(text)
    lines = body.splitlines()
    offset = len(text.splitlines()) - len(lines)
    issue = {
        "frontmatter": meta,
        "h1": None,
        "h1_line": 0,
        "quote_line": None,
        "quote_line_line": 0,
        "sections": [],
        "separators": [],
        "containers": [],
        "unknown_containers": [],
    }
    section = None
    card = None
    entry = None
    field_name = None
    before_first_section = True
    for index, raw in enumerate(lines):
        lineno = index + 1 + offset
        line = raw.rstrip()
        stripped = line.strip()
        if CARD_OPEN_RE.match(stripped):
            card = {
                "type": CARD_OPEN_RE.match(stripped).group("type"),
                "open_line": lineno,
                "close_line": None,
            }
            issue["containers"].append(card)
            field_name = None
            continue
        if CARD_CLOSE_RE.match(stripped):
            if card is None:
                issue["unknown_containers"].append((lineno, stripped))
            else:
                card["close_line"] = lineno
                card = None
            field_name = None
            continue
        if stripped.startswith(":::"):
            issue["unknown_containers"].append((lineno, stripped))
            field_name = None
            continue
        if stripped == "---":
            issue["separators"].append(lineno)
            field_name = None
            continue
        if stripped.startswith("# "):
            issue["h1"] = stripped[2:].strip()
            issue["h1_line"] = lineno
            field_name = None
            continue
        if before_first_section and stripped.startswith("> ") and issue["quote_line"] is None:
            issue["quote_line"] = stripped
            issue["quote_line_line"] = lineno
            field_name = None
            continue
        if stripped.startswith("## "):
            before_first_section = False
            section = {
                "heading": nfc(stripped[3:].strip()),
                "line": lineno,
                "entries": [],
                "placeholder": False,
            }
            issue["sections"].append(section)
            card = None
            entry = None
            field_name = None
            continue
        if section is not None and placeholder is not None and stripped == placeholder.strip():
            section["placeholder"] = True
            continue
        if stripped.startswith("### ") and section is not None:
            parsed = parse_entry_heading(stripped)
            entry = {
                "heading": stripped,
                "line": lineno,
                "card_type": card["type"] if card else None,
                "parsed": parsed,
                "fields": {},
                "field_lines": {},
                "urls": URL_RE.findall(stripped),
            }
            section["entries"].append(entry)
            field_name = None
            continue
        field_match = FIELD_BULLET_RE.match(stripped)
        if field_match and entry is not None:
            field_name = field_match.group("label").strip().rstrip("：:")
            entry["fields"][field_name] = field_match.group("rest").strip()
            entry["field_lines"][field_name] = lineno
            entry["urls"].extend(URL_RE.findall(field_match.group("rest")))
            continue
        if entry is not None and field_name is not None and stripped:
            entry["fields"][field_name] += " " + stripped
            entry["urls"].extend(URL_RE.findall(stripped))
            continue
        if not stripped:
            field_name = None
    return issue


def apply_field_aliases(fields: dict, cfg: dict) -> dict:
    aliases = cfg.get("entry", {}).get("field_aliases", {}) or {}
    out = {}
    for name, value in fields.items():
        out[aliases.get(name, name)] = value
    return out


def template_to_regex(template: str, number_group: str = r"(?P<number>\d+)") -> re.Pattern:
    pattern = re.escape(template).replace(re.escape("{number}"), number_group)
    return re.compile(pattern)


def issue_number_from_filename(name: str, cfg: dict):
    match = template_to_regex(cfg["issue_filename"]).match(name)
    if not match:
        return None
    return int(match.group("number"))


def filename_for_number(number: int, cfg: dict) -> str:
    return cfg["issue_filename"].replace("{number}", str(number))


def pool_filename_for_number(number: int, cfg: dict) -> str:
    return cfg["pool_filename"].replace("{number}", str(number))


def title_for_number(number: int, cfg: dict) -> str:
    return cfg["title_template"].replace("{site_name}", cfg["site_name"]).replace("{number}", str(number))


def find_issues_dir(cfg: dict, base: Path | None = None) -> Path | None:
    base = base or Path.cwd()
    candidate = base / cfg["issues_subdir"]
    if candidate.is_dir():
        return candidate
    return None


def scan_issue_numbers(issues_dir: Path, cfg: dict) -> list:
    numbers = []
    for path in sorted(issues_dir.glob("*.md")):
        number = issue_number_from_filename(path.name, cfg)
        if number is not None:
            numbers.append(number)
    return sorted(numbers)


def extract_urls(text: str) -> list:
    return URL_RE.findall(text)
