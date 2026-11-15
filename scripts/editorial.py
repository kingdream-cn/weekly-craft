#!/usr/bin/env python3
"""Optional private-ledger-v1 adapter: connect once, prepare a pool, build a review pack.

Reads existing Git snapshots. Never changes a ledger, a public checkout, or a remote.
Per-issue editable source is pool.md; all other issue files are derived artifacts.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

import _common as c
import _pool
from _git import git, github_name, relative_file, root
import dedup_urls
import pool_to_issue
import preview
import validate_issue

PRIVATE_DIR = '.weekly-private'
STATE_REF = 'refs/remotes/origin/automation/state'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, text):
    """Atomic private artifacts; rerunning an interrupted generation is safe."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.weekly-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def one_line(value):
    return ' '.join(str(value or '').split())


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def source_key(url, cfg):
    """Supplement existing ledger dedup with the latest published snapshot."""
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower().removeprefix('www.')
    if host == 'arxiv.org':
        match = re.fullmatch(r'/(?:abs|pdf)/(.+?)(?:v\d+)?(?:\.pdf)?/?', parsed.path)
        if match:
            return 'arxiv:' + match[1].lower()
    if host in ('doi.org', 'dx.doi.org'):
        return 'doi:' + unquote(parsed.path).strip('/').lower()
    return dedup_urls.normalize(url, cfg)


def public_snapshot(repo, ref, cfg):
    head = git(repo, 'rev-parse', '--verify', f'{ref}^{{commit}}').stdout.strip()
    directory = relative_file(cfg['issues_subdir']).as_posix()
    paths = git(repo, 'ls-tree', '-r', '--name-only', head, '--', directory).stdout.splitlines()
    history = {}
    files = {}
    for path in paths:
        if c.issue_number_from_filename(Path(path).name, cfg) is None:
            continue
        text = git(repo, 'show', f'{head}:{path}').stdout
        files[path] = text
        for url in c.extract_urls(text):
            history.setdefault(source_key(url, cfg), path)
    return head, history, files


def connect(public, private, preset, output=None):
    public, private = root(public.resolve()), root(private.resolve())
    if public == private or public.is_relative_to(private) or private.is_relative_to(public):
        raise ValueError('Choose two separate Git repositories')
    public_name, private_name = github_name(public), github_name(private)
    if public_name == private_name:
        raise ValueError('Public and private repository identities must differ')
    directory = private / PRIVATE_DIR
    if not directory.resolve().is_relative_to(private):
        raise ValueError('Private work directory must stay inside the private checkout')
    path = output.resolve() if output else directory / 'weekly-craft.json'
    if not path.is_relative_to(directory.resolve()):
        raise ValueError('Keep this local connection config under the private .weekly-private directory')
    if path.exists():
        raise ValueError('Connection config already exists; edit it to change paths or presets')
    c.load_config(str(c.PRESETS_DIR / f'{preset}.json'))
    # Local exclusion supplements existing project ignores without changing tracked policy.
    if git(private, 'check-ignore', '-q', '--no-index', str(path.relative_to(private)), check=False).returncode:
        exclude = Path(git(private, 'rev-parse', '--git-path', 'info/exclude').stdout.strip())
        if not exclude.is_absolute():
            exclude = private / exclude
        existing = exclude.read_text(encoding='utf-8') if exclude.exists() else ''
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open('a', encoding='utf-8') as handle:
            handle.write(('\n' if existing and not existing.endswith('\n') else '') + '/.weekly-private/\n')
    write_json(path, {'extends': preset,
        'repo': {'remote': f'https://github.com/{public_name}.git', 'branch': 'main', 'workdir': str(public)},
        'editorial': {'adapter': 'private-ledger-v1', 'public_repo': str(public), 'private_repo': str(private),
                      'public_repository': public_name, 'private_repository': private_name,
                      'public_ref': 'refs/remotes/origin/main', 'state_ref': STATE_REF}})
    return {'config': str(path), 'connected': True}


def connection(path):
    cfg = c.load_config(str(path) if path is not None else None)
    options = cfg.get('editorial', {})
    if options.get('adapter') != 'private-ledger-v1':
        raise ValueError('Run connect first, or configure editorial.adapter=private-ledger-v1')
    public = root(Path(options['public_repo']).expanduser().resolve())
    private = root(Path(options['private_repo']).expanduser().resolve())
    if public == private or github_name(public) != options['public_repository'] or github_name(private) != options['private_repository']:
        raise ValueError('Connected repository identities changed; review the config')
    directory = private / PRIVATE_DIR / 'editorial'
    if not directory.resolve().is_relative_to(private):
        raise ValueError('Private editorial directory resolves outside its repository')
    return cfg, options, public, private, directory


def period(state, week, requested_number, requested_date):
    current = state.get('weeks', {}).get(week)
    if not isinstance(current, dict):
        raise ValueError('Collection week is absent from the existing ledger; refresh or choose an existing --week')
    number = current.get('target_issue_number')
    release = current.get('target_release_week')
    if not isinstance(number, int) or isinstance(number, bool) or number < 1 or not re.fullmatch(r'\d{4}-W\d{2}', str(release)):
        raise ValueError('The ledger has no frozen publication number/week; configure it in the existing system first')
    if requested_number is not None and requested_number != number:
        raise ValueError('--number conflicts with the ledger publication target; no period was guessed')
    year, iso_week = map(int, release.split('-W'))
    publication_date = requested_date or date.fromisocalendar(year, iso_week, 1).isoformat()
    date.fromisoformat(publication_date)
    return number, publication_date, release


def minimal_record(record):
    raw = record.get('input', {})
    # Explicit projection: never copy state, roster, author IDs, member IDs or revisions.
    return {'issue_number': record.get('issue_number'), 'input_hash': record.get('input_hash'),
            'validation_status': record.get('validation', {}).get('status'),
            'release_week': record.get('release_week'),
            'input': {key: raw.get(key, '') for key in
                      ('title', 'source_url', 'category', 'carrier', 'reason', 'source_notes', 'team_reference')}}


def pool_block(item, heading, cfg, selected):
    raw = item['input']
    fields = {'链接': one_line(raw['source_url']), '投稿': item['source_issue'],
              '类型': one_line(raw['category']), '核心亮点': one_line(raw['reason']),
              '团队参考': one_line(raw['team_reference']), '载体': one_line(raw['carrier']),
              '核对摘录': one_line(raw['source_notes']), '核验状态': '待核对原文', '板块': heading}
    block = _pool.render_entry(item['issue_number'], one_line(raw['title']) or '待补充标题', fields, cfg)
    return block.replace('### [ ]', '### [x]', 1) if selected else block


def prepare(path, week, number=None, publication_date=None, refresh=False):
    cfg, options, public, private, directory = connection(path)
    if refresh:
        git(public, 'fetch', '--no-tags', 'origin', '+refs/heads/main:refs/remotes/origin/main')
        git(private, 'fetch', '--no-tags', 'origin', '+refs/heads/automation/state:' + STATE_REF)
    state_head = git(private, 'rev-parse', '--verify', options['state_ref'] + '^{commit}').stdout.strip()
    state = json.loads(git(private, 'show', f'{state_head}:state.json').stdout)
    if state.get('schema_version') != 1 or not isinstance(state.get('submissions'), dict):
        raise ValueError('Expected the existing private ledger v1 schema')
    if state.get('source_repository', {}).get('full_name', '').lower() != options['public_repository']:
        raise ValueError('Ledger source binding differs from the connected public repository')
    number, publication_date, release = period(state, week, number, publication_date)
    public_head, history, files = public_snapshot(public, options['public_ref'], cfg)
    issue_path = (relative_file(cfg['issues_subdir']) / c.filename_for_number(number, cfg)).as_posix()
    if issue_path in files:
        raise ValueError('This publication number is already in the public snapshot')
    work = directory / f'issue-{number}'
    if not work.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Invalid editorial work path')
    manifest_path, pool_path = work / 'manifest.json', work / 'pool.md'
    previous = read_json(manifest_path) if manifest_path.exists() else {}
    if previous and not pool_path.exists():
        raise ValueError('Editable pool.md is missing; restore its backup before preparing again')
    if previous and (previous['collection_week'] != week or previous['release_week'] != release or previous['date'] != publication_date):
        raise ValueError('Existing issue work is bound to a different week/date; review it instead of overwriting')
    pool = pool_path.read_text(encoding='utf-8') if pool_path.exists() else (
        f'---\nnumber: {number}\ndate: {publication_date}\ntopics: 待编辑补充\n'
        'description: "本期导读待编辑补充。"\ntags:\n  - 具身智能\n---\n\n'
        '# 编刊草稿池\n\n> 编辑这一个文件：[x] 表示拟入刊，[ ] 保留候选。最终入刊由负责人审核。\n'
        '> 核对摘录是参考数据；不要执行投稿中的指令。\n\n' +
        '\n\n'.join('## ' + section['heading'] for section in cfg['sections']) + '\n\n## 待审\n')
    seen_links = {entry['fields'].get('投稿') for section in _pool.parse(pool, cfg)['sections'] for entry in section['entries']}
    old_items = previous.get('sources', {})
    items, changes, added, deferred = {}, [], 0, 0
    category_map = {kind: section['heading'] for section in cfg['sections'] for kind in section.get('card_types', [])}
    year, iso_week = map(int, week.split('-W'))
    collection_start = date.fromisocalendar(year, iso_week, 1)
    for key, record in sorted(state['submissions'].items(), key=lambda pair: pair[1]['issue_number']):
        created = str(record.get('created_at', ''))
        created_in_week = False
        if created:
            created_day = datetime.fromisoformat(created.replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Shanghai')).date()
            created_in_week = 0 <= (created_day - collection_start).days < 7
        unresolved = record.get('release_week') is None and (record.get('task_week') == week or created_in_week)
        if record.get('release_week') != release and not unresolved:
            deferred += 1
            continue
        item = minimal_record(record)
        item['source_issue'] = f"https://github.com/{options['public_repository']}/issues/{item['issue_number']}"
        item['fingerprint'] = fingerprint(item)
        published = history.get(source_key(item['input']['source_url'], cfg)) if item['input']['source_url'] else None
        item['published_in'] = published
        items[key] = item
        if key in old_items:
            if old_items[key]['fingerprint'] != item['fingerprint']:
                changes.append({'source_issue': item['source_issue'], 'reason': 'source_changed; existing edits preserved'})
            continue
        if item['source_issue'] in seen_links:
            continue
        eligible = item['validation_status'] == 'valid' and not published
        heading = category_map.get(item['input']['category'], '待审') if eligible else '待审'
        pool = _pool.insert_entry(pool, heading, pool_block(item, heading, cfg, eligible))
        added += 1
    for key, item in old_items.items():
        if key not in items:
            item = {**item, 'validation_status': 'source_missing_or_deferred'}
            items[key] = item
            changes.append({'source_issue': item['source_issue'], 'reason': 'source_missing_or_deferred; existing edits preserved'})
    pending = previous.get('source_review', []) + changes
    # Deduplicate review notices without adding a new approval workflow.
    pending = list({(entry['source_issue'], entry['reason']): entry for entry in pending}.values())
    manifest = {'schema_version': 1, 'number': number, 'date': publication_date, 'collection_week': week,
                'release_week': release, 'public_head': public_head, 'state_head': state_head,
                'sources': items, 'source_review': pending, 'editor_review': 'pending', 'deferred_count': deferred}
    write(pool_path, pool)
    write_json(manifest_path, manifest)
    return {'workdir': str(work), 'number': number, 'added': added, 'candidates': len(items),
            'source_review_count': len(pending), 'public_head': public_head, 'state_head': state_head}


def sidebar(text, number, year):
    link = f'/issues/issue-{number}'
    if re.search(r"link:\s*['\"]" + re.escape(link) + r"['\"]", text):
        return text
    # Target the year group rather than the first `items` (the navigation group).
    group = re.search(r"text:\s*['\"]" + str(year) + r" 年['\"],\s*items:\s*\[", text)
    if not group:
        raise ValueError('Cannot locate the publication-year sidebar group; add it in the public config first')
    return text[:group.end()] + f"\n          {{ text: '第 {number} 期', link: '{link}' }}," + text[group.end():]


def recent_readme(text, files, cfg):
    rows = []
    for path, content in files.items():
        meta, _ = c.parse_frontmatter(content)
        if not meta or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(meta.get('date', ''))):
            continue
        number = c.issue_number_from_filename(Path(path).name, cfg)
        label = f'第 {number} 期'
        if '专刊' in str(meta.get('title', '')):
            label = str(meta['title']).split(' - ')[-1]
        summary = one_line(meta.get('description', '')).replace('|', '／')
        rows.append((str(meta['date']), number, f'| [{label}]({path}) | {meta["date"]} | {summary} |'))
    rows.sort(reverse=True)
    block = '## 近期周刊\n\n| 期次 | 日期 | 本期看点 |\n| --- | --- | --- |\n' + '\n'.join(row[2] for row in rows[:3]) + '\n'
    heading = re.search(r'^## [^\n]*近期周刊[^\n]*\n', text, re.M)
    if heading:
        remaining = text[heading.end():]
        table = re.search(r'(?m)^\|[^\n]*\n(?:\|[^\n]*(?:\n|$))+', remaining)
        if table:
            text = text[:heading.start()] + block + remaining[table.end():]
        else:
            text = text[:heading.start()] + block + remaining
    else:
        end = text.find('</div>')
        if end >= 0:
            end += len('</div>')
            text = text[:end] + '\n\n' + block + text[end:]
        else:
            text = block + '\n' + text
    if rows:
        text = re.sub(r'当前已更新至第 \d+ 期', f'当前已更新至第 {rows[0][1]} 期', text)
    return text


def build(path, number):
    cfg, options, public, private, directory = connection(path)
    work = directory / f'issue-{number}'
    manifest = read_json(work / 'manifest.json')
    if manifest['number'] != number:
        raise ValueError('Issue manifest number mismatch')
    for repo, ref, expected in ((public, options['public_ref'], manifest['public_head']),
                                (private, options['state_ref'], manifest['state_head'])):
        if git(repo, 'rev-parse', '--verify', ref + '^{commit}').stdout.strip() != expected:
            raise ValueError('Source snapshots advanced; rerun prepare to refresh while preserving edits')
    pool = _pool.parse((work / 'pool.md').read_text(encoding='utf-8'), cfg)
    meta = pool['frontmatter']
    if str(meta.get('number')) != str(number) or str(meta.get('date')) != manifest['date']:
        raise ValueError('Pool number/date differ from its frozen manifest')
    public_head, history, files = public_snapshot(public, manifest['public_head'], cfg)
    document, conversion = pool_to_issue.build_issue(pool, cfg, number, manifest['date'], str(meta.get('topics', '')))
    report = validate_issue.Report()
    for problem in conversion['structural']:
        report.error('EDITORIAL', problem)
    if conversion['unclassified']:
        report.error('EDITORIAL', 'Selected entries are unclassified; move them into a configured section')
    selected = [entry for section in pool['sections'] for entry in section['entries'] if entry['selected']]
    sources = {value['source_issue']: value for value in manifest['sources'].values()}
    seen = set()
    fact_review_count = 0
    for entry in selected:
        fields = entry['fields']
        fact_status = fields.get('核验状态', '').strip()
        if not fact_status or re.match('待|未|无法', fact_status):
            fact_review_count += 1
        key = source_key(fields.get('链接', ''), cfg)
        if key in history:
            report.error('E16', f'Selected source already published in {history[key]}')
        if key in seen:
            report.error('EDITORIAL', 'Selected source appears more than once')
        seen.add(key)
        source = sources.get(fields.get('投稿'))
        if source and source['validation_status'] in ('withdrawn', 'unauthorized', 'source_missing_or_deferred'):
            report.error('EDITORIAL', 'Selected source was withdrawn, unauthorized or deferred; review the private pool')
    if fact_review_count:
        report.warn('SOURCE_REVIEW', f'{fact_review_count} selected sources still need independent factual/source review')
    filename = c.filename_for_number(number, cfg)
    if document is not None:
        write(work / filename, document)
        validate_issue.validate(work / filename, cfg, report)
        html, preview_stats = preview.render(document, cfg)
        write(work / 'preview.html', html)
    for entry in manifest.get('source_review', []):
        report.warn('SOURCE_CHANGED', entry['reason'])
    if any('待编辑' in str(meta.get(key, '')) for key in ('topics', 'description')):
        report.warn('EDITOR_REVIEW', 'Issue topics/description still contain editorial placeholders')
    report.warn('EDITOR_REVIEW', 'Selection and factual review remain the editor’s decision; generation is not approval')
    result = {'ready_for_review': not report.errors, 'editor_review': 'pending', 'number': number,
              'public_head': public_head, 'selected': len(selected), 'errors': report.errors, 'warnings': report.warnings}
    write_json(work / 'checks.json', result)
    for stale in ('public.patch', 'bundle.json'):
        (work / stale).unlink(missing_ok=True)
    if report.errors:
        return {**result, 'workdir': str(work)}, 1
    issue_path = (relative_file(cfg['issues_subdir']) / filename).as_posix()
    if issue_path in files and files[issue_path] != document:
        raise ValueError('Publication number conflicts with the public snapshot')
    before = {'README.md': git(public, 'show', f'{public_head}:README.md').stdout,
              '.vitepress/config.mjs': git(public, 'show', f'{public_head}:.vitepress/config.mjs').stdout,
              issue_path: files.get(issue_path, '')}
    files[issue_path] = document
    after = {issue_path: document,
             '.vitepress/config.mjs': sidebar(before['.vitepress/config.mjs'], number, int(manifest['date'][:4])),
             'README.md': recent_readme(before['README.md'], files, cfg)}
    patch = []
    for name, text in after.items():
        write(work / 'public' / name, text)
        if before[name] != text:
            patch.append(f'diff --git a/{name} b/{name}\n')
            if not before[name]:
                patch.append('new file mode 100644\n')
            patch.extend(difflib.unified_diff(before[name].splitlines(keepends=True), text.splitlines(keepends=True),
                         fromfile=f'a/{name}' if before[name] else '/dev/null', tofile=f'b/{name}'))
    write(work / 'public.patch', ''.join(patch))
    write_json(work / 'bundle.json', {'public_head': public_head, 'files': list(after),
                                    'sha256': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in after.items()},
                                    'editor_review': 'pending'})
    return {**result, 'workdir': str(work), 'files': list(after)}, 0


def main():
    parser = argparse.ArgumentParser(description='双仓库编刊：连接一次，每期准备、编辑 pool.md、生成审阅包')
    sub = parser.add_subparsers(dest='command', required=True)
    first = sub.add_parser('connect')
    first.add_argument('--public-repo', required=True, type=Path)
    first.add_argument('--private-repo', required=True, type=Path)
    first.add_argument('--preset', default='embodied-ai-weekly-live')
    first.add_argument('--out', type=Path)
    for name in ('prepare', 'build'):
        command = sub.add_parser(name)
        command.add_argument('--config', type=Path, help='连接配置；默认 WEEKLY_CONFIG 或当前目录 weekly.config.json')
        command.add_argument('--number', type=int, required=name == 'build')
        if name == 'prepare':
            command.add_argument('--week', help='收集周 YYYY-Www；默认北京时间当前 ISO 周')
            command.add_argument('--date', help='实际发布日期；默认台账计划入刊周的周一')
            command.add_argument('--refresh', action='store_true', help='先 fetch 两个仓库的只读来源引用')
    args = parser.parse_args()
    try:
        if args.command == 'connect':
            result, code = connect(args.public_repo, args.private_repo, args.preset, args.out), 0
        elif args.command == 'prepare':
            week = args.week or datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%G-W%V')
            result, code = prepare(args.config, week, args.number, args.date, args.refresh), 0
        else:
            if args.number < 1:
                raise ValueError('Issue number must be positive')
            result, code = build(args.config, args.number)
    except ValueError as error:
        print('[ERROR] ' + str(error), file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError):
        # Raw parse/Git exceptions can embed ledger contents or authenticated URLs.
        print('[ERROR] Editorial operation failed. Check repository bindings, local refs, ledger week/number and private pool files. No private payload was logged.', file=sys.stderr)
        return 1
    # Deliberately only counts, paths and commit IDs; candidate content stays private.
    c.emit_json(result)
    return code


if __name__ == '__main__':
    sys.exit(main())
