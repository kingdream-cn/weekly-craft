#!/usr/bin/env python3
"""Unit tests for weekly-craft core pure functions (stdlib only).

Run: python3 tests/test_common.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import _common as c  # noqa: E402
import dedup_urls  # noqa: E402
import preview  # noqa: E402


class TempCwdTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._env = os.environ.pop("WEEKLY_CONFIG", None)
        self._tmp = tempfile.TemporaryDirectory(prefix="wc-test-")
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        if self._env is not None:
            os.environ["WEEKLY_CONFIG"] = self._env
        self._tmp.cleanup()


class TestDeepMerge(unittest.TestCase):
    def test_nested_override_keeps_siblings(self):
        base = {"a": {"x": 1, "y": 2}, "b": [1, 2]}
        merged = c.deep_merge(base, {"a": {"y": 9}})
        self.assertEqual(merged["a"], {"x": 1, "y": 9})
        self.assertEqual(merged["b"], [1, 2])

    def test_list_replaces_not_concatenates(self):
        merged = c.deep_merge({"b": [1, 2, 3]}, {"b": [9]})
        self.assertEqual(merged["b"], [9])

    def test_private_keys_ignored(self):
        merged = c.deep_merge({"a": 1}, {"_comment": "note", "a": 2})
        self.assertNotIn("_comment", merged)
        self.assertEqual(merged["a"], 2)

    def test_base_not_mutated(self):
        base = {"a": {"x": 1}}
        c.deep_merge(base, {"a": {"x": 2}})
        self.assertEqual(base["a"]["x"], 1)


class TestLoadConfig(TempCwdTest):
    def test_defaults_when_no_config(self):
        cfg = c.load_config(None)
        self.assertEqual(cfg["site_name"], c.DEFAULTS["site_name"])
        self.assertEqual(len(cfg["sections"]), 3)
        self.assertFalse(cfg["card"]["containers"])

    def test_extends_preset_by_name(self):
        (Path.cwd() / "weekly.config.json").write_text(
            json.dumps({"extends": "embodied-ai-weekly"}), encoding="utf-8"
        )
        cfg = c.load_config(None)
        self.assertEqual(len(cfg["sections"]), 5)
        self.assertTrue(cfg["card"]["containers"])
        self.assertEqual(cfg["entry"]["required_fields"], ["核心亮点", "团队参考", "载体"])

    def test_explicit_overrides_extended_field(self):
        cfg_path = Path.cwd() / "my.json"
        cfg_path.write_text(
            json.dumps({"extends": "minimal", "site_name": "我的周刊"}), encoding="utf-8"
        )
        cfg = c.load_config(str(cfg_path))
        self.assertEqual(cfg["site_name"], "我的周刊")
        self.assertEqual(len(cfg["sections"]), 3)

    def test_chained_extends(self):
        (Path.cwd() / "mid.json").write_text(
            json.dumps({"extends": "minimal", "quote_max_chars": 66}), encoding="utf-8"
        )
        (Path.cwd() / "top.json").write_text(
            json.dumps({"extends": "mid.json", "site_name": "链式"}), encoding="utf-8"
        )
        cfg = c.load_config(str(Path.cwd() / "top.json"))
        self.assertEqual(cfg["quote_max_chars"], 66)
        self.assertEqual(cfg["site_name"], "链式")

    def test_cycle_detected(self):
        (Path.cwd() / "a.json").write_text(json.dumps({"extends": "b.json"}), encoding="utf-8")
        (Path.cwd() / "b.json").write_text(json.dumps({"extends": "a.json"}), encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            c.load_config(str(Path.cwd() / "a.json"))
        self.assertEqual(ctx.exception.code, 2)


class TestPresetVariants(TempCwdTest):
    """板块变体预设只应改 sections，其余风格全部继承。"""

    def _load(self, extends: str) -> dict:
        (Path.cwd() / "cfg.json").write_text(json.dumps({"extends": extends}), encoding="utf-8")
        return c.load_config(str(Path.cwd() / "cfg.json"))

    def test_legacy_variant_swaps_only_fourth_section(self):
        base = self._load("embodied-ai-weekly")
        legacy = self._load("embodied-ai-weekly-legacy")
        self.assertEqual(len(legacy["sections"]), 5)
        self.assertEqual(base["sections"][3]["heading"], "🛒 硬件测评 & 选型雷达")
        self.assertEqual(legacy["sections"][3]["heading"], "⚙️ 工程实战 & 踩坑记录")
        self.assertEqual(legacy["sections"][:3], base["sections"][:3])
        self.assertEqual(legacy["sections"][4], base["sections"][4])

    def test_legacy_variant_inherits_style(self):
        base = self._load("embodied-ai-weekly")
        legacy = self._load("embodied-ai-weekly-legacy")
        for key in ("site_name", "entry", "card", "frontmatter", "quote_max_chars", "dedup", "sources"):
            self.assertEqual(legacy[key], base[key], key)


class TestFrontmatter(unittest.TestCase):
    def test_scalars_and_list(self):
        text = (
            '---\ntitle: "周刊 - 第 1 期"\ndate: 2026-01-01\n'
            "tags:\n  - 甲\n  - 乙\n---\n\n# 周刊 - 第 1 期\n"
        )
        fm, body = c.parse_frontmatter(text)
        self.assertEqual(fm["title"], "周刊 - 第 1 期")
        self.assertEqual(fm["date"], "2026-01-01")
        self.assertEqual(fm["tags"], ["甲", "乙"])
        self.assertIn("# 周刊 - 第 1 期", body)

    def test_missing_frontmatter(self):
        fm, body = c.parse_frontmatter("# 无 frontmatter\n")
        self.assertIsNone(fm)
        self.assertIn("无 frontmatter", body)


class TestTemplates(unittest.TestCase):
    def test_filename_number_roundtrip(self):
        cfg = c.DEFAULTS
        self.assertEqual(c.filename_for_number(7, cfg), "issue-7.md")
        self.assertEqual(c.issue_number_from_filename("issue-7.md", cfg), 7)
        self.assertIsNone(c.issue_number_from_filename("other.md", cfg))

    def test_title_for_number(self):
        cfg = dict(c.DEFAULTS, site_name="2026具身周刊")
        self.assertEqual(c.title_for_number(43, cfg), "2026具身周刊 - 第 43 期")

    def test_field_aliases(self):
        cfg = {"entry": {"field_aliases": {"核心创新": "核心亮点"}}}
        out = c.apply_field_aliases({"核心创新": "x", "载体": "y"}, cfg)
        self.assertEqual(out, {"核心亮点": "x", "载体": "y"})


class TestDedupNormalize(unittest.TestCase):
    def setUp(self):
        self.cfg = c.DEFAULTS

    def test_strip_tracking_params(self):
        norm = dedup_urls.normalize(
            "https://Example.com/post?utm_source=x&utm_medium=y&id=3&spm=a.b", self.cfg
        )
        self.assertEqual(norm, "https://example.com/post?id=3")

    def test_vd_source_stripped(self):
        norm = dedup_urls.normalize("https://www.bilibili.com/video/BV1x?vd_source=abc", self.cfg)
        self.assertEqual(norm, "https://www.bilibili.com/video/BV1x")

    def test_trailing_slash_and_fragment(self):
        norm = dedup_urls.normalize("https://example.com/a/b/#section", self.cfg)
        self.assertEqual(norm, "https://example.com/a/b")

    def test_root_slash_kept(self):
        norm = dedup_urls.normalize("https://example.com/", self.cfg)
        self.assertEqual(norm, "https://example.com/")


class TestPreviewStats(unittest.TestCase):
    TEXT = (
        '---\ntitle: "周刊 - 第 1 期"\ndate: 2026-01-01\ndescription: d\n'
        "tags:\n  - 甲\n  - 乙\n---\n\n# 周刊 - 第 1 期\n\n"
        "## 本周要点\n\n"
        "### 1. [标签] [A](https://example.com/a)\n\n- **摘要：** x\n\n"
        "### 2. [标签] [B](https://example.com/b)\n\n- **摘要：** y\n\n"
        "## 内容精选\n\n> *本期暂无收录。*\n"
    )

    def test_counts_entries_per_section(self):
        doc, stats = preview.render(self.TEXT, c.DEFAULTS)
        self.assertEqual(stats["sections"], 2)
        self.assertEqual(stats["entries"], 2)
        self.assertEqual(
            stats["section_items"],
            [{"heading": "本周要点", "entries": 2}, {"heading": "内容精选", "entries": 0}],
        )
        self.assertIn("本期统计", doc)
        self.assertIn("摘要 2/2", doc)

    def test_coverage_uses_field_aliases(self):
        cfg = c.deep_merge(
            c.DEFAULTS,
            {"entry": {"required_fields": ["核心亮点"], "field_aliases": {"核心创新": "核心亮点"}}},
        )
        doc, _ = preview.render(self.TEXT.replace("摘要", "核心创新"), cfg)
        self.assertIn("核心亮点 2/2", doc)

    def test_stats_skipped_when_no_sections(self):
        doc, stats = preview.render("# 周刊 - 第 1 期\n", c.DEFAULTS)
        self.assertEqual(stats["sections"], 0)
        self.assertNotIn("本期统计", doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
