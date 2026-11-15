#!/usr/bin/env python3
"""Rebuild fictional README examples and the local interactive demo; standard library only.

Run from any directory: python3 docs/build_demo.py
Screenshots are captured separately from docs/demo.html in a browser.
"""
from pathlib import Path
import html
import json
import re
import sys

repo = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo / 'scripts'))
import _common as c
import _pool
import _review
import validate_issue
import pool_to_issue
import preview

sample = repo / 'examples/demo'
cfg = c.load_config(str(sample / 'config.json'))
pool = _pool.parse((sample / 'pool.md').read_text(encoding='utf-8'), cfg)
issue, conversion = pool_to_issue.build_issue(pool, cfg, 1, '2026-11-16', pool['frontmatter']['topics'])
if issue is None or conversion['structural'] or conversion['unclassified']:
    raise SystemExit('Demo pool cannot be converted')
(sample / 'issue-1.md').write_text(issue, encoding='utf-8')
preview_html, preview_stats = preview.render(issue, cfg)
(sample / 'preview.html').write_text(preview_html, encoding='utf-8')
names = {101: '示例投稿人 A', 102: '示例投稿人 B', 103: '示例投稿人 C', 104: '示例投稿人 A'}
sources = {}
for section in pool['sections']:
    for entry in section['entries']:
        f = entry['fields']
        number = int(f['投稿'].rsplit('/', 1)[-1])
        sources[f'issue-{number}'] = {
            'issue_number': number, 'source_issue': f['投稿'], 'submitter_name': names.get(number, '示例投稿人'),
            'validation_status': 'valid', 'published_in': 'issues/issue-0.md' if number == 104 else None,
            'input': {'title': entry['title'], 'source_url': f['链接'], 'category': f['类型'],
                      'carrier': f['载体'], 'reason': f['核心亮点']}}
manifest = {'number': 1, 'date': '2026-11-16', 'sources': sources}
review = _review.render(pool, manifest, cfg)
review = review.replace('\n\n', '\n\n> 演示资料：投稿人、内容与 example.com 链接均为虚构示例。\n\n', 1)
(sample / 'review.md').write_text(review, encoding='utf-8')
report = validate_issue.Report()
validate_issue.validate(sample / 'issue-1.md', cfg, report)
if report.errors:
    raise SystemExit('Demo issue did not pass format validation')
(sample / 'checks.json').write_text(json.dumps({'demo': True, 'selected': 2,
    'errors': report.errors, 'warnings': report.warnings}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def review_markup(text):
    """Render only the known review.md subset for this fictional documentation demo."""
    def inline(line):
        line = re.sub(r'\[([^\]]+)\]\(<([^>]+)>\)', r'<a href="\2">\1</a>', line)
        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', line)
    result, in_table = [], False
    for line in text.splitlines():
        if line.startswith('| '):
            if re.fullmatch(r'\|(?:[ :|-]+)\|', line):
                continue
            cells = line.strip('|').split('|')
            tag = 'td' if in_table else 'th'
            row = '<tr>' + ''.join(f'<{tag}>{inline(cell.strip())}</{tag}>' for cell in cells) + '</tr>'
            if not in_table:
                result.append('<table><thead>' + row + '</thead><tbody>')
                in_table = True
            else:
                result.append(row)
            continue
        if in_table:
            result.append('</tbody></table>')
            in_table = False
        if line.startswith('# '):
            result.append('<h1>' + inline(line[2:]) + '</h1>')
        elif line.startswith('## '):
            result.append('<h2>' + inline(line[3:]) + '</h2>')
        elif line.startswith('> '):
            result.append('<blockquote><p>' + inline(line[2:]) + '</p></blockquote>')
        elif line.startswith(('<details>', '</details>', '<summary>')):
            result.append(line)
        elif line.strip():
            result.append('<p>' + inline(line) + '</p>')
    if in_table:
        result.append('</tbody></table>')
    return '\n'.join(result)

review_body = review_markup(review)
review_css = '''
:root{color-scheme:light;--fg:#192b3a;--muted:#657789;--line:#e2e9ee;--accent:#12786d;--bg:#fff;--soft:#f5f8fa}
*{box-sizing:border-box}body{margin:0;color:var(--fg);background:var(--bg);font:16px/1.65 system-ui,"Noto Sans CJK SC",sans-serif}main{max-width:1160px;padding:24px 32px 54px;margin:auto}h1{font-size:29px;letter-spacing:-.6px;margin:4px 0 12px}h2{font-size:20px;margin:26px 0 10px}p{margin:10px 0}blockquote{font-size:12px;color:var(--muted);padding:7px 12px;margin:0 0 14px;border-left:3px solid #91cbbb;background:var(--soft)}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.65;table-layout:fixed}th,td{padding:12px 13px;border:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}th{background:var(--soft);text-align:left;font-weight:650}th:nth-child(1){width:7%}th:nth-child(2){width:12%}th:nth-child(3){width:16%}th:nth-child(4){width:45%}th:nth-child(5){width:20%}tbody tr:nth-child(even){background:#fafcfd}td:nth-child(4) a{font-weight:650}details{color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:16px;margin-top:28px}summary{cursor:pointer}main>p:nth-of-type(1){font-size:14px;color:var(--muted)}@media(max-width:680px){main{padding:20px 14px}table{min-width:820px}body{overflow-x:auto}h1{font-size:25px}}'''
review_html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><base href="../examples/demo/"><title>审核表 · 虚构数据演示</title><style>' + review_css + '</style></head><body><main>' + review_body + '</main></body></html>'
preview_html = (sample / 'preview.html').read_text(encoding='utf-8')
page = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>weekly-craft · 交付物演示</title>
<style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:system-ui,"Noto Sans CJK SC",sans-serif;color:#1c3144;background:#eaf0f4}body{display:block}header{padding:18px 28px;background:#102637;color:#eaf6f6;display:flex;align-items:center;justify-content:space-between;gap:18px}.brand{display:flex;align-items:center;gap:12px;font-weight:720;font-size:19px;letter-spacing:-.4px}.mark{width:29px;height:34px;border-radius:6px;background:#85dfc0;display:grid;place-content:center;gap:4px}.mark i{height:2px;width:15px;background:#21483d}.tag{font-weight:450;color:#b4cbd5;font-size:13px;border-left:1px solid #3d5769;padding-left:13px;margin-left:2px}.note{font-size:12px;color:#b4cbd5}.toolbar{display:flex;align-items:center;justify-content:space-between;padding:12px 28px;gap:12px;background:white;border-bottom:1px solid #dbe5eb}.tabs{display:flex;gap:5px;padding:4px;background:#eef3f6;border-radius:10px}button{border:0;background:transparent;padding:10px 20px;font:600 14px system-ui,sans-serif;color:#627584;border-radius:7px;cursor:pointer}button[aria-selected=true]{color:#11574f;background:#fff;box-shadow:0 1px 5px #16364718}button:focus-visible{outline:2px solid #178776;outline-offset:2px}.toolbar a{font-size:13px;color:#176c63;text-decoration:none}.workspace{flex:1;min-height:0;padding:16px 22px 22px}iframe{display:block;width:100%;height:800px;border:1px solid #d6e1e9;border-radius:12px;background:white;box-shadow:0 6px 25px #1026370b}iframe[hidden]{display:none}@media(max-width:640px){header{padding:15px}.tag,.note{display:none}.toolbar{padding:10px 12px}.workspace{padding:8px}button{padding:10px 13px}.toolbar a{font-size:12px}}
</style>
</head>
<body>
<header><div class="brand"><span class="mark" aria-hidden="true"><i></i><i></i><i></i></span>weekly-craft<span class="tag">交付物演示</span></div><span class="note">虚构示例 · 4 个候选 / 2 个拟入刊</span></header>
<div class="toolbar"><div class="tabs" role="tablist" aria-label="选择交付物"><button id="tab-review" role="tab" aria-controls="review" aria-selected="true" tabindex="0">01 审核候选</button><button id="tab-preview" role="tab" aria-controls="preview" aria-selected="false" tabindex="-1">02 周刊预览</button></div><a href="../examples/demo/pool.md" target="_blank" rel="noopener">查看素材池 ↗</a></div>
<main class="workspace">
<iframe id="review" role="tabpanel" aria-labelledby="tab-review" title="虚构投稿的负责人审核表" srcdoc="__REVIEW_BODY__"></iframe>
<iframe id="preview" role="tabpanel" aria-labelledby="tab-preview" title="脚本生成的单文件周刊预览" srcdoc="__PREVIEW_BODY__" hidden></iframe>
</main>
<script>
const tabs = [...document.querySelectorAll('[role=tab]')];
function fitFrame(view) {
  requestAnimationFrame(() => {
    const frame = document.getElementById(view);
    if (!frame || frame.hidden || !frame.contentDocument) return;
    frame.style.height = '1px';
    frame.style.height = (frame.contentDocument.documentElement.scrollHeight + 2) + 'px';
  });
}
document.querySelectorAll('iframe').forEach(frame => frame.addEventListener('load', () => fitFrame(frame.id)));
function selectView(view) {
  if (!['review', 'preview'].includes(view)) view = 'review';
  tabs.forEach(tab => {
    const selected = tab.getAttribute('aria-controls') === view;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
  });
  fitFrame(view);
}
window.addEventListener('resize', () => fitFrame(location.hash.slice(1) || 'review'));
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => { location.hash = tab.getAttribute('aria-controls'); });
  tab.addEventListener('keydown', event => {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].focus(); location.hash = tabs[next].getAttribute('aria-controls');
    }
  });
});
window.addEventListener('hashchange', () => selectView(location.hash.slice(1)));
selectView(location.hash.slice(1));
</script>
</body>
</html>
'''
page = page.replace('__REVIEW_BODY__', html.escape(review_html, quote=True)).replace('__PREVIEW_BODY__', html.escape(preview_html, quote=True))
(repo / 'docs').mkdir(exist_ok=True)
(repo / 'docs/demo.html').write_text(page, encoding='utf-8')
print('Demo generated only from fictional pool; 4 review candidates and 2 issue entries.')
