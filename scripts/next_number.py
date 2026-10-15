#!/usr/bin/env python3
"""Query the next issue number from local issues dir or the remote repo (read-only).

Exit codes: 0 = ok, 2 = environment/argument error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402


def remote_names(remote: str, subdir: str, branch: str) -> list:
    match = re.match(r"(?:https?://github\.com/|git@github\.com:)(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$", remote)
    if not match:
        c.die(f"无法从 remote 解析 owner/repo: {remote}")
    url = f"https://api.github.com/repos/{match.group('owner')}/{match.group('repo')}/contents/{subdir}?ref={branch}"
    request = urllib.request.Request(url, headers={"User-Agent": "weekly-craft", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            entries = json.load(response)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        c.die(f"查询远端 issues 目录失败: {exc}")
    return [entry["name"] for entry in entries if isinstance(entry, dict) and entry.get("type") == "file"]


def compute_next(cfg: dict, base: Path | None = None, remote: str | None = None):
    """Return (next_number, max_existing, source). source in {local, remote}."""
    numbers: list = []
    source = "none"
    base = base or Path.cwd()
    issues_dir = base / cfg["issues_subdir"]
    if issues_dir.is_dir():
        numbers = c.scan_issue_numbers(issues_dir, cfg)
        source = "local"
    remote = remote or cfg["repo"]["remote"]
    if not numbers and remote:
        names = remote_names(remote, cfg["issues_subdir"], cfg["repo"]["branch"])
        numbers = sorted(n for n in (c.issue_number_from_filename(name, cfg) or 0 for name in names) if n)
        source = "remote"
    if source == "none":
        c.die("本地 issues 目录与远端 remote 均不可用")
    return (max(numbers) + 1 if numbers else 1), (max(numbers) if numbers else 0), source


def main() -> int:
    parser = argparse.ArgumentParser(description="查询下一期期号")
    parser.add_argument("--repo-dir", help="本地周刊仓库目录（含 issues/ 子目录）")
    parser.add_argument("--remote", help="GitHub remote 地址（本地无 issues 目录时只读查询）")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    cfg = c.load_config(args.config)
    base = Path(args.repo_dir) if args.repo_dir else Path.cwd()
    nxt, max_existing, source = compute_next(cfg, base, args.remote)
    if args.as_json:
        c.emit_json({"next": nxt, "max_existing": max_existing, "source": source})
    else:
        print(nxt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
