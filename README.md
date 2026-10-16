# weekly-craft

周刊生成与排版风格 Agent Skill：把自由格式的素材草稿变成规范化、可发布的周刊 issue，
覆盖 **取号 → 素材池 → 转换 → 校验 → 去重 → 预览 → 安全发布** 全流程。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/kingdream-cn/weekly-craft/actions/workflows/test.yml/badge.svg)](https://github.com/kingdream-cn/weekly-craft/actions/workflows/test.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-green.svg)](#)
[![Zero deps](https://img.shields.io/badge/dependencies-0-orange.svg)](#)

适用于 Qoder / Claude Code / Trae 等支持 Agent Skills 的 CLI，也可脱离 agent，
直接当一套命令行工具集使用。

---

## 这是什么

周刊运营里最琐碎、最容易出错的不是"选题"，而是**排版一致性**：板块顺序、条目编号、
字段齐全、card 容器配对、跨期不重复、别把脏工作区推上去……这些是确定性的活儿，
适合脚本；而**归类、摘要、取舍**是语义性的活儿，适合 agent。weekly-craft 的边界就是：

- **脚本做确定性的事**：校验、渲染、去重、抓取、生成骨架、安全发布。
- **agent 做语义性的事**：把草稿归类到板块、写摘要/亮点、补缺字段。
- **风格与引擎分离**：脚本与格式规则内置中性默认，零配置即可用于**任何**周刊站点；
  你自己的风格通过 `presets/` 预设 + `extends` 换皮。

一句话：**别人 clone 下来换一行 `extends` 就能做出和你同款排版的周刊，而不是被你的风格绑死。**

## 特性

- **引擎与风格分离**：内置中性默认（零配置可用，适用于任何周刊）；风格通过预设 + `extends` 换皮，
  用户配置只需写要覆盖的字段，其余深合并继承。
- **格式校验器**：E01–E16 / W01–W05 共 21 条规则，**全部配置驱动**——阈值设 `0`/空即自动跳过该检查，
  无需改代码；校验器同时被 agent 自检和 CI 复用。
- **跨期去重**：URL 规范化（剥 `utm_*`/`spm`/`vd_source` 等跟踪参数、统一大小写、去尾斜杠）
  + 历史全量精确比对 + 可选标题模糊匹配（`--fuzzy`）；同一篇文章带不同跟踪参数只算一条。
- **单文件 HTML 预览**：内联 CSS、自动暗色模式、card 配色按配置注入，无需建站即可目检排版；
  附「本期统计」块（板块条目分布 + 必填字段完整度），纯 CSS 无依赖，只在预览里显示。
- **两段式安全发布**：默认 dry-run 只打印报告；`--push` 需人工确认；期号冲突 / 脏工作区 /
  rebase 冲突三重拒绝；**无 force push 入口**；每次尝试写 `.publish-history.jsonl` 审计。
- **素材抓取（可选）**：`fetch_arxiv.py` 抓 arXiv 周候选论文、`fetch_github_trends.py` 抓 GitHub
  周趋势仓库，输出的纯文本可直接喂给素材池。
- **本地素材池（手搓友好）**：候选先落盘成单文件 md 池子，你人工润色（视频条目可先抓 B 站标题/UP/时长），
  再用脚本**确定性**搬回 issue 骨架；缺字段**不猜**、留空交给校验器报出来。
- **零依赖**：全部脚本仅用 Python 3.9+ 标准库，无第三方包、无 Node、无 CDN。

## 工作流总览

```
research → pool? → draft → convert → validate → preview → confirm → publish → verify-CI
              ↑                    │(error)
              └────────────────────┘  修复后回到 validate
```

| 阶段 | 执行者 | 产物 | 把关 |
|---|---|---|---|
| research | agent + `fetch_*` 脚本 | 去重后的候选清单 | 候选先过 `dedup_urls.py` |
| pool（可选） | 脚本 + **你手搓** | `sources/issue-N-pool.md` | `[x]` 勾选 + 字段补全 |
| draft | agent | 自由格式草稿 md | — |
| convert | agent / `pool_to_issue.py` | `issue-N.md` | — |
| validate | 脚本 | 校验报告 | **error 必须清零** |
| preview | 脚本 | 单文件 HTML | 用户目检 |
| confirm | **用户** | 明确同意 | 无同意不发布 |
| publish | 脚本 | dry-run 报告 → commit → push | 三重拒绝 + 审计 |
| verify-CI | agent | CI 绿 + 线上 URL | Actions 查询 |

各阶段的断点续跑判据、拒绝路径与回滚见 [references/workflow.md](references/workflow.md)。

## 快速开始

### 主流程（4 步）

```bash
# 1. 生成一期脚手架（零配置 = 中性默认风格；期号自动取）
python3 scripts/new_issue.py --date 2026-10-15 --out ./issues

# 2. 填入内容后校验（零 error 才继续）
python3 scripts/validate_issue.py issues/issue-1.md

# 3. 本地预览（浏览器打开，含「本期统计」）
python3 scripts/preview.py issues/issue-1.md --open

# 4. 发布（先 dry-run 看报告，确认后加 --push）
python3 scripts/publish.py issues/issue-1.md --repo-dir /path/to/weekly-repo
```

### 素材池旁路（想先人工润色时）

视频/图文条目不放心全交给 agent 时，别让它直接写进 issue，**先把候选落盘**：

```bash
# 1. 建池并导入候选（可喂 fetch_arxiv / fetch_github_trends / dedup_urls 的纯文本输出）
python3 scripts/new_pool.py --number 44 --from candidates.txt

# 2.（可选）抓 B 站视频元信息成池条目
python3 scripts/fetch_bilibili.py BV1diGX6rEN5 \
    --pool sources/issue-44-pool.md --section "📚 精选教程 & 学习资源"

# 3. 手搓：把 [ ] 改成 [x]、补字段、用「- 板块：<板块名>」归类
# 4. 确定性搬成 issue 骨架（缺字段不猜，留空交给 validate）
python3 scripts/pool_to_issue.py sources/issue-44-pool.md
```

### 定制你自己的风格

在你的周刊工作目录放一个 `weekly.config.json` 即可：

```json
{
  "extends": "embodied-ai-weekly",
  "site_name": "2026具身周刊",
  "repo": { "remote": "https://github.com/you/your-weekly.git" }
}
```

## 脚本一览

全部 Python 3.9+ 标准库；退出码统一为 `0` 成功 / `1` 业务失败 / `2` 环境或参数错误；多数支持 `--json`。

| 脚本 | 作用 | 典型调用 |
|---|---|---|
| `new_issue.py` | 生成 issue 脚手架，期号自动取（本地或 GitHub 只读） | `new_issue.py --date 2026-10-15` |
| `next_number.py` | 只查询下一期号，不写文件 | `next_number.py --remote owner/repo` |
| `new_pool.py` | 建素材池并导入候选到「待归类」 | `new_pool.py --number 44 --from candidates.txt` |
| `fetch_bilibili.py` | 抓 B 站视频标题/UP/时长成池条目，可追加到板块 | `fetch_bilibili.py BV1xx --pool p.md --section "…"` |
| `pool_to_issue.py` | 素材池 → issue 骨架（确定性搬运，缺字段列出） | `pool_to_issue.py sources/issue-44-pool.md` |
| `validate_issue.py` | 格式校验（agent 与 CI 共用） | `validate_issue.py issues/issue-43.md` |
| `dedup_urls.py` | 候选 URL 跨期去重（可 `--fuzzy`） | `dedup_urls.py --candidates urls.txt` |
| `fetch_arxiv.py` | arXiv 周候选论文（Atom API） | `fetch_arxiv.py --days 7` |
| `fetch_github_trends.py` | GitHub 周趋势仓库（Search API） | `fetch_github_trends.py --topic robotics` |
| `preview.py` | 单文件 HTML 预览 + 本期统计 | `preview.py issue.md --open` |
| `publish.py` | 安全发布（默认 dry-run，`--push` 才推） | `publish.py issue.md --repo-dir <repo>` |

> `scripts/_common.py`（配置/解析/公共工具）与 `scripts/_pool.py`（素材池格式）是共享库，不作为命令直接调用。

常用旗标：`--config` 指定配置；validate `--strict`（警告即失败）/`--with-history`（E16 跨期比对）/
`--issue-dir`；publish `--repo-dir`/`--allow-dirty`/`--message`。

## 素材池（手搓友好）详解

**动机**：周刊里总有些条目需要人手打磨（尤其视频），全交给 agent 不放心，逐条口头描述又低效。
素材池是「人机接力」的中间态：脚本把候选落盘成一份**你熟悉 markdown 就能改**的文件，
你改完，脚本再把勾选的条目**确定性**地搬成 issue 骨架。

**单文件 md 池格式**：

```markdown
---
pool: issue-44
number: 44
date: 2026-10-16
topics: 具身智能、VLA 训练
description: "本期聚焦 VLA 训练数据质量。"
tags:
  - 具身智能
  - VLA
  - 仿真环境
---

## 💡 行业洞察

### [x] 1. 数据质量比规模更重要      ← [x] 才会入选；[ ] 表示暂不收录
- 链接：https://news.example.com/insight-1
- 来源：机器之心
- 类型：insight                  ← 该板块允许的 card type；留空取板块第一个
- 标签：洞察                      ← 条目 H3 的 [标签]
- 时长：8 分钟
- 核心亮点：用实验证明数据质量对收敛速度的影响更大。   ← 预设必填字段
- 团队参考：标注流水线可优先提升质量而非堆量。
- 载体：行业洞察 · 8 分钟速读
- 板块：💡 行业洞察               ← 填了就以它为准（可用「待归类」暂存后统一归类）
```

规则要点：

- **`## <板块标题>`** 需与预设板块一致；认不出的板块名会让条目「未归类」被跳过（会提示）。
- **`### [ ] N. 标题`**：`N` 可留空或任意，搬骨架时按**板块内顺序**重排为 `1..n`。
- **字段**：`- 键：值` 一行一个，也兼容 `- **键：** 值`。基础键 `链接/来源/类型/标签/时长`，
  再加预设的 `entry.required_fields`。
- **`## 待归类`** 是暂存区：导入的候选先落这里，手搓时移到目标板块或加 `- 板块：<板块名>`。

**分工与保证**：脚本只做确定性搬运（筛选 `[x]`、配 card 容器、套引用行/空板块占位、报告缺字段），
**绝不替你撰写摘要/亮点**——缺的部分留空，`validate_issue.py` 会以 E12/W03 报出来，再由 agent 补齐语义内容。
`pool_to_issue.py` 返回 `1` 表示结构性问题（无 `[x]` 条目 / 未归类 / tags 或 description 越界 / 缺 topics）。

## 安装（作为 Agent Skill）

### 途径一：skills.sh

```bash
npx --yes skills@1.5.22 add 'kingdream-cn/weekly-craft' -g -a qoder-cn -y
npx --yes skills@1.5.22 list   # 验证
```

> 大陆网络先执行 `npm config set registry https://registry.npmmirror.com`
> 版本号 `1.5.22` 为撰写时的可用版本，可用 `npx skills@latest --version` 查看最新再替换。

### 途径二：手动

```bash
git clone https://github.com/kingdream-cn/weekly-craft.git
cp -r weekly-craft ~/.qoder-cn/skills/weekly-craft   # 或 ln -s 软链，便于 git pull 更新
```

然后在 CLI 里 `/skills reload`，`/skills list` 应能看到 `weekly-craft`。
调用：`/weekly-craft convert draft.md`，或直接对 agent 说「帮我把这份草稿转成周刊」。

## 配置

完整字段表见 [references/presets-guide.md](references/presets-guide.md)，
带注释的示例见 [config.example.json](config.example.json)。

解析链（优先级从高到低，逐层**深合并**）：

```
--config  >  $WEEKLY_CONFIG  >  cwd/weekly.config.json  >  extends 预设链  >  内置中性默认
```

常用项速览：

| 字段 | 默认 | 说明 |
|---|---|---|
| `site_name` / `title_template` | `"周刊"` / `"{site_name} - 第 {number} 期"` | 刊名与标题模板 |
| `sections[]` | 3 个中性板块 | 板块集合：`{heading, card_types[]}`，顺序即校验顺序 |
| `entry.required_fields` | `["摘要"]` | 条目必填字段（有序，输出顺序一致） |
| `entry.field_aliases` | `{}` | 别名归一，如 `{"核心创新": "核心亮点"}` |
| `entry.tag_required` | `false` | 条目 H3 的 `[标签]` 是否必填 |
| `card.containers` / `card.colors` | `false` / `{}` | 是否用 `::: card <type>` 容器；各 type 配色 |
| `frontmatter.tags_min` / `tags_max` | `0` / `0` | tags 数量区间，0=不检查 |
| `frontmatter.description_max_chars` | `0` | description 字数上限，0=不检查 |
| `quote_line_template` / `quote_max_chars` | `""` / `0` | 引用行模板与引文长度上限 |
| `repo.remote` / `repo.branch` / `repo.workdir` | `""` / `"main"` / `""` | 发布目标仓库/分支/克隆目录 |

> **约定：阈值 `0` 或空一律表示"关闭该检查"**，校验器自动跳过对应规则，不必改代码。

## 预设与换皮

| 预设 | 风格 |
|---|---|
| [`minimal`](presets/minimal.json) | 中性默认的显式化：3 板块（本周要点/内容精选/工具与项目）、无 card 容器、单字段"摘要"，适合作为新周刊起点 |
| [`embodied-ai-weekly`](presets/embodied-ai-weekly.json) | 具身智能周刊：5 个 emoji 板块、6 色 card、三字段（核心亮点/团队参考/载体）、tags 3–5、description ≤80、引文 ≤125 |
| [`embodied-ai-weekly-legacy`](presets/embodied-ai-weekly-legacy.json) | 上者的**板块变体**：仅第 4 板块换成「⚙️ 工程实战 & 踩坑记录」，其余全部继承，复现早期形态 |

演示站点：[具身智能周刊](https://kingdream-cn.github.io/embodied-ai-weekly/) 即 `embodied-ai-weekly` 预设的实例。

换风格 = 换一行 `extends`。`embodied-ai-weekly-legacy` 是「板块变体」的最小示例：
只覆盖 `sections`（列表整体替换，需写全），配色/字段/阈值全靠继承。做自己的预设并提交上游见
[references/presets-guide.md](references/presets-guide.md)。

## 目录结构

```
weekly-craft/
├── SKILL.md              # agent 入口：工作流、脚本速查表、发布红线
├── scripts/              # 11 个零依赖 Python 脚本（+ _common.py/_pool.py 共享库）
├── presets/              # 官方预设（minimal / embodied-ai-weekly / embodied-ai-weekly-legacy）
├── references/           # 深度文档（style-guide / workflow / publishing / presets-guide / content-sourcing）
├── assets/               # issue 模板、预览样式、card 规范
├── tests/                # 单测（common + pool） + 四 golden + 15 坏样本 + run_tests.sh
├── config.example.json   # 带注释的配置示例
├── CONTRIBUTING.md       # 贡献指南
└── CHANGELOG.md          # 变更日志（Keep a Changelog + SemVer）
```

## 测试

```bash
bash tests/run_tests.sh   # 全绿输出 ALL TESTS PASSED
```

包含三部分：**单测**（`test_common.py` 配置/模板/去重/预览统计 + `test_pool.py` 素材池解析/搬运/端到端
validate）、**四份 golden**（中性、具身预设 ×2、板块变体，必须 PASS）、**15 份坏样本**（每份必须触发
对应 rule id，防止规则改动后静默失效）。

GitHub Actions 已在 **Python 3.9 / 3.10 / 3.11 / 3.12** 矩阵上自动跑同一套回归
（见 [.github/workflows/test.yml](.github/workflows/test.yml)），就是页面顶部那个 `tests` 徽章。

## 贡献

欢迎提交预设、新规则、脚本与文档改进，流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
提 Issue 请用 [模板](.github/ISSUE_TEMPLATE/)（bug / 功能请求 / 预设提交）；
改动任何脚本或预设后请先跑通 `bash tests/run_tests.sh`。

## FAQ

**Q: 会发布到 Qoder 官方市场（插件 zip）吗？**
A: v1 不做；当前以 GitHub 公开仓库 + skills.sh 为分发渠道，官方市场插件打包列入后续路线。

**Q: 必须用 VitePress 吗？**
A: 不必须。产出的 `issue-N.md` 是合法 GFM；无站点时可用 `preview.py` 的单文件 HTML，
或把 `card.containers` 设为 `false` 直发任意博客。见 [references/publishing.md](references/publishing.md)。

**Q: 校验规则太严 / 太松？**
A: 所有阈值配置驱动，设 `0` 或空即关闭对应检查，无需改代码。

**Q: 发布安全吗？**
A: 默认 dry-run 只打印报告；`--push` 前脚本展示 remote/branch/文件清单；期号冲突、脏工作区、
rebase 冲突三重拒绝；**无 force push 入口**；每次尝试写审计日志。

**Q: 可以只用其中某个脚本吗？**
A: 可以，11 个脚本相互独立（仅共享 `_common.py`/`_pool.py`），单独调用即可。

**Q: 素材池和让 agent 直接写 issue 有什么区别？**
A: 素材池把「确定性搬运」和「语义撰写」分开：你先在落盘文件上手搓，脚本负责格式与筛选，
缺字段留空、由校验器兜底，避免 agent 一次性产出难以人工微调的长文。

## License

[MIT](LICENSE) © 2026 kingdream
