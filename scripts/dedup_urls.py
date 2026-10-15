#!/usr/bin/env python3
"""Check candidate URLs (and optionally titles) against past issues for duplicates.

Input: positional URLs, or --candidates FILE with one "URL" or "URL<TAB>title" per line.
Exit codes: 0 = checked (duplicates are information, not errors), 2 = environment error.
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402


def normalize(url: str, cfg: dict) -> str:
    parts = urlparse(url.strip())
    patterns = cfg.get("dedup", {}).get("url_strip_params", [])
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not any(fnmatch.fnmatch(key.lower(), pattern.lower()) for pattern in patterns)
    ]
    path = parts.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parts.scheme.lower(), parts.netloc.lower(), path, parts.params, urlencode(query), ""))


def load_history(issues_dir: Path, cfg: dict):
    """Return {normalized_url: (filename, entry_title)} and [(title, filename)]."""
    urls: dict = {}
    titles: list = []
    for path in sorted(issues_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        issue = c.parse_issue(text, placeholder=cfg["empty_section_placeholder"])
        for section in issue["sections"]:
            for entry in section["entries"]:
                title = entry["parsed"]["title"] if entry["parsed"] else entry["heading"]
                titles.append((title, path.name))
                for url in entry["urls"]:
                    urls.setdefault(normalize(url, cfg), (path.name, title))
    return urls, titles


def read_candidates(args) -> list:
    candidates = []
    if args.candidates:
        path = Path(args.candidates)
        if not path.exists():
            c.die(f"候选文件不存在: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                url, title = line.split("\t", 1)
                candidates.append((url.strip(), title.strip()))
            else:
                candidates.append((line, ""))
    for url in args.urls:
        candidates.append((url, ""))
    if not candidates:
        c.die("没有候选 URL（位置参数或 --candidates 文件）")
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="跨历史期刊 URL/标题去重检查")
    parser.add_argument("urls", nargs="*", metavar="URL")
    parser.add_argument("--candidates", help="候选文件，每行 URL 或 URL<TAB>标题")
    parser.add_argument("--issues-dir", help="历史期刊目录（默认 cwd 下 issues_subdir）")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--fuzzy", action="store_true", help="追加标题相似度检查")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    issues_dir = Path(args.issues_dir) if args.issues_dir else c.find_issues_dir(cfg)
    if issues_dir is None or not issues_dir.is_dir():
        c.die(f"历史期刊目录不存在: {issues_dir or ('cwd/' + cfg['issues_subdir'])}")
    hist_urls, hist_titles = load_history(issues_dir, cfg)
    threshold = cfg.get("dedup", {}).get("title_threshold", 0.85)

    new_items = []
    duplicates = []
    for url, title in read_candidates(args):
        norm = normalize(url, cfg)
        hit = hist_urls.get(norm)
        similarity = 0.0
        if hit is None and args.fuzzy and title:
            best_title, best_file, similarity = "", "", 0.0
            for hist_title, hist_file in hist_titles:
                ratio = difflib.SequenceMatcher(None, title, hist_title).ratio()
                if ratio > similarity:
                    best_title, best_file, similarity = hist_title, hist_file, ratio
            if similarity >= threshold:
                hit = (best_file, best_title)
        if hit:
            duplicates.append({"url": url, "found_in": hit[0], "title": hit[1], "similarity": round(similarity, 3)})
        else:
            new_items.append(url)

    if args.as_json:
        c.emit_json({"new": new_items, "duplicates": duplicates})
    else:
        for url in new_items:
            print(f"NEW  {url}")
        for item in duplicates:
            print(f"DUP  {item['url']}  ← {item['found_in']} 『{item['title']}』")
        print(f"{len(new_items)} new / {len(duplicates)} dup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
