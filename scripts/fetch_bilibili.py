#!/usr/bin/env python3
"""Fetch bilibili video metadata (title / uploader / duration) as a pool entry.

Input: BV ids or bilibili video URLs. With --pool + --section the entry is appended
to that pool section (existing lines are never modified).

Exit codes: 0 = all fetched, 1 = at least one video failed, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402
import _pool  # noqa: E402

API = "https://api.bilibili.com/x/web-interface/view"
BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def extract_bv(text: str):
    match = BV_RE.search(text.strip())
    return match.group(1) if match else None


def minutes(seconds: int) -> int:
    return max(1, math.ceil(seconds / 60))


def fetch(bvid: str) -> dict:
    params = urllib.parse.urlencode({"bvid": bvid})
    request = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": UA, "Referer": "https://www.bilibili.com"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            if payload.get("code") != 0:
                raise ValueError(f"code={payload.get('code')} {payload.get('message')}")
            return payload["data"]
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(str(last_error))


def entry_fields(data: dict, bvid: str) -> dict:
    owner = (data.get("owner") or {}).get("name") or "未知 UP 主"
    return {
        "链接": f"https://www.bilibili.com/video/{bvid}",
        "来源": f"B 站 · {owner}",
        "类型": "",
        "标签": "",
        "时长": f"{minutes(int(data.get('duration') or 0))} 分钟",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取 B 站视频元信息，生成/追加素材池条目")
    parser.add_argument("videos", nargs="+", metavar="BV|URL", help="BV 号或 B 站视频链接")
    parser.add_argument("--pool", help="素材池文件（与 --section 一起用时把条目追加进去）")
    parser.add_argument("--section", help="追加到哪个板块（板块标题需与预设一致）")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if args.pool and not args.section:
        c.die("--pool 需与 --section 一起使用")
    cfg = c.load_config(args.config)

    pool_text = None
    if args.pool:
        pool_path = Path(args.pool)
        if not pool_path.exists():
            c.die(f"素材池不存在: {pool_path}")
        pool_text = pool_path.read_text(encoding="utf-8")
        headings = [section["heading"] for section in _pool.parse(pool_text, cfg)["sections"]]
        if c.nfc(args.section.strip()) not in [c.nfc(h) for h in headings]:
            c.die(f"板块不存在: {args.section}\n可用板块: {' / '.join(headings) or '（池里没有 ## 板块）'}")

    results = []
    failed = 0
    for raw in args.videos:
        bvid = extract_bv(raw)
        if bvid is None:
            results.append({"input": raw, "ok": False, "error": "无法解析 BV 号"})
            failed += 1
            continue
        try:
            data = fetch(bvid)
        except RuntimeError as exc:
            results.append({"input": raw, "ok": False, "error": f"请求失败: {exc}"})
            failed += 1
            continue
        results.append(
            {
                "input": raw,
                "ok": True,
                "bvid": bvid,
                "title": data.get("title", ""),
                "owner": (data.get("owner") or {}).get("name", ""),
                "duration_seconds": data.get("duration"),
                "fields": entry_fields(data, bvid),
            }
        )

    for item in results:
        if not item["ok"]:
            print(f"[ERROR] {item['input']}: {item['error']}", file=sys.stderr)

    if args.pool:
        written = 0
        for item in results:
            if not item["ok"]:
                continue
            index = _pool.section_entry_count(pool_text, cfg, args.section) + 1
            pool_text = _pool.insert_entry(pool_text, args.section, _pool.render_entry(index, item["title"], item["fields"], cfg))
            written += 1
        Path(args.pool).write_text(pool_text, encoding="utf-8")

    if args.as_json:
        c.emit_json({"ok": not failed, "results": results, "pool": args.pool, "written": written if args.pool else 0})
    else:
        for item in results:
            if not item["ok"]:
                continue
            block = _pool.render_entry(1, item["title"], item["fields"], cfg)
            print(block)
            print()
        if args.pool:
            print(f"已追加 {written} 条到 {args.pool} 的「{args.section}」板块（勾选 [x] 后才会进 issue）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
