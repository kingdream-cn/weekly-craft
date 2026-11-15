#!/usr/bin/env python3
"""Preview publication without mutation; --commit writes locally, --push publishes.

Exit codes: 0 success, 1 content/Git precondition failure, 2 usage/environment error.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import _common as c
from _git import git, remote_key, relative_file, root
import validate_issue

HISTORY_NAME = '.publish-history.jsonl'


def log_history(entry, repo):
    path = Path(git(repo, 'rev-parse', '--git-path', HISTORY_NAME).stdout.strip())
    if not path.is_absolute():
        path = repo / path
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(), **entry}, ensure_ascii=False) + '\n')


def publish(src, cfg, workdir, *, commit=False, push=False, allow_dirty=False, message=None, force_content=False):
    workdir = root(workdir)
    if not src.is_file():
        raise ValueError('Input issue file does not exist')
    report = validate_issue.Report()
    validate_issue.validate(src, cfg, report)
    if report.errors and not (force_content and push):
        return {'errors': report.errors, 'warnings': report.warnings}, 1
    if c.issue_number_from_filename(src.name, cfg) is None:
        raise ValueError('Input filename must match the configured issue filename')
    branch = cfg['repo']['branch']
    current = git(workdir, 'branch', '--show-current').stdout.strip()
    if current != branch:
        raise ValueError('Checked-out branch differs from repo.branch; select the intended checkout first')
    actual = git(workdir, 'remote', 'get-url', 'origin', check=False)
    configured = cfg['repo'].get('remote', '')
    if configured and (actual.returncode or remote_key(configured) != remote_key(actual.stdout)):
        raise ValueError('origin differs from repo.remote; no repository files were changed')
    rel = relative_file(cfg['issues_subdir']) / src.name
    target = workdir / rel
    if not target.resolve().is_relative_to(workdir):
        raise ValueError('Publication target resolves outside the repository')
    content = src.read_text(encoding='utf-8')
    identical = target.exists() and target.read_text(encoding='utf-8') == content
    if target.exists() and not identical:
        raise ValueError('Issue number already exists with different content')
    dirty = bool(git(workdir, 'status', '--porcelain').stdout.strip())
    if dirty and not allow_dirty:
        raise ValueError('Working tree has changes; use an isolated checkout or explicitly --allow-dirty')
    # --allow-dirty preserves unrelated staged changes but never overwrites this target.
    if git(workdir, 'status', '--porcelain', '--', str(rel)).stdout.strip():
        raise ValueError('Publication target has uncommitted changes; review it first')
    result = {'dry_run': not (commit or push), 'pushed': False, 'commit': None,
              'branch': branch, 'remote': remote_key(actual.stdout) if not actual.returncode else '',
              'files': [rel.as_posix()], 'identical': identical, 'warnings': report.warnings}
    if not (commit or push):
        return result, 0
    if push:
        if actual.returncode:
            raise ValueError('Publishing requires an origin remote')
        git(workdir, 'fetch', '--no-tags', 'origin', branch)
        remote_head = git(workdir, 'rev-parse', 'FETCH_HEAD').stdout.strip()
        if git(workdir, 'merge-base', '--is-ancestor', remote_head, 'HEAD', check=False).returncode:
            raise ValueError('Remote has newer or conflicting commits; synchronize explicitly before publishing')
        ahead_files = [name for name in git(workdir, 'log', '--format=', '--name-only', f'{remote_head}..HEAD').stdout.splitlines() if name]
        if set(ahead_files) - {rel.as_posix()}:
            raise ValueError('Local unpublished commits include unrelated files; publish from an isolated branch')
    if not identical:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        git(workdir, 'add', '--', rel.as_posix())
        meta, _ = c.parse_frontmatter(content)
        git(workdir, 'commit', '--only', '-m', message or f"publish: {meta.get('title', src.stem)}", '--', rel.as_posix())
    elif git(workdir, 'ls-files', '--error-unmatch', '--', rel.as_posix(), check=False).returncode:
        raise ValueError('Identical target is not committed')
    result['commit'] = git(workdir, 'rev-parse', 'HEAD').stdout.strip()
    if push:
        # Explicit HEAD avoids accidentally pushing a different local branch ref.
        pushed = git(workdir, 'push', 'origin', f'HEAD:refs/heads/{branch}', check=False)
        if pushed.returncode:
            log_history({'issue': src.name, **result, 'result': 'push-rejected'}, workdir)
            raise ValueError('Push was rejected; local commit is preserved; inspect before retrying')
        result['pushed'] = True
    log_history({'issue': src.name, **result, 'result': 'pushed' if push else 'committed'}, workdir)
    return result, 0


def main():
    parser = argparse.ArgumentParser(description='发布预演默认只读；--commit 本地提交；--push 推送')
    parser.add_argument('file')
    parser.add_argument('--repo-dir', help='已有目标 Git 仓库，或配置 repo.workdir')
    parser.add_argument('--remote', help='覆盖 repo.remote，用于核对 origin')
    parser.add_argument('--commit', action='store_true', help='明确执行本地提交')
    parser.add_argument('--push', action='store_true', help='明确同意后的提交与推送')
    parser.add_argument('--message')
    parser.add_argument('--allow-dirty', action='store_true', help='保留其他改动，仅提交本期文件')
    parser.add_argument('--force-content', action='store_true', help='与 --push 配合的兼容内容校验绕过')
    parser.add_argument('--config')
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args()
    cfg = c.load_config(args.config)
    if args.remote:
        cfg['repo']['remote'] = args.remote
    directory = args.repo_dir or cfg['repo'].get('workdir')
    if not directory:
        parser.error('Provide --repo-dir or repo.workdir pointing to an existing clone')
    try:
        result, code = publish(Path(args.file).resolve(), cfg, Path(directory).expanduser().resolve(),
                               commit=args.commit, push=args.push, allow_dirty=args.allow_dirty,
                               message=args.message, force_content=args.force_content)
    except (ValueError, OSError) as error:
        # Only controlled ValueError messages; OSError paths may be private.
        message = str(error) if isinstance(error, ValueError) else 'Unable to read or write local files'
        result, code = {'error': message}, 1
    if args.as_json:
        c.emit_json(result)
    elif code:
        print('[ERROR] ' + json.dumps(result, ensure_ascii=False), file=sys.stderr)
    else:
        print(('DRY-RUN（目标文件、索引与提交均未修改）' if result['dry_run'] else
               '已推送' if result['pushed'] else '已本地提交') + ': ' + ', '.join(result['files']))
    return code


if __name__ == '__main__':
    sys.exit(main())
