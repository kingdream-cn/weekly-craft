# Changelog

本文件记录 weekly-craft 的所有重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。
**major** = issue 格式规范或配置 schema 的不兼容变更。

## [Unreleased]

### Added
- **本地素材池链路**（`scripts/_pool.py`、`new_pool.py`、`pool_to_issue.py`、
  `fetch_bilibili.py`）：候选先落盘成单文件 md 池子，人工润色后用脚本确定性搬回 issue 骨架；
  `[x]` 勾选入选、`- 键：值` 字段、`- 板块：` 归类；缺字段不猜、留空交校验器。
- `scripts/fetch_bilibili.py`：抓 B 站视频标题/UP/时长（免登录 API），可 `--pool ... --section ...`
  追加到指定板块。
- 配置新增 `pool_dir`（默认 `"sources"`）与 `pool_filename`（默认 `"issue-{number}-pool.md"`）。
- 预设 `presets/embodied-ai-weekly-legacy.json`：`embodied-ai-weekly` 的**板块变体**示例
  （仅覆盖 `sections`，其余全继承）。
- `preview.py` 增加「本期统计」块（板块条目分布 + 必填字段完整度，纯 CSS，仅预览可见）。
- 工程质量：`.github/workflows/test.yml`（Python 3.9–3.12 矩阵 CI）、`tests/test_common.py` /
  `tests/test_pool.py` 单测、四份 golden、`CONTRIBUTING.md`、Issue/PR 模板。

### Changed
- `scripts/new_issue.py` 抽出 `render_document()`，供 `pool_to_issue.py` 复用，保证池骨架与
  脚手架格式逐字一致。
- `tests/run_tests.sh` 回归扩展为「单测（common + pool）+ 四 golden + 15 坏样本」。

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
