# weekly-craft

把投稿或草稿整理成可审核的 Markdown 周刊：生成正文、校验格式、跨期去重、预览排版，并准备网站更新。脚本处理文件，agent 整理内容，负责人决定入刊。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/kingdream-cn/weekly-craft/actions/workflows/test.yml/badge.svg)](https://github.com/kingdream-cn/weekly-craft/actions/workflows/test.yml)

Python 3.9+ 标准库，无第三方 Python 依赖。可作为 Agent Skill，也可直接使用 CLI。VitePress 网站构建沿用目标项目的 Node/npm 环境。

## 两种用法

| 场景 | 入口 |
| --- | --- |
| 已有公开周刊 + 私有投稿运营台账 | 连接两库，从真实投稿生成可审核出刊包 |
| 只有草稿、链接或素材池 | 继续使用独立格式工具，无需私有仓库 |

双仓库模式面向已有 `private-ledger-v1` 台账的项目。它复用有效性、去重、期号与通知规则，不另外建设采集器、数据库或常驻服务。通用格式引擎仍可通过预设用于其他周刊。

## 双仓库：连接一次，每期准备与生成

```bash
python3 scripts/editorial.py connect \
  --public-repo /path/to/public-weekly \
  --private-repo /path/to/private-operations

python3 scripts/editorial.py prepare \
  --config /path/to/private-operations/.weekly-private/weekly-craft.json --refresh
# 编辑返回目录中的 pool.md：补导读、核对摘要，调整拟入刊勾选
python3 scripts/editorial.py build \
  --config /path/to/private-operations/.weekly-private/weekly-craft.json --number 47
```

期号来自既有台账，示例 `47` 应替换为 prepare 返回值。每期只编辑一份 Markdown 池；来源、检查和续跑信息保存在私有侧。重复准备保留人工编辑，新增投稿追加，源内容变化单列提示。

生成内容包括本期正文、HTML 预览、校验结果，以及公开正文、VitePress 侧边栏和 README 近期三期的变更补丁。私有 `review.md` 自动列出全部候选的投稿人、类型、标题与一句话要点，按拟入刊和暂未入选分组；负责人按编号给出取舍即可。生成成功表示可审核，入刊和正式发布由负责人决定。实际台账、成员资料与通知记录不会进入公开包。

接口、历史周期、离线回放与应用补丁见 [双仓库编刊](references/dual-repo.md)。

## 普通草稿：独立使用

```bash
python3 scripts/new_issue.py --date 2026-11-16 --out ./issues
# agent 或编辑补充内容
python3 scripts/validate_issue.py issues/issue-1.md
python3 scripts/preview.py issues/issue-1.md --open
```

需要先人工整理素材时，用 `new_pool.py` 建池、`pool_to_issue.py` 转换。arXiv、B 站元信息及 GitHub 新建仓库抓取都是可选工具，不要求每期重新搜集。

## 安装为 skill

整个仓库就是 skill 目录，保留 `scripts/`、`references/`、`presets/` 和 `assets/`。例如先 clone 到自己的工作区，再链接到 Codex 用户技能目录：

```bash
git clone https://github.com/kingdream-cn/weekly-craft.git /path/to/weekly-craft
mkdir -p ~/.agents/skills
ln -s /path/to/weekly-craft ~/.agents/skills/weekly-craft
```

如果该位置已有技能，先核对原安装，不覆盖。Codex 支持目录软链接和自动发现；未出现时重启。见 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)。Claude Code 等宿主可将同一完整目录放到各自支持的技能目录，具体发现机制以宿主文档为准。

自然语言调用示例：

> 使用 weekly-craft，按已有双仓库配置准备本期周刊，整理摘要并生成预览和出刊包，交给我审核。

无需 agent API 密钥或额外后台；内容理解由当前调用 skill 的 agent 完成。没有 agent 时 CLI 负责确定性转换，摘要由编辑填写。

## 风格与配置

配置解析：`--config` → `WEEKLY_CONFIG` → 当前目录 `weekly.config.json` → `extends` 预设 → 内置中性默认。只写需要覆盖的字段。

| 预设 | 用途 |
| --- | --- |
| `minimal` | 中性三板块、单字段摘要、无 card |
| `embodied-ai-weekly` | 保留原五板块与既有格式要求 |
| `embodied-ai-weekly-legacy` | 原五板块的工程实战变体 |
| `embodied-ai-weekly-live` | 现役七类，空栏目可省略，不强制标签、阅读分钟数或摘要长度 |

```json
{"extends": "embodied-ai-weekly-live", "site_name": "我的具身周刊"}
```

阈值设 `0` 可关闭相应数量/长度检查。字段、配色及板块都可配置；详见 [预设指南](references/presets-guide.md) 和 [配置示例](config.example.json)。

## 提交与发布

完整出刊包先应用到公开独立分支，运行网站检查，再按授权走现有 Git/PR 流程。单份正文可用发布工具：

```bash
python3 scripts/publish.py issue-N.md --repo-dir /path/to/weekly --config weekly.config.json
# 显式本地提交加 --commit；已经获准的正式推送加 --push
```

默认预演不修改目标文件、索引或提交，也不联网同步。明确执行时核对 origin/分支，只提交本次文件；其他暂存改动保留。推送前检查远端基线，冲突交由调用者处理。详见 [发布说明](references/publishing.md)。

## 开发与验证

```bash
bash tests/run_tests.sh
```

包含配置与素材池单测、真实本地 Git 发布测试、双仓库接入与公开导出测试，以及历史 golden/坏样本回归。CI 沿用 Python 3.9–3.12 矩阵。测试状态徽章反映远端已提交版本；未发布的本地改进以实际检查记录为准。

- [SKILL.md](SKILL.md)：agent 入口。
- [CONTRIBUTING.md](CONTRIBUTING.md)：贡献约定。
- [CHANGELOG.md](CHANGELOG.md)：兼容行为与版本变化。

当前改进在 Unreleased；本地验收不等于 GitHub release、网站部署或群通知已完成。

## License

[MIT](LICENSE) © 2026 kingdream
