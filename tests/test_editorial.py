"""Two real Git fixtures exercise the existing ledger contract and public export."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import editorial as e
import _review
import _common as c
import validate_issue
from test_publish import git, init

SECRET = 'PRIVATE_ROSTER_AND_CREDENTIAL_SENTINEL'


def record(number, status='valid', release='2026-W47', url=None):
    return {'issue_number': number, 'input_hash': f'hash-{number}', 'validation': {'status': status},
            'task_week': '2026-W46', 'release_week': release, 'created_at': '2026-11-10T08:00:00Z',
            'member_id': SECRET, 'author_user_id': 123,
            'input': {'title': f'公开条目 {number}', 'source_url': url or f'https://example.com/article/{number}',
                      'category': 'practice', 'carrier': '文章', 'reason': '原文介绍可复现的工程方法，指标需要编辑回到原文核对。',
                      'source_notes': '这是提交者提供的公开摘录，保存在私有编辑池用于核对，不自动全文发表。',
                      'team_reference': '可先在仿真环境验证方法适用性，再决定是否在实机复现。', 'extra_private': SECRET}}


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.public = init(self.directory / 'public')
        self.private = init(self.directory / 'private')
        for repo, name in ((self.public, 'public'), (self.private, 'private')):
            git(repo, 'remote', 'add', 'origin', f'https://github.com/example/{name}.git')
        (self.public / 'issues').mkdir()
        (self.public / '.vitepress').mkdir()
        (self.public / '.vitepress/config.mjs').write_text("export default {themeConfig: {sidebar: [{text: '导航', items: []}, {text: '2026 年', items: [\n  {text: '第 46 期', link: '/issues/issue-46'},\n]}]}}\n")
        (self.public / 'README.md').write_text('# Fixture\n\n## 近期周刊\n\n| 期次 | 日期 | 本期看点 |\n| --- | --- | --- |\n| [第 46 期](issues/issue-46.md) | 2026-11-09 | 旧内容 |\n\n## 保留说明\n\nKeep this text.\n')
        (self.public / 'issues/issue-46.md').write_text('---\ntitle: "2026具身周刊 - 第 46 期"\ndate: 2026-11-09\ndescription: "旧期刊"\ntags:\n  - 测试\n---\n\n[旧来源](https://example.com/old)\n')
        git(self.public, 'add', '.')
        git(self.public, 'commit', '-m', 'site fixture')
        git(self.public, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.state = {'schema_version': 1, 'source_repository': {'full_name': 'example/public'},
                      'weeks': {'2026-W46': {'target_issue_number': 47, 'target_release_week': '2026-W47', 'members_snapshot': [SECRET]}},
                      'submissions': {'issue-1': record(1), 'issue-2': record(2, status='needs_changes', release=None),
                                      'issue-3': record(3, release='2026-W48'), 'issue-4': record(4, url='https://example.com/old')},
                      'revisions': {'secret': SECRET}, 'webhook': SECRET}
        self.persist_state()
        result = e.connect(self.public, self.private, 'embodied-ai-weekly-live')
        self.config = Path(result['config'])
        self.work = self.private / '.weekly-private/editorial/issue-47'

    def persist_state(self):
        (self.private / 'state.json').write_text(json.dumps(self.state, ensure_ascii=False))
        git(self.private, 'add', 'state.json')
        git(self.private, 'commit', '--allow-empty', '-m', 'ledger fixture')
        git(self.private, 'update-ref', e.STATE_REF, 'HEAD')

    def prepare(self):
        return e.prepare(self.config, '2026-W46')

    def test_real_connection_reads_both_and_frozen_number_without_ledger_writes(self):
        before = git(self.private, 'rev-parse', 'HEAD')
        result = self.prepare()
        self.assertEqual(result['number'], 47)
        self.assertEqual(result['candidates'], 3)
        pool = (self.work / 'pool.md').read_text()
        self.assertIn('### [x] 1.', pool)
        self.assertIn('### [ ] 2.', pool)
        self.assertIn('### [ ] 4.', pool)
        self.assertNotIn('/article/3', pool)
        self.assertNotIn(SECRET, ''.join(path.read_text() for path in self.work.iterdir() if path.is_file()))
        self.assertEqual(git(self.private, 'rev-parse', 'HEAD'), before)
        self.assertEqual(git(self.private, 'status', '--porcelain'), '')
        self.assertEqual((self.work / 'manifest.json').stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            e.prepare(self.config, '2026-W46', number=46)

    def test_repeat_preserves_editor_changes_and_source_changes_are_visible(self):
        self.prepare()
        path = self.work / 'pool.md'
        edited = path.read_text().replace('原文介绍可复现的工程方法，指标需要编辑回到原文核对。', '编辑已写好的摘要。')
        path.write_text(edited)
        first_manifest = (self.work / 'manifest.json').read_bytes()
        self.prepare()
        self.assertEqual(path.read_text(), edited)
        self.assertEqual(first_manifest, (self.work / 'manifest.json').read_bytes())
        self.state['submissions']['issue-1']['input']['reason'] = '投稿作者修改了理由。'
        self.persist_state()
        with self.assertRaisesRegex(ValueError, 'advanced'):
            e.build(self.config, 47)
        result = self.prepare()
        self.assertEqual(path.read_text(), edited)
        self.assertGreater(result['source_review_count'], 0)
        self.assertIn('投稿作者修改了理由', (self.work / 'manifest.json').read_text())
        self.assertIn('source_changed', (self.work / 'manifest.json').read_text())

    def test_build_exports_only_public_files_with_applyable_patch(self):
        self.prepare()
        public_before = git(self.public, 'rev-parse', 'HEAD')
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 0, result)
        self.assertEqual(set(result['files']), {'issues/issue-47.md', '.vitepress/config.mjs', 'README.md'})
        all_output = ''.join(path.read_text() for path in (self.work / 'public').rglob('*') if path.is_file())
        self.assertNotIn(SECRET, all_output)
        for forbidden in ('source_notes', 'input_hash', 'member_id', 'members_snapshot', 'validation_status', 'manifest.json'):
            self.assertNotIn(forbidden, all_output)
        self.assertNotIn('这是提交者提供的公开摘录', all_output)
        self.assertIn('/issues/issue-47', (self.work / 'public/.vitepress/config.mjs').read_text())
        self.assertIn('Keep this text.', (self.work / 'public/README.md').read_text())
        self.assertLess((self.work / 'public/README.md').read_text().index('第 47 期'), (self.work / 'public/README.md').read_text().index('第 46 期'))
        git(self.public, 'apply', '--check', str(self.work / 'public.patch'))
        self.assertEqual(git(self.public, 'status', '--porcelain'), '')
        self.assertEqual(git(self.public, 'rev-parse', 'HEAD'), public_before)
        self.assertTrue((self.work / 'preview.html').exists())
        before = (self.work / 'public.patch').read_bytes()
        e.build(self.config, 47)
        self.assertEqual(before, (self.work / 'public.patch').read_bytes())

    def test_selected_duplicate_unclassified_and_withdrawn_block_pack(self):
        self.prepare()
        path = self.work / 'pool.md'
        original = path.read_text()
        path.write_text(original.replace('### [ ] 4.', '### [x] 4.').replace('- 板块：待审', '- 板块：⚙️ 工程实战 & 踩坑记录'))
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 1)
        self.assertTrue(any(error['rule'] == 'E16' for error in result['errors']))
        self.assertFalse((self.work / 'bundle.json').exists())
        path.write_text(original.replace('- 板块：⚙️ 工程实战 & 踩坑记录', '- 板块：未知栏目'))
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 1)
        self.assertTrue(any('unclassified' in error['message'] for error in result['errors']))
        path.write_text(original)
        self.state['submissions']['issue-1']['validation']['status'] = 'withdrawn'
        self.persist_state()
        self.prepare()
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 1)

    def test_source_binding_and_repository_identity_are_checked(self):
        self.state['source_repository']['full_name'] = 'example/wrong'
        self.persist_state()
        with self.assertRaisesRegex(ValueError, 'binding'):
            self.prepare()
        self.assertFalse(self.work.exists())
        git(self.public, 'remote', 'set-url', 'origin', 'https://github.com/example/other.git')
        with self.assertRaisesRegex(ValueError, 'identities'):
            self.prepare()

    def test_missing_manifest_is_recovered_without_duplicating_existing_pool_entries(self):
        self.prepare()
        # Simulate loss of a generated manifest after the pool was atomically saved.
        (self.work / 'manifest.json').unlink()
        previous = (self.work / 'pool.md').read_text()
        self.prepare()
        self.assertEqual(previous, (self.work / 'pool.md').read_text())
        self.assertEqual(len(e.read_json(self.work / 'manifest.json')['sources']), 3)

    def test_missing_editable_pool_stops_instead_of_silently_dropping_candidates(self):
        self.prepare()
        before = (self.work / 'manifest.json').read_bytes()
        (self.work / 'pool.md').unlink()
        with self.assertRaisesRegex(ValueError, 'pool.md is missing'):
            self.prepare()
        self.assertEqual(before, (self.work / 'manifest.json').read_bytes())
        self.assertFalse((self.work / 'pool.md').exists())

    def test_optional_sections_remain_ordered_and_old_presets_unchanged(self):
        self.prepare()
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 0, result)
        issue = self.work / 'issue-47.md'
        text = issue.read_text()
        self.assertIn('## ⚙️ 工程实战', text)
        self.assertNotIn('## 💡 行业洞察', text)
        report = validate_issue.Report()
        validate_issue.validate(issue, c.load_config(str(self.config)), report)
        self.assertFalse(report.errors)
        self.assertFalse(c.load_config(str(ROOT / 'presets/embodied-ai-weekly.json')).get('sections_optional'))

    def test_source_key_matches_arxiv_versions_and_doi_case(self):
        cfg = c.load_config()
        self.assertEqual(e.source_key('https://arxiv.org/pdf/2611.12345v2.pdf', cfg), e.source_key('https://arxiv.org/abs/2611.12345', cfg))
        self.assertEqual(e.source_key('https://doi.org/10.1234/ABC', cfg), e.source_key('https://dx.doi.org/10.1234/abc', cfg))

    def test_private_review_resolves_names_shows_all_candidates_and_keeps_exports_clean(self):
        name = 'PRIVATE_REVIEW_NAME_SENTINEL'
        self.state['weeks']['2026-W46']['members_snapshot'] = [
            {'member_id': SECRET, 'github_user_id': 123, 'display_name': 'Frozen alias'}]
        self.state['submissions']['issue-2']['validation']['errors'] = ['请补充可定位的原始资料链接']
        self.persist_state()
        mapping = self.private / '.weekly-private/names.json'
        mapping.write_text(json.dumps({'schema_version': 1, 'enabled': True, 'members': [
            {'member_id': SECRET, 'github_user_id': 123, 'real_name': name}]}))
        config = e.read_json(self.config)
        config['editorial']['review_names_file'] = '.weekly-private/names.json'
        e.write_json(self.config, config)
        output = subprocess.run([sys.executable, str(ROOT / 'scripts/editorial.py'), 'prepare',
                                 '--config', str(self.config), '--week', '2026-W46'], capture_output=True, text=True)
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertNotIn(name, output.stdout + output.stderr)
        review = (self.work / 'review.md').read_text()
        for number in (1, 2, 4):
            self.assertIn(f'[#'+str(number)+']', review)
        self.assertNotIn('[#3]', review)
        self.assertEqual(review.count(name), 3)
        self.assertIn('工程实战', review)
        self.assertIn('文章', review)
        self.assertIn('请补充可定位', review)
        self.assertIn('与已刊内容重复', review)
        self.assertEqual((self.work / 'review.md').stat().st_mode & 0o777, 0o600)
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 0, result)
        public = ''.join(path.read_text() for path in (self.work / 'public').rglob('*') if path.is_file())
        public += (self.work / 'public.patch').read_text() + (self.work / 'issue-47.md').read_text()
        public += (self.work / 'preview.html').read_text() + (self.work / 'checks.json').read_text()
        self.assertNotIn(name, public)
        self.assertNotIn(SECRET, public)
        self.assertEqual(git(self.private, 'status', '--porcelain'), '')

    def test_review_tracks_edits_and_only_includes_actionable_editorial_notes(self):
        self.prepare()
        path = self.work / 'pool.md'
        path.write_text(path.read_text().replace('原文介绍可复现的工程方法，指标需要编辑回到原文核对。',
                                                '更新后的工程方法摘要。后续细节留在完整预览。')
                        .replace('- 核验状态：待核对原文', '- 核验状态：已核对官方页面\n- 入刊提示：这是旧闻，请决定是否作为回顾'))
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 0, result)
        review = (self.work / 'review.md').read_text()
        self.assertIn('更新后的工程方法摘要。', review)
        self.assertNotIn('后续细节', review)
        self.assertIn('这是旧闻', review)
        self.assertNotIn('已核对官方页面', review)
        self.assertNotIn('原文核对及编辑注意事项', review)
        # It is still useful when a selected withdrawn source makes the pack invalid.
        self.state['submissions']['issue-1']['validation']['status'] = 'withdrawn'
        self.persist_state()
        self.prepare()
        result, code = e.build(self.config, 47)
        self.assertEqual(code, 1)
        self.assertIn('投稿已撤回', (self.work / 'review.md').read_text())

    def test_review_retains_removed_candidate_without_readding_it_to_the_pool(self):
        self.prepare()
        path = self.work / 'pool.md'
        text = path.read_text()
        start = text.index('### [ ] 2.')
        end = text.index('### [ ] 4.', start)
        path.write_text(text[:start] + text[end:])
        self.prepare()
        self.assertNotIn('### [ ] 2.', path.read_text())
        self.assertIn('[#2]', (self.work / 'review.md').read_text())
        self.assertIn('已从素材池移除', (self.work / 'review.md').read_text())

    def test_names_require_both_frozen_identities_and_never_guess_from_display_names(self):
        state = {'weeks': {'2026-W46': {'members_snapshot': [
            {'member_id': 'stable-id', 'github_user_id': 123, 'display_name': 'Frozen alias'}]}}}
        submission = {'task_week': '2026-W46', 'member_id': 'stable-id', 'author_user_id': 123}
        mapped = {'member_id': 'stable-id', 'github_user_id': 123, 'real_name': 'Private test name'}
        self.assertEqual(_review.submitter_name(state, submission, '2026-W46', [mapped]), 'Private test name')
        self.assertEqual(_review.submitter_name(state, submission, '2026-W46', [mapped, mapped]), 'Frozen alias')
        self.assertEqual(_review.submitter_name(state, submission, '2026-W46', [{**mapped, 'github_user_id': 999}]), 'Frozen alias')
        self.assertEqual(_review.submitter_name(state, {**submission, 'author_user_id': 999}, '2026-W46', [mapped]), '未匹配成员')

    def test_private_yaml_names_support_existing_format_without_logging_bad_payloads(self):
        mapping = self.private / '.weekly-private/names.yml'
        mapping.write_text('schema_version: 1\nenabled: true\nreal_name_scope: dingtalk_group_only\n'
                           'members:\n  - member_id: test-id\n    github_user_id: 123\n'
                           '    real_name: "Private | test name" # local comment\n')
        options = {'review_names_file': '.weekly-private/names.yml'}
        self.assertEqual(_review.load_names(self.private, options)[0]['real_name'], 'Private | test name')
        mapping.write_text('members: [PRIVATE_BAD_MAPPING_SENTINEL]\n')
        with self.assertRaises(ValueError) as error:
            _review.load_names(self.private, options)
        self.assertNotIn('PRIVATE_BAD_MAPPING_SENTINEL', str(error.exception))
        with self.assertRaises(ValueError):
            _review.load_names(self.private, {'review_names_file': '../outside.yml'})

    def test_review_escapes_submission_text_and_rejects_non_web_links(self):
        self.prepare()
        pool = {'sections': [{'entries': [{'selected': False, 'title': '<script> | [x]',
                  'fields': {'链接': 'javascript:alert(1)', '核心亮点': '<img src=x> | **a**'}}]}]}
        document = _review.render(pool, {**e.read_json(self.work / 'manifest.json'), 'sources': {}}, c.load_config(str(self.config)))
        self.assertNotIn('<script>', document)
        self.assertNotIn('<img', document)
        self.assertNotIn('javascript:', document)
        self.assertIn('&#124;', document)


if __name__ == '__main__':
    unittest.main()
