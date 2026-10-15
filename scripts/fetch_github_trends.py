#!/usr/bin/env python3
"""Fetch weekly trending GitHub repositories as candidates (read-only, optional helper).

Exit codes: 0 = ok, 1 = network failure after retries, 2 = argument error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402

API = "https://api.github.com/search/repositories"


def fetch(query: str, max_results: int) -> list:
    params = urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": max_results}
    )
    headers = {"User-Agent": "weekly-craft", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print("[WARN] 未设置 GITHUB_TOKEN，未认证限流 60 req/h", file=sys.stderr)
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(f"{API}?{params}", headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            return payload.get("items", [])
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    print(f"[ERROR] GitHub Search API 请求失败（重试 3 次）: {last_error}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub 周趋势仓库检索")
    parser.add_argument("--topic", action="append", help="GitHub topic（可多次；默认取配置 sources.github_topics）")
    parser.add_argument("--days", type=int, default=7, help="创建时间回溯天数")
    parser.add_argument("--min-stars", type=int, default=50, help="最低 star 数过滤")
    parser.add_argument("--max", type=int, default=20, dest="max_results")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    topics = args.topic or cfg.get("sources", {}).get("github_topics", [])
    cutoff = (date.today() - timedelta(days=args.days)).isoformat()
    clauses = [f"created:>{cutoff}"]
    if topics:
        clauses.append("(" + " OR ".join(f"topic:{t}" for t in topics) + ")")
    query = " ".join(clauses)
    items = [item for item in fetch(query, args.max_results) if item.get("stargazers_count", 0) >= args.min_stars]
    repos = [
        {
            "full_name": item["full_name"],
            "stars": item["stargazers_count"],
            "language": item.get("language"),
            "created_at": item.get("created_at", "")[:10],
            "description": (item.get("description") or "").strip(),
            "url": item["html_url"],
        }
        for item in items
    ]
    if args.as_json:
        c.emit_json({"query": query, "cutoff": cutoff, "count": len(repos), "repos": repos})
    else:
        print(f"query: {query}  cutoff: {cutoff}  count: {len(repos)}")
        for repo in repos:
            print(f"- {repo['full_name']} ★{repo['stars']} [{repo['language'] or '-'}] {repo['url']}\n  {repo['description']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
