---
name: weekly-craft
description: 周刊生成与排版风格引擎。将自由格式草稿转换为规范化周刊 issue（frontmatter + 板块 + card 容器），并提供脚手架、格式校验（E01–E16/W01–W05）、跨期 URL 去重、单文件 HTML 预览、arXiv/GitHub 趋势素材抓取，以及 dry-run 默认的两段式安全发布到 GitHub Pages 仓库。当用户要新建/转换/校验/预览/发布周刊，或要为周刊定制风格预设（presets + extends）时使用。零配置即中性默认，可直接用于任何周刊站点。
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, WebFetch, WebSearch
argument-hint: "[new|convert|validate|preview|publish] [draft-path]"
---

# weekly-craft 周刊生成与排版风格

## Overview

引擎与风格分离：脚本负责确定性的校验/渲染/发布，agent 负责语义性的归类/改写/摘要。
内置中性默认（零配置可用）；完整风格通过 `presets/` 预设 + 用户配置 `extends` 换皮。

## 配置解析链

`--config` > `$WEEKLY_CONFIG` > `cwd/weekly.config.json` > `extends` 预设链 > 内置中性默认（深合并）。
字段全表与预设机制见 `references/presets-guide.md`；中性示例见 `config.example.json`。

## 工作流（状态机）

research → draft → convert → validate → preview → confirm → publish → verify-CI
各阶段产物、断点续跑见 `references/workflow.md`。

## 脚本速查表

全部 Python 3.9+ 标准库，退出码 0 成功 / 1 业务失败 / 2 环境错误，多数支持 `--json`。

| 脚本 | 用途 | 典型调用 |
|---|---|---|
| `scripts/new_issue.py` | 生成 issue 脚手架（自动取号） | `python3 scripts/new_issue.py --date 2026-10-15` |
| `scripts/next_number.py` | 查询下一期号（本地或 GitHub 只读） | `python3 scripts/next_number.py --remote owner/repo` |
| `scripts/validate_issue.py` | 格式校验（agent 与 CI 共用） | `python3 scripts/validate_issue.py issues/issue-43.md` |
| `scripts/dedup_urls.py` | 候选 URL 跨期去重（可 `--fuzzy`） | `python3 scripts/dedup_urls.py --candidates urls.txt` |
| `scripts/fetch_arxiv.py` | arXiv 周候选论文 | `python3 scripts/fetch_arxiv.py --days 7` |
| `scripts/fetch_github_trends.py` | GitHub 周趋势仓库 | `python3 scripts/fetch_github_trends.py --topic robotics` |
| `scripts/preview.py` | 单文件 HTML 预览 | `python3 scripts/preview.py issue.md --open` |
| `scripts/publish.py` | 安全发布（默认 dry-run） | `python3 scripts/publish.py issue.md`（确认后加 `--push`） |

常用旗标：`--config` 指定配置；validate `--strict`（警告即失败）/`--with-history`（E16 跨期）；
publish `--repo-dir`/`--allow-dirty`/`--message`。

## 草稿转换规则（convert 阶段，agent 执行）

输入：自由格式草稿（分区标题 + 条目字段不统一）。输出：符合配置的 `issue-N.md`。

1. 读配置确定板块集合、card type 映射、必填字段与别名、引用行模板。
2. 将草稿每个条目**语义归类**到目标板块；无法归类时放入最接近的板块并在回复中说明。
3. 条目改写为 `### N. [标签] [标题](url)`（标签必填与否看 `entry.tag_required`），
   字段按 `entry.required_fields` 顺序输出为 `- **字段名：** 内容`，别名先归一。
4. **摘要/亮点由 agent 撰写**：忠实原意、面向读者团队给行动建议；不得编造 URL 或事实。
5. 每个条目包进 `::: card <type>` / `:::`（`card.containers` 开启时）；空板块写占位行。
6. frontmatter：title 按模板生成、date、description、tags；H1 与 title 逐字相同。
7. 转换后立即 `validate_issue.py` 自检，error 清零后才进入 preview。

写作与排版细则、正反例见 `references/style-guide.md`。

## 校验规则摘要

E01 frontmatter 必备 / E02 title 模板+期号一致 / E03 date 格式 / E04 tags 数量 /
E05 H1=title / E06 引用行模板 / E07 板块顺序（NFC 比对）/ E08 `---` 分隔 /
E09 card 容器配对与 type / E10 条目 H3 模式 / E11 编号连续 / E12 字段齐全（经别名）/
E13 URL 合法 / E14 空板块占位 / E15 description 字数 / E16（--with-history）跨期重复；
W01 引文超长 / W02 文内 URL 重复 / W03 字段格式惯用式 / W04 persona 弱提示 / W05 全新标签。
配置关闭的规则自动跳过。阈值全部来自配置，勿在提示词里硬编码。

## 发布红线（必须遵守）

1. validate 存在 error → 拒绝发布（无 `--force-content --push` 双旗标不得绕过）。
2. preview 生成后**必须经用户确认**才可进入 publish。
3. publish 默认 dry-run；`--push` 仅在用户对本次发布明确同意后附加。
4. 推送前脚本会打印 remote/branch/文件清单；有脏工作区需用户知情后加 `--allow-dirty`。
5. 任何情况下不使用 force push（脚本无此入口，agent 也不得手工绕过）。
6. 目标仓库结构、期号冲突处理、回滚流程见 `references/publishing.md`。

## 预设与换皮

- 官方预设：`presets/minimal.json`（中性默认显式化）、`presets/embodied-ai-weekly.json`
  （具身智能周刊风格：5 板块 / 6 色 card / 三字段 / 各阈值）。
- 用户配置只需 `{"extends": "embodied-ai-weekly", ...覆盖字段}`；换预设即换风格。
- 新建预设并提交上游的流程见 `references/presets-guide.md`。

## 素材搜集（research 阶段，可选）

来源清单、API 查询式、去重策略与大陆网络注意事项见 `references/content-sourcing.md`。
原则：候选先过 `dedup_urls.py`，再进入草稿。

## Resources

- `references/`：style-guide / workflow / publishing / presets-guide / content-sourcing（按需加载）
- `assets/issue-template.md`（脚手架模板）、`assets/preview-style.css`（预览基础样式）、
  `assets/card-spec.md`（card 容器语法说明）
- `tests/run_tests.sh`：双 golden 回归（改动任何脚本/预设后必须先跑通）
