#!/usr/bin/env python3
"""Unit + integration tests for the material-pool chain (stdlib only).

Covers _pool parsing/writing, new_pool candidate import, pool_to_issue skeleton
generation (neutral + embodied preset), and fetch_bilibili pure helpers.

Run: python3 tests/test_pool.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

import _common as c  # noqa: E402
import _pool  # noqa: E402
import fetch_bilibili  # noqa: E402
import new_pool  # noqa: E402
import pool_to_issue  # noqa: E402
import validate_issue as vi  # noqa: E402
from test_common import TempCwdTest  # noqa: E402

POOL_FIXTURE = """---
pool: issue-44
number: 44
date: 2026-10-16
topics: 甲、乙
description: "草稿。"
tags:
  - 甲
  - 乙
---

# 素材池

> 一段用法说明，应被解析器跳过。

<!--
### [ ] 1. 模板
- 链接：https://...
-->

## 内容精选

### [x] 1. 已入选条目
- 链接：https://example.com/a
- 来源：来源平台
- 类型：
- 标签：标签甲
- 时长：10 分钟
- 摘要：一句摘要。
- 板块：内容精选

### [ ] 2. 未勾选条目
- 链接：https://example.com/b
- 板块：内容精选

## 工具与项目
"""

EMBODIED_POOL = """---
pool: issue-44
number: 44
date: 2026-10-16
topics: 具身智能、VLA
description: "本期聚焦 VLA 训练数据质量。"
tags:
  - 具身智能
  - VLA
  - 仿真环境
---

## \U0001f4a1 行业洞察

### [x] 1. 数据质量比规模更重要
- 链接：https://news.example.com/insight-1
- 来源：机器之心
- 类型：insight
- 标签：洞察
- 核心亮点：实验证明数据质量对收敛速度影响更大。
- 团队参考：标注流水线优先提质。
- 载体：行业洞察 · 8 分钟速读
- 板块：\U0001f4a1 行业洞察
"""


class TestPoolParse(unittest.TestCase):
    def setUp(self):
        self.cfg = c.load_config(None)

    def test_sections_and_selection(self):
        parsed = _pool.parse(POOL_FIXTURE, self.cfg)
        headings = [s["heading"] for s in parsed["sections"]]
        self.assertEqual(headings, ["内容精选", "工具与项目"])
        first = parsed["sections"][0]["entries"]
        self.assertEqual([e["selected"] for e in first], [True, False])
        self.assertEqual(first[0]["title"], "已入选条目")
        self.assertEqual(first[0]["fields"]["摘要"], "一句摘要。")
        self.assertEqual(first[0]["fields"]["板块"], "内容精选")

    def test_comment_and_quote_lines_skipped(self):
        parsed = _pool.parse(POOL_FIXTURE, self.cfg)
        self.assertNotIn("模板", [e["title"] for e in parsed["sections"][0]["entries"]])
        self.assertEqual(parsed["loose"], [])

    def test_field_bullet_fallback(self):
        text = "## 内容精选\n\n### [x] 1. 标题\n- **核心亮点：** 亮点\n"
        entry = _pool.parse(text, self.cfg)["sections"][0]["entries"][0]
        self.assertEqual(entry["fields"]["核心亮点"], "亮点")


class TestRenderAndKeys(unittest.TestCase):
    def setUp(self):
        self.cfg = c.load_config(None)

    def test_entry_keys_order(self):
        keys = _pool.entry_keys(self.cfg, ["板块"])
        self.assertEqual(keys[:5], _pool.BASE_KEYS)
        self.assertIn("摘要", keys)
        self.assertIn("板块", keys)
        self.assertEqual(keys.count("摘要"), 1)

    def test_render_entry_keeps_empty_keys(self):
        block = _pool.render_entry(3, "标题", {"链接": "u"}, self.cfg)
        self.assertTrue(block.startswith("### [ ] 3. 标题"))
        self.assertIn("- 链接：u", block)
        self.assertIn("- 摘要：", block)


class TestInsertEntry(unittest.TestCase):
    def setUp(self):
        self.cfg = c.load_config(None)

    def test_appends_at_section_end_and_preserves(self):
        out = _pool.insert_entry(POOL_FIXTURE, "内容精选", "### [ ] 3. 新增\n- 链接：https://new")
        self.assertIsNotNone(out)
        self.assertIn("### [x] 1. 已入选条目", out)
        self.assertIn("### [ ] 2. 未勾选条目", out)
        self.assertIn("### [ ] 3. 新增", out)
        self.assertEqual(_pool.section_entry_count(out, self.cfg, "内容精选"), 3)
        self.assertLess(out.index("### [ ] 3. 新增"), out.index("## 工具与项目"))

    def test_missing_heading_returns_none(self):
        self.assertIsNone(_pool.insert_entry(POOL_FIXTURE, "不存在的板块", "x"))


class TestNewPool(TempCwdTest):
    def test_build_pool_has_sections_and_one_template(self):
        cfg = c.load_config(None)
        text = new_pool.build_pool(cfg, 7, "2026-10-16", [])
        for section in cfg["sections"]:
            self.assertIn("## " + section["heading"], text)
        self.assertEqual(text.count("条目模板"), 1)
        self.assertIn("number: 7", text)

    def test_read_candidates_formats(self):
        text = (
            "- [2025-01-02] 论文标题 — 作者\n  https://arxiv.org/abs/2501.00001\n  一句话摘要\n"
            "- foo/bar ★1.2k [Python] https://github.com/foo/bar\n  desc\n"
            "NEW  https://example.com/c\t新闻标题\n"
            "DUP  https://example.com/old\n"
        )
        items, dup = new_pool.read_candidates(text)
        self.assertEqual(dup, 1)
        urls = {i["url"] for i in items}
        self.assertIn("https://arxiv.org/abs/2501.00001", urls)
        self.assertIn("https://github.com/foo/bar", urls)
        self.assertIn("https://example.com/c", urls)
        titles = {i["url"]: i["title"] for i in items}
        self.assertEqual(titles["https://arxiv.org/abs/2501.00001"], "论文标题")
        self.assertEqual(titles["https://example.com/c"], "新闻标题")


class TestFetchBilibili(unittest.TestCase):
    def test_extract_bv(self):
        self.assertEqual(fetch_bilibili.extract_bv("BV1diGX6rEN5"), "BV1diGX6rEN5")
        self.assertEqual(fetch_bilibili.extract_bv("https://www.bilibili.com/video/BV1hKgK6fEPi?p=1"), "BV1hKgK6fEPi")
        self.assertIsNone(fetch_bilibili.extract_bv("not-a-video"))

    def test_minutes_ceil_min_one(self):
        self.assertEqual(fetch_bilibili.minutes(0), 1)
        self.assertEqual(fetch_bilibili.minutes(60), 1)
        self.assertEqual(fetch_bilibili.minutes(61), 2)
        self.assertEqual(fetch_bilibili.minutes(599), 10)

    def test_entry_fields(self):
        fields = fetch_bilibili.entry_fields({"owner": {"name": "UP"}, "duration": 610}, "BV1diGX6rEN5")
        self.assertEqual(fields["链接"], "https://www.bilibili.com/video/BV1diGX6rEN5")
        self.assertEqual(fields["来源"], "B 站 · UP")
        self.assertEqual(fields["时长"], "11 分钟")


class TestPoolToIssueNeutral(TempCwdTest):
    def _build(self, text):
        cfg = c.load_config(None)
        pool = _pool.parse(text, cfg)
        return pool_to_issue.build_issue(pool, cfg, 44, "2026-10-16", "甲、乙"), cfg

    def test_skeleton_shape(self):
        (doc, report), cfg = self._build(POOL_FIXTURE)
        self.assertIn('title: "周刊 - 第 44 期"', doc)
        self.assertIn("# 周刊 - 第 44 期", doc)
        self.assertIn("## 内容精选", doc)
        self.assertIn("## 工具与项目", doc)
        self.assertIn(cfg["empty_section_placeholder"], doc)
        self.assertNotIn("::: card", doc)
        self.assertIn("### 1. [标签甲] [已入选条目](https://example.com/a)", doc)
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(report["prepared"], 1)
        self.assertFalse(report["warnings"])

    def test_no_selected_is_structural(self):
        text = "## 内容精选\n\n### [ ] 1. 没选\n- 链接：https://example.com/x\n"
        (doc, report), _ = self._build(text)
        self.assertIsNone(doc)
        self.assertTrue(any("入选条目" in s for s in report["structural"]))

    def test_missing_title_or_link_is_structural(self):
        text = "## 内容精选\n\n### [x] 1. 没链接\n- 摘要：x\n"
        (doc, report), _ = self._build(text)
        self.assertIsNone(doc)
        self.assertTrue(any("缺标题或链接" in s for s in report["structural"]))


class TestPoolToIssueEmbodied(TempCwdTest):
    def _cfg(self):
        (Path.cwd() / "weekly.config.json").write_text(json.dumps({"extends": "embodied-ai-weekly"}), encoding="utf-8")
        return c.load_config(None)

    def test_full_chain_writes_valid_issue(self):
        cfg = self._cfg()
        pool = _pool.parse(EMBODIED_POOL, cfg)
        doc, report = pool_to_issue.build_issue(pool, cfg, 44, "2026-10-16", "具身智能、VLA")
        self.assertIsNotNone(doc, report["structural"])
        self.assertIn("::: card insight", doc)
        self.assertIn("> 📅 **发布时间**：2026-10-16", doc)
        out = Path.cwd() / "issues" / "issue-44.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc, encoding="utf-8")
        report_obj = vi.Report()
        vi.validate(out, cfg, report_obj)
        self.assertEqual(report_obj.errors, [])

    def test_tags_below_min_is_structural(self):
        cfg = self._cfg()
        text = (
            "---\nnumber: 44\ndate: 2026-10-16\ntopics: 甲\ndescription: \"x\"\n"
            "tags:\n  - 只有一个\n---\n\n## \U0001f4a1 行业洞察\n\n"
            "### [x] 1. 标题\n- 链接：https://example.com/a\n"
        )
        pool = _pool.parse(text, cfg)
        doc, report = pool_to_issue.build_issue(pool, cfg, 44, "2026-10-16", "甲")
        self.assertIsNone(doc)
        self.assertTrue(any("tags" in s for s in report["structural"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
