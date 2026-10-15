# weekly-craft

周刊生成与排版风格 Agent Skill：把自由格式草稿变成规范化周刊 issue，
覆盖 取号 → 转换 → 校验 → 去重 → 预览 → 安全发布 全流程。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-green.svg)](#)
[![Zero deps](https://img.shields.io/badge/dependencies-0-orange.svg)](#)

适用于 Qoder / Claude Code/Trae 等支持 Agent Skills 的 CLI，也可脱离 agent
直接当命令行工具集使用。

## 特性

- **引擎与风格分离**：内置中性默认，零配置即可用；风格通过预设（presets）+ `extends` 换皮
- **格式校验器**：E01–E16 / W01–W05 共 21 条规则，全部配置驱动，关闭项自动跳过；agent 与 CI 共用
- **跨期去重**：URL 规范化（剥 utm/spm 等跟踪参数）+ 历史全量比对 + 可选标题模糊匹配
- **单文件 HTML 预览**：内联 CSS、暗色模式、card 配色按配置注入，无站点也能目检排版
- **两段式安全发布**：默认 dry-run，`--push` 需人工确认；期号冲突/脏工作区/rebase 冲突三重拒绝；无 force push 入口；`.publish-history.jsonl` 审计
- **素材抓取（可选）**：arXiv Atom API 周候选论文、GitHub Search API 周趋势仓库
- **零依赖**：全部脚本仅用 Python 3.9+ 标准库

## 快速开始

```bash
# 1. 生成一期脚手架（零配置 = 中性默认风格）
python3 scripts/new_issue.py --date 2026-10-15 --out ./issues

# 2. 填入内容后校验
python3 scripts/validate_issue.py issues/issue-1.md

# 3. 本地预览（浏览器打开）
python3 scripts/preview.py issues/issue-1.md --open

# 4. 发布（先 dry-run 看报告，确认后 --push）
python3 scripts/publish.py issues/issue-1.md --repo-dir /path/to/weekly-repo
```

在你的周刊工作目录放一个 `weekly.config.json` 即可定制一切：

```json
{
  "extends": "embodied-ai-weekly",
  "site_name": "2026具身周刊",
  "repo": { "remote": "https://github.com/you/your-weekly.git" }
}
```

## 安装（作为 Agent Skill）

### 途径一：skills.sh

```bash
npx --yes skills@1.5.22 add 'kingdream-cn/weekly-craft' -g -a qoder-cn -y
npx --yes skills@1.5.22 list   # 验证
```

> 大陆网络先执行 `npm config set registry https://registry.npmmirror.com`

### 途径二：手动

```bash
git clone https://github.com/kingdream-cn/weekly-craft.git
cp -r weekly-craft ~/.qoder-cn/skills/weekly-craft   # 或 ln -s
```

然后在 CLI 里 `/skills reload`，`/skills list` 应能看到 `weekly-craft`。
调用：`/weekly-craft convert draft.md` 或直接对 agent 说"帮我把这份草稿转成周刊"。

## 配置

完整字段表见 [references/presets-guide.md](references/presets-guide.md)，
带注释的示例见 [config.example.json](config.example.json)。

解析链：`--config` > `$WEEKLY_CONFIG` > `cwd/weekly.config.json` > `extends` 预设链 > 内置中性默认（深合并）。

常用项速览：

| 字段 | 说明 |
|---|---|
| `site_name` / `title_template` | 刊名与标题模板 |
| `sections[]` | 板块集合（标题、顺序、允许的 card type） |
| `entry.required_fields` / `field_aliases` | 条目字段与别名归一 |
| `card.containers` / `card.colors` | card 容器开关与配色 |
| `frontmatter.*` / `quote_max_chars` | 各类阈值（0 = 关闭检查） |
| `repo.remote` / `branch` / `workdir` | 发布目标 |

## 预设与换皮

| 预设 | 风格 |
|---|---|
| [`minimal`](presets/minimal.json) | 中性默认显式化：3 板块、无容器、单字段"摘要" |
| [`embodied-ai-weekly`](presets/embodied-ai-weekly.json) | 具身智能周刊：5 emoji 板块、6 色 card、核心亮点/团队参考/载体三字段 |

演示站点：[具身智能周刊](https://kingdream-cn.github.io/embodied-ai-weekly/)
即 `embodied-ai-weekly` 预设的实例。

换风格 = 换一行 `extends`；做自己的预设并提交上游见
[references/presets-guide.md](references/presets-guide.md)。

## 目录结构

```
weekly-craft/
├── SKILL.md              # agent 入口（工作流/速查表/红线）
├── scripts/              # 8 个零依赖 Python 脚本
├── presets/              # 官方预设
├── references/           # 深度文档（按需加载）
├── assets/               # 模板/样式/card 规范
├── tests/                # 双 golden 回归 + 15 坏样本
└── config.example.json
```

## 测试

```bash
bash tests/run_tests.sh   # 双 golden + 坏样本 rule id 断言，全绿输出 ALL TESTS PASSED
```

## FAQ

**Q: 会发布到 Qoder 官方市场（插件 zip）吗？**
A: v1 不做；当前以 GitHub 公开仓库 + skills.sh 为分发渠道，官方市场插件打包列入后续路线。


**Q: 必须用 VitePress 吗？**
A: 不必须。产出的 issue-N.md 是合法 GFM；无站点可用 preview.py 的单文件 HTML，
或 `card.containers=false` 直发任意博客。见 [references/publishing.md](references/publishing.md)。

**Q: 校验规则太严/太松？**
A: 所有阈值配置驱动，设 0/空即关闭对应检查，无需改代码。

**Q: 发布安全吗？**
A: 默认 dry-run 只打印报告；`--push` 前脚本展示 remote/branch/文件清单；
无 force push 入口；每次尝试写审计日志。

**Q: 可以只用其中某个脚本吗？**
A: 可以，8 个脚本相互独立（共享 `_common.py`），单独调用即可。

## License

[MIT](LICENSE) © 2026 kingdream
