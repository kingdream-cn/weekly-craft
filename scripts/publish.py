#!/usr/bin/env python3
"""Publish a validated issue into the newsletter repo. Two-stage by design:
default is dry-run (local commit only); --push performs the actual push and
must only be added after explicit user consent. Force push is impossible.

Exit codes: 0 = ok, 1 = validation/number/dirty/push failure, 2 = environment error.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402
import validate_issue  # noqa: E402

HISTORY_NAME = ".publish-history.jsonl"


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, rule, message, line=0):
        self.errors.append({"rule": rule, "line": line, "message": message})

    def warn(self, rule, message, line=0):
        self.warnings.append({"rule": rule, "line": line, "message": message})


def git(args: list, cwd: Path, check: bool = True):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"[ERROR] git {' '.join(args)} 失败:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result


def log_history(entry: dict) -> None:
    entry = {"time": datetime.now(timezone.utc).isoformat(), **entry}
    with Path(HISTORY_NAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="发布 issue 到周刊仓库（默认 dry-run）")
    parser.add_argument("file")
    parser.add_argument("--repo-dir", help="本地克隆目录（默认取配置 repo.workdir，否则临时克隆）")
    parser.add_argument("--remote", help="覆盖配置 repo.remote")
    parser.add_argument("--push", action="store_true", help="实际推送（需用户明确同意；默认仅 dry-run）")
    parser.add_argument("--message", help="commit message（默认 'publish: <title>'）")
    parser.add_argument("--allow-dirty", action="store_true", help="工作区存在其他改动时仍继续")
    parser.add_argument("--force-content", action="store_true", help="跳过校验拒绝（必须同时 --push，慎用）")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    src = Path(args.file)
    if not src.exists():
        c.die(f"输入文件不存在: {src}")
    cfg = c.load_config(args.config)

    report = Report()
    validate_issue.validate(src, cfg, report)
    if report.errors:
        if not (args.force_content and args.push):
            for item in report.errors:
                print(f"[ERROR] {item['rule']}: {item['message']} (line {item['line']})")
            print("[ERROR] 校验未通过，拒绝发布（逃生门：--force-content 且 --push）", file=sys.stderr)
            return 1
        print("[WARN] --force-content 生效：跳过上述校验错误继续发布", file=sys.stderr)

    remote = args.remote or cfg["repo"]["remote"]
    branch = cfg["repo"]["branch"]
    temp_dir = None
    if args.repo_dir:
        workdir = Path(args.repo_dir).expanduser()
    elif cfg["repo"]["workdir"]:
        workdir = Path(cfg["repo"]["workdir"]).expanduser()
    else:
        temp_dir = tempfile.mkdtemp(prefix="weekly-craft-publish-")
        workdir = Path(temp_dir) / "repo"
    print(f"[1/5] 准备仓库: {workdir}")
    if (workdir / ".git").exists():
        if remote:
            pull = git(["pull", "--rebase", "origin", branch], workdir, check=False)
            if pull.returncode != 0:
                git(["rebase", "--abort"], workdir, check=False)
                print("[ERROR] 同步仓库 pull --rebase 失败（远端存在冲突提交），已 abort，请人工处理", file=sys.stderr)
                log_history({"issue": src.name, "commit": None, "pushed": False, "result": "sync-conflict"})
                return 1
    elif remote:
        workdir.parent.mkdir(parents=True, exist_ok=True)
        clone = subprocess.run(["git", "clone", "--branch", branch, remote, str(workdir)], capture_output=True, text=True)
        if clone.returncode != 0:
            clone = subprocess.run(["git", "clone", remote, str(workdir)], capture_output=True, text=True)
        if clone.returncode != 0:
            print(f"[ERROR] clone 失败:\n{clone.stderr.strip()}", file=sys.stderr)
            return 2
    else:
        c.die("repo.remote 未配置，且 --repo-dir 指向的目录不是 git 仓库")

    issues_dir = workdir / cfg["issues_subdir"]
    issues_dir.mkdir(parents=True, exist_ok=True)
    target = issues_dir / src.name
    print(f"[2/5] 目标文件: {target}")
    identical = target.exists() and target.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")
    if target.exists() and not identical:
        print(f"[ERROR] 期号冲突：{target} 已存在且内容不同", file=sys.stderr)
        return 1

    sha = None
    if identical:
        sha = git(["rev-parse", "HEAD"], workdir).stdout.strip()
        if not args.push:
            print("目标文件内容已一致且未要求推送，无需操作")
            log_history({"issue": src.name, "commit": sha, "pushed": False, "result": "no-change"})
            return 0
        print(f"[3/5] 目标文件已在本地 commit（{sha[:8]}），直接进入推送阶段")
    else:
        status = git(["status", "--porcelain"], workdir).stdout.strip().splitlines()
        if status and not args.allow_dirty:
            print("[ERROR] 工作区存在其他未提交改动，拒绝继续（--allow-dirty 可跳过）:", file=sys.stderr)
            for line in status:
                print(f"  {line}", file=sys.stderr)
            return 1
        shutil.copyfile(src, target)
        git(["add", "--", str(target.relative_to(workdir))], workdir)
        meta, _ = c.parse_frontmatter(src.read_text(encoding="utf-8"))
        title = (meta or {}).get("title", src.stem)
        message = args.message or f"publish: {title}"
        commit = git(["commit", "-m", message], workdir, check=False)
        if commit.returncode != 0:
            if "nothing to commit" in commit.stdout:
                print("无变更需要提交")
                return 0
            print(f"[ERROR] commit 失败:\n{commit.stderr.strip()}", file=sys.stderr)
            return 1
        sha = git(["rev-parse", "HEAD"], workdir).stdout.strip()
        print(f"[3/5] 本地 commit: {sha[:8]} — {message}")
        stat = git(["show", "--stat", "--oneline", "HEAD"], workdir).stdout.strip()
        print(stat)
        log_history({"issue": src.name, "commit": sha, "pushed": False, "result": "dry-run"})
        if not args.push:
            counts = git(["rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"], workdir, check=False)
            ahead_behind = counts.stdout.strip() if counts.returncode == 0 else "? ?"
            print(f"[4/5] DRY-RUN 完成（ahead/behind: {ahead_behind}）。加 --push 才会实际推送。")
            if args.as_json:
                c.emit_json({"dry_run": True, "commit": sha, "workdir": str(workdir), "ahead_behind": ahead_behind})
            return 0

    print(f"[4/5] 即将推送: remote={remote} branch={branch} 文件={[str(target.relative_to(workdir))]}")
    pull = git(["pull", "--rebase", "origin", branch], workdir, check=False)
    if pull.returncode != 0:
        git(["rebase", "--abort"], workdir, check=False)
        print("[ERROR] 推送前 pull --rebase 冲突，已 abort，请人工处理", file=sys.stderr)
        log_history({"issue": src.name, "commit": sha, "pushed": False, "result": "rebase-conflict"})
        return 1
    if not target.exists():
        print("[ERROR] rebase 后目标文件消失，请人工检查", file=sys.stderr)
        return 1
    push = subprocess.run(["git", "push", "origin", branch], cwd=workdir, capture_output=True, text=True)
    if push.returncode != 0:
        print(f"[ERROR] push 被拒（non-fast-forward 或其他）:\n{push.stderr.strip()}\n提示：先 pull --rebase 后重试，禁止 force push", file=sys.stderr)
        log_history({"issue": src.name, "commit": sha, "pushed": False, "result": "push-rejected"})
        return 1
    print(f"[5/5] 已推送。CI: 见 {remote} 的 Actions；线上页面稍后更新。")
    log_history({"issue": src.name, "commit": sha, "pushed": True, "result": "pushed"})
    if args.as_json:
        c.emit_json({"dry_run": False, "commit": sha, "pushed": True})
    return 0


if __name__ == "__main__":
    sys.exit(main())
