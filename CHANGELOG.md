# Changelog

本文件记录 weekly-craft 的所有重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。
**major** = issue 格式规范或配置 schema 的不兼容变更。

## [Unreleased]

### Added
- 待发布项在此累积。

## [0.1.0] - 2026-10-15

首个可用版本（首个公开版本为 1.0.0，待端到端演练与开源发布后打出）。

### Added
- 配置层 `scripts/_common.py`：解析链 `--config` > `$WEEKLY_CONFIG` > `weekly.config.json`
  > `extends` 预设链（深合并、环检测）> 内置中性默认；issue/frontmatter/card 解析器。
- 官方预设：`presets/minimal.json`（中性默认显式化）、
  `presets/embodied-ai-weekly.json`（具身智能周刊风格：5 板块 / 6 色 card / 三字段 / 阈值集）。
- `scripts/validate_issue.py`：校验规则 E01–E16 / W01–W05，全部配置驱动，关闭项自动跳过；
  `--strict` / `--with-history` / `--json`。
- `scripts/new_issue.py` + `scripts/next_number.py`：脚手架与自动取号（本地或 GitHub 只读）。
- `scripts/dedup_urls.py`：URL 规范化（剥跟踪参数）+ 历史比对 + `--fuzzy` 标题相似。
- `scripts/preview.py` + `assets/preview-style.css`：单文件 HTML 预览，
  card 配色按配置注入，暗色模式，未知块降级 `<pre>` + WARN。
- `scripts/fetch_arxiv.py` / `scripts/fetch_github_trends.py`：素材抓取（arXiv Atom / GitHub Search）。
- `scripts/publish.py`：两段式安全发布，默认 dry-run，`--push` 需人工确认；
  期号冲突 / 脏工作区 / rebase 冲突三重拒绝；无 force push；`.publish-history.jsonl` 审计。
- 文档：`SKILL.md`、`references/`（style-guide / workflow / publishing / presets-guide / content-sourcing）、
  `assets/card-spec.md`、`README.md`、`config.example.json`。
- 测试：`tests/run_tests.sh`（双 golden 回归 + 15 坏样本 rule id 断言）。

[Unreleased]: https://github.com/kingdream-cn/weekly-craft/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kingdream-cn/weekly-craft/releases/tag/v0.1.0
