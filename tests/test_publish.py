"""Real local Git repositories exercise observable publishing side effects."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import _common as c
import publish


def git(repo, *args):
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def init(repo):
    repo.mkdir(parents=True)
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.name', 'Fixture Editor')
    git(repo, 'config', 'user.email', 'fixture@example.com')
    (repo / 'base.txt').write_text('base\n')
    git(repo, 'add', 'base.txt')
    git(repo, 'commit', '-m', 'fixture')
    return repo


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.repo = init(self.directory / 'repo')
        self.src = self.directory / 'issue-1.md'
        self.src.write_text((ROOT / 'tests/golden/neutral-issue.md').read_text().replace('第 7 期', '第 1 期'))
        # Use the fixture's own number rather than assuming its title.
        import re
        text = self.src.read_text()
        text = re.sub(r'第 \d+ 期', '第 1 期', text)
        self.src.write_text(text)
        self.cfg = c.load_config(str(ROOT / 'presets/minimal.json'))
        # Keep audit artifacts out of the repository being published.
        self.cwd = Path.cwd()
        import os
        os.chdir(self.directory)
        self.addCleanup(os.chdir, self.cwd)

    def snapshot(self):
        return (git(self.repo, 'rev-parse', 'HEAD'), git(self.repo, 'status', '--porcelain'),
                (self.repo / '.git/index').read_bytes(),
                sorted(str(path.relative_to(self.repo)) for path in self.repo.rglob('*') if '.git' not in path.parts))

    def test_default_is_read_only_including_no_audit_log(self):
        before = self.snapshot()
        result, code = publish.publish(self.src, self.cfg, self.repo)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['dry_run'])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.directory / publish.HISTORY_NAME).exists())
        self.assertFalse((self.repo / 'issues').exists())

    def test_commit_preserves_unrelated_staged_and_unstaged_changes(self):
        (self.repo / 'other.txt').write_text('unrelated staged work')
        git(self.repo, 'add', 'other.txt')
        (self.repo / 'base.txt').write_text('unrelated unstaged work')
        result, code = publish.publish(self.src, self.cfg, self.repo, commit=True, allow_dirty=True)
        self.assertEqual(code, 0, result)
        self.assertEqual(git(self.repo, 'show', '--format=', '--name-only', 'HEAD'), 'issues/issue-1.md')
        self.assertEqual(git(self.repo, 'diff', '--cached', '--name-only'), 'other.txt')
        self.assertEqual((self.repo / 'base.txt').read_text(), 'unrelated unstaged work')
        _, code = publish.publish(self.src, self.cfg, self.repo, commit=True, allow_dirty=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['commit'], git(self.repo, 'rev-parse', 'HEAD'))

    def test_dirty_and_branch_and_remote_mismatch_do_not_mutate(self):
        (self.repo / 'base.txt').write_text('keep this')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Working tree'):
            publish.publish(self.src, self.cfg, self.repo)
        self.assertEqual(before, self.snapshot())
        self.cfg['repo']['branch'] = 'other'
        with self.assertRaisesRegex(ValueError, 'branch'):
            publish.publish(self.src, self.cfg, self.repo, commit=True, allow_dirty=True)
        self.cfg['repo']['branch'] = 'main'
        self.cfg['repo']['remote'] = 'https://github.com/example/intended.git'
        git(self.repo, 'remote', 'add', 'origin', 'https://github.com/example/wrong.git')
        with self.assertRaisesRegex(ValueError, 'origin'):
            publish.publish(self.src, self.cfg, self.repo, commit=True, allow_dirty=True)
        self.assertEqual(before[0], git(self.repo, 'rev-parse', 'HEAD'))

    def test_rejects_path_escape_and_issue_collision(self):
        self.cfg['issues_subdir'] = '../outside'
        with self.assertRaises(ValueError):
            publish.publish(self.src, self.cfg, self.repo, commit=True)
        self.assertFalse((self.directory / 'outside').exists())
        self.cfg['issues_subdir'] = 'issues'
        (self.repo / 'issues').mkdir()
        (self.repo / 'issues/issue-1.md').write_text('existing publication')
        with self.assertRaisesRegex(ValueError, 'number'):
            publish.publish(self.src, self.cfg, self.repo, commit=True)

    def test_push_to_local_bare_remote_and_retry(self):
        bare = self.directory / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(bare)], check=True, capture_output=True)
        git(self.repo, 'remote', 'add', 'origin', str(bare))
        git(self.repo, 'push', '-u', 'origin', 'main')
        self.cfg['repo']['remote'] = str(bare)
        result, code = publish.publish(self.src, self.cfg, self.repo, push=True)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['pushed'])
        self.assertEqual(git(bare, 'rev-parse', 'refs/heads/main'), result['commit'])
        again, code = publish.publish(self.src, self.cfg, self.repo, push=True)
        self.assertEqual(code, 0)
        self.assertEqual(again['commit'], result['commit'])

    def test_push_rejects_unrelated_unpublished_commits(self):
        bare = self.directory / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(bare)], check=True, capture_output=True)
        git(self.repo, 'remote', 'add', 'origin', str(bare))
        git(self.repo, 'push', '-u', 'origin', 'main')
        remote_before = git(bare, 'rev-parse', 'refs/heads/main')
        (self.repo / 'base.txt').write_text('unrelated committed change')
        git(self.repo, 'add', 'base.txt')
        git(self.repo, 'commit', '-m', 'other work')
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            publish.publish(self.src, self.cfg, self.repo, push=True)
        self.assertEqual(git(bare, 'rev-parse', 'refs/heads/main'), remote_before)
        self.assertFalse((self.repo / 'issues').exists())

    def test_push_also_rejects_unrelated_commits_reverted_in_the_final_tree(self):
        bare = self.directory / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(bare)], check=True, capture_output=True)
        git(self.repo, 'remote', 'add', 'origin', str(bare))
        git(self.repo, 'push', '-u', 'origin', 'main')
        (self.repo / 'base.txt').write_text('unrelated intermediate content')
        git(self.repo, 'add', 'base.txt')
        git(self.repo, 'commit', '-m', 'intermediate')
        git(self.repo, 'revert', '--no-edit', 'HEAD')
        self.assertEqual(git(self.repo, 'diff', '--name-only', 'origin/main..HEAD'), '')
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            publish.publish(self.src, self.cfg, self.repo, push=True)

    def test_audit_log_does_not_dirty_target_when_running_inside_it(self):
        import os
        os.chdir(self.repo)
        result, code = publish.publish(self.src, self.cfg, self.repo, commit=True)
        self.assertEqual(code, 0, result)
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        self.assertTrue((self.repo / '.git' / publish.HISTORY_NAME).exists())
        _, code = publish.publish(self.src, self.cfg, self.repo)
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
