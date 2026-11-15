"""Private editorial review: resolve names and render a decision-oriented table."""
from __future__ import annotations

import html
import json
import re
from urllib.parse import urlsplit

from _git import relative_file


def _scalar(value):
    value = value.strip()
    if value.startswith('"'):
        parsed, end = json.JSONDecoder().raw_decode(value)
        if value[end:].strip() and not value[end:].lstrip().startswith('#'):
            raise ValueError('Invalid private review name mapping')
        return parsed
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if not match:
            raise ValueError('Invalid private review name mapping')
        return match[1].replace("''", "'")
    value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
    if value in ('true', 'false'):
        return value == 'true'
    if value.isdecimal():
        return int(value)
    if not value or value[0] in '&*![]{}>|':
        raise ValueError('Use flat YAML or JSON for the private review name mapping')
    return value


def load_names(private, options):
    """Optional explicit local opt-in; never change the source mapping's scope."""
    filename = options.get('review_names_file')
    if not filename:
        return []
    path = private / relative_file(filename)
    if not path.resolve().is_relative_to(private) or path.stat().st_size > 128 * 1024:
        raise ValueError('Private review name mapping must be a small file inside the private repository')
    text = path.read_text(encoding='utf-8')
    try:
        if text.lstrip().startswith('{'):
            data = json.loads(text)
        else:
            # The existing member-map format: top-level scalars + a flat members list.
            # Deliberately do not implement YAML aliases, tags or arbitrary nesting.
            data, current = {}, None
            for line in text.splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                top = re.fullmatch(r'([\w-]+):\s*(.*?)\s*', line)
                member = re.fullmatch(r'\s+-\s+([\w-]+):\s*(.*?)\s*', line)
                field = re.fullmatch(r'\s+([\w-]+):\s*(.*?)\s*', line)
                if top:
                    key, value = top.groups()
                    if key in data:
                        raise ValueError()
                    data[key] = [] if key == 'members' and not value else _scalar(value)
                    current = None
                elif member and isinstance(data.get('members'), list):
                    key, value = member.groups()
                    current = {key: _scalar(value)}
                    data['members'].append(current)
                elif field and current is not None:
                    key, value = field.groups()
                    if key in current:
                        raise ValueError()
                    current[key] = _scalar(value)
                else:
                    raise ValueError()
        if data.get('schema_version') != 1 or not isinstance(data.get('members'), list):
            raise ValueError()
        if data.get('enabled') is not True:
            return []
        return [member for member in data['members'] if isinstance(member, dict)]
    except (ValueError, TypeError, AttributeError):
        # Parser errors must not include a line containing an actual name.
        raise ValueError('Invalid private review name mapping; use the existing flat members format') from None


def submitter_name(state, record, collection_week, names):
    week = state.get('weeks', {}).get(record.get('task_week') or collection_week, {})
    members = week.get('members_snapshot', [])
    matches = [member for member in members if isinstance(member, dict)
               and member.get('member_id') == record.get('member_id')
               and member.get('github_user_id') == record.get('author_user_id')
               and member.get('member_id') is not None and member.get('github_user_id') is not None]
    if len(matches) != 1:
        return '未匹配成员'
    member = matches[0]
    mapped = [item for item in names if item.get('member_id') == member['member_id']
              and item.get('github_user_id') == member['github_user_id']]
    if len(mapped) == 1 and isinstance(mapped[0].get('real_name'), str) and mapped[0]['real_name'].strip():
        return mapped[0]['real_name'].strip()
    return member.get('display_name') or '姓名待确认'


def _line(value):
    return ' '.join(str(value or '').split())


def _cell(value):
    value = html.escape(_line(value), quote=False).replace('\\', '\\\\').replace('|', '&#124;')
    for char in '[]*`':
        value = value.replace(char, '\\' + char)
    return value


def _link(label, url):
    url = _line(url)
    try:
        valid = urlsplit(url).scheme in ('http', 'https') and bool(urlsplit(url).hostname)
    except ValueError:
        valid = False
    if not valid:
        return _cell(label)
    for char, escaped in (('<', '%3C'), ('>', '%3E'), (' ', '%20'), ('\\', '%5C'), ('|', '%7C')):
        url = url.replace(char, escaped)
    return f'[{_cell(label)}](<{url}>)'


def _brief(value):
    text = _line(value)
    first = re.split(r'(?<=[。！？])|(?<=[.!?])\s+', text, maxsplit=1)[0]
    return first if len(first) <= 140 else first[:139].rstrip() + '…'


def _advice(entry, source, removed=False):
    problems = []
    if source.get('published_in'):
        problems.append('与已刊内容重复')
    status = source.get('validation_status')
    if status in ('withdrawn', 'unauthorized', 'source_missing_or_deferred'):
        problems.append({'withdrawn': '投稿已撤回', 'unauthorized': '投稿身份未通过核验',
                         'source_missing_or_deferred': '来源已移除或改到其他期'}[status])
    elif status and status != 'valid':
        errors = source.get('validation_errors', [])
        problems.extend(errors[:2] or ['投稿信息需补充，详见投稿页'])
    note = entry['fields'].get('入刊提示', '')
    if note:
        problems.append(note)
    if removed:
        problems.append('已从素材池移除')
    if problems:
        prefix = '拟入刊，需决定：' if entry['selected'] else '暂未入选：'
        return prefix + '；'.join(map(_line, problems))
    return '拟入刊' if entry['selected'] else '暂未入选，可补选'


def render(pool, manifest, cfg):
    sources = {item['source_issue']: item for item in manifest['sources'].values()}
    rows, present = [], set()
    categories = {kind: re.sub(r'^[^\w\u4e00-\u9fff]+', '', section['heading']).split(' & ')[0]
                  for section in cfg['sections'] for kind in section.get('card_types', [])}
    for section in pool['sections']:
        for entry in section['entries']:
            url = entry['fields'].get('投稿')
            present.add(url)
            rows.append((entry, sources.get(url, {}), False))
    # A manually removed pool entry remains visible as an unselected candidate.
    for url, source in sources.items():
        if url not in present:
            raw = source['input']
            rows.append(({'selected': False, 'title': raw['title'], 'fields': {
                '投稿': url, '链接': raw['source_url'], '类型': raw['category'],
                '载体': raw['carrier'], '核心亮点': raw['reason']}}, source, True))
    selected = sum(entry['selected'] for entry, _, _ in rows)
    manual_numbers = {id(entry): f'手动-{index}' for index, (entry, source, _) in enumerate(rows, 1) if not source}
    lines = [f'# 第 {manifest["number"]} 期入刊审核', '',
             f'计划日期：{manifest["date"]} · 候选 {len(rows)} 条 · 拟入刊 {selected} 条 · 暂未入选 {len(rows) - selected} 条', '',
             '按编号告诉 agent 保留、去掉或修改哪些条目即可；取舍会同步到素材池，再更新正文与预览。', '',
             '[查看完整周刊预览](preview.html)', '']
    for selected_group, heading in ((True, '拟入刊'), (False, '暂未入选')):
        group = [(entry, source, removed) for entry, source, removed in rows if entry['selected'] == selected_group]
        lines += [f'## {heading}（{len(group)} 条）', '']
        if not group:
            lines += ['暂无。', '']
            continue
        lines += ['| 编号 | 投稿人 | 投稿类型 | 标题与一句话内容要点 | 入刊建议 |',
                  '| --- | --- | --- | --- | --- |']
        for entry, source, removed in group:
            fields = entry['fields']
            number = f'#{source["issue_number"]}' if source else manual_numbers[id(entry)]
            name = source.get('submitter_name') or ('姓名待补充' if source else '手动添加')
            kind = fields.get('类型') or source.get('input', {}).get('category')
            category = categories.get(kind, kind or '待分类')
            carrier = fields.get('载体') or source.get('input', {}).get('carrier', '')
            category = _cell(category) + ('<br>' + _cell(carrier) if carrier else '')
            summary = _brief(fields.get('核心亮点') or source.get('input', {}).get('reason', ''))
            title = _link(entry['title'], fields.get('链接'))
            if summary:
                title += '<br>' + _cell(summary)
            lines.append('| ' + ' | '.join((_link(number, fields.get('投稿')), _cell(name), category,
                                              title, _cell(_advice(entry, source, removed)))) + ' |')
        lines.append('')
    lines += ['<details>', '<summary>编辑文件与详细检查</summary>', '',
              '[素材池](pool.md) · [检查记录](checks.json) · [生成正文](' +
              cfg['issue_filename'].replace('{number}', str(manifest['number'])) + ')', '', '</details>', '']
    return '\n'.join(lines)
