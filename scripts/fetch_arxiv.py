#!/usr/bin/env python3
"""Fetch recent arXiv papers as weekly candidates (read-only, optional helper).

Exit codes: 0 = ok, 1 = network failure after retries, 2 = argument error.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402

ATOM = "{http://www.w3.org/2005/Atom}"
API = "http://export.arxiv.org/api/query"


def fetch(query: str, max_results: int) -> list:
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 0,
            "max_results": max_results,
        }
    )
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": "weekly-craft"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
            return parse(payload)
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    print(f"[ERROR] arXiv API 请求失败（重试 3 次）: {last_error}", file=sys.stderr)
    sys.exit(1)


def parse(payload: bytes) -> list:
    root = ET.fromstring(payload)
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        title = re.sub(r"\s+", " ", (entry.findtext(f"{ATOM}title") or "").strip())
        summary = re.sub(r"\s+", " ", (entry.findtext(f"{ATOM}summary") or "").strip())
        authors = [a.findtext(f"{ATOM}name") or "" for a in entry.findall(f"{ATOM}author")]
        link = ""
        for child in entry.findall(f"{ATOM}link"):
            if child.get("type") == "text/html" or not link:
                link = child.get("href", "")
        papers.append(
            {
                "title": title,
                "authors": authors[:3] + (["et al."] if len(authors) > 3 else []),
                "published": (entry.findtext(f"{ATOM}published") or "")[:10],
                "link": link,
                "summary_first_sentence": summary.split("。")[0].split(". ")[0][:200],
            }
        )
    return papers


def main() -> int:
    parser = argparse.ArgumentParser(description="arXiv 周候选论文检索")
    parser.add_argument("--query", help="arXiv 查询式（默认由配置 sources.arxiv_categories 生成）")
    parser.add_argument("--days", type=int, default=7, help="回溯天数（用于提示，过滤 published）")
    parser.add_argument("--max", type=int, default=30, dest="max_results")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    query = args.query
    if not query:
        categories = cfg.get("sources", {}).get("arxiv_categories", [])
        if not categories:
            c.die("未配置 sources.arxiv_categories，请用 --query 显式指定")
        query = " OR ".join(f"cat:{cat}" for cat in categories)
    cutoff = (date.today() - timedelta(days=args.days)).isoformat()
    papers = [p for p in fetch(query, args.max_results) if p["published"] >= cutoff]
    if args.as_json:
        c.emit_json({"query": query, "cutoff": cutoff, "count": len(papers), "papers": papers})
    else:
        print(f"query: {query}  cutoff: {cutoff}  count: {len(papers)}")
        for paper in papers:
            authors = ", ".join(paper["authors"])
            print(f"- [{paper['published']}] {paper['title']} — {authors}\n  {paper['link']}\n  {paper['summary_first_sentence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
