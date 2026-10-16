# 预设机制与配置字段全表

## extends 语法

配置文件（默认 `cwd/weekly.config.json`）顶层可写 `extends`：

```json
{
  "extends": "embodied-ai-weekly",
  "site_name": "2026具身周刊",
  "repo": { "remote": "https://github.com/owner/weekly-repo.git" }
}
```

- `extends` 取值：预设名（解析为 `<skill>/presets/<名>.json`）或任意相对/绝对路径。
- 可链式：预设自身也可 `extends` 另一个预设；检测到环会报错。
- 合并规则：**深合并**，本层字段覆盖上层；列表整体替换（不拼接）。
- 以 `_` 开头的键被忽略（可用来写注释，如 `"_comment": "..."`）。
- 完整解析链：`--config` > `$WEEKLY_CONFIG` > `cwd/weekly.config.json` > extends 链 > 内置中性默认。

## 字段全表（内置中性默认值）

| 字段 | 默认 | 说明 |
|---|---|---|
| `site_name` | `"周刊"` | 站点名，用于 title 模板 |
| `title_template` | `"{site_name} - 第 {number} 期"` | 占位符 `{site_name}` `{number}` |
| `issue_filename` | `"issue-{number}.md"` | 文件名模板，占位符 `{number}` |
| `issues_subdir` | `"issues"` | 仓库内期刊目录 |
| `pool_dir` | `"sources"` | 素材池目录 |
| `pool_filename` | `"issue-{number}-pool.md"` | 素材池文件名模板，占位符 `{number}` |
| `sections` | 3 个中性板块 | 数组，元素 `{heading, card_types[]}`；heading 逐字匹配（校验前 NFC）；card_types 为该板块允许的 card type（空=不允许/不校验） |
| `separator` | `"---"` | 板块分隔线 |
| `empty_section_placeholder` | `"> *本期暂无收录。*"` | 空板块占位行 |
| `quote_line_template` | `""` | 空=不生成引用行；支持 `{date}` `{topics}` |
| `entry.required_fields` | `["摘要"]` | 有序列表，条目必须按此顺序输出字段 |
| `entry.field_aliases` | `{}` | 归一映射 `{"核心创新": "核心亮点"}`，校验与转换都先过别名 |
| `entry.tag_required` | `false` | H3 的 `[标签]` 是否必填 |
| `entry.carrier_field` | `""` | 指定某字段为"载体"字段（配合 W03） |
| `entry.carrier_pattern` | `""` | 载体格式正则，空=不检查 |
| `card.containers` | `false` | 是否使用 `::: card <type>` 容器 |
| `card.colors` | `{}` | `{type: {bg, border, dark_bg, dark_border}}`，preview 注入 CSS 变量 |
| `frontmatter.required` | `["title","date","description","tags"]` | 必备字段 |
| `frontmatter.tags_min/max` | `0/0` | tags 数量区间，0=不检查 |
| `frontmatter.description_max_chars` | `0` | 0=不检查 |
| `quote_max_chars` | `0` | 引用行内引文长度上限，0=不检查 |
| `persona` | `""` | 读者人设描述（W04 弱提示用），空=不检查 |
| `dedup.title_threshold` | `0.85` | --fuzzy 标题相似度阈值 |
| `dedup.url_strip_params` | `["utm_*","spm","vd_source"]` | 规范化时剥除的参数（fnmatch） |
| `sources.arxiv_categories` | `[]` | fetch_arxiv 默认查询分类 |
| `sources.github_topics` | `[]` | fetch_github_trends 默认 topics |
| `sources.sites` | `[]` | 手工来源清单（agent 参考，脚本不用） |
| `repo.remote` | `""` | 目标仓库（URL 或本地路径） |
| `repo.branch` | `"main"` | 发布分支 |
| `repo.workdir` | `""` | 本地克隆目录，空=publish 用临时 clone |

**约定：阈值 0/空 一律表示"关闭该检查"，校验器自动跳过对应规则。**

## 官方预设

- `minimal.json`：中性默认的显式化，适合作为新周刊的起点直接改。
- `embodied-ai-weekly.json`：具身智能周刊风格——5 个 emoji 板块、6 色 card、
  三字段（核心亮点/团队参考/载体）、tags 3–5、description ≤80、引文 ≤125。
  演示站点即该预设的实例；任何人 `extends` 它即可复刻同款排版。
- `embodied-ai-weekly-legacy.json`：上者的**板块变体**，见下。

## 板块变体（只换板块，其余继承）

同一刊物的板块构成会随选题演进。做法是让变体预设 `extends` 主预设，
**只覆盖 `sections`**，配色/字段/阈值全继承——`embodied-ai-weekly-legacy` 就是范例：
它把第 4 板块从「🛒 硬件测评 & 选型雷达」换回早期形态（issue 37–41）的
「⚙️ 工程实战 & 踩坑记录」，复用了已有的 `practice` 配色，因此无需新增任何 color 定义。

```json
{
  "extends": "embodied-ai-weekly",
  "sections": [
    { "heading": "💡 行业洞察", "card_types": ["insight"] },
    { "heading": "📚 精选教程 & 学习资源", "card_types": ["tutorial"] },
    { "heading": "🛠️ 开源项目 & 行业案例", "card_types": ["opensource", "practice"] },
    { "heading": "⚙️ 工程实战 & 踩坑记录", "card_types": ["practice"] },
    { "heading": "📑 顶会前沿 & 论文速递", "card_types": ["paper"] }
  ]
}
```

要点：

- `sections` 是**列表整体替换**，所以变体要写全所有板块，不能只写改动那一项。
- 新板块优先复用主预设已有的 card type（配色随之继承）；确实要新 type 时，
  再在 `card.colors` 里补上该 type 的 4 个色值（`bg`/`border`/`dark_bg`/`dark_border`）。
- 变体不会自动同步主预设的后续改动：主预设改板块时，变体要跟着改。
- 回归保障：变体一般配一个早期形态的 golden（如 `tests/golden/issue-40-legacy.md`）
  钉住"只换板块、其余继承"的语义，见 `tests/test_common.py::TestPresetVariants`。

## 制作新预设

1. 复制 `presets/minimal.json` 为 `presets/<你的名字>.json`。
2. 只写与默认不同的字段即可（extends 链会补齐其余）；板块/card/字段/阈值按需覆盖。
3. 自测三件套：

```bash
echo '{"extends": "<你的名字>"}' > /tmp/t.json
# 取号要能从 --out 的上级目录定位到 issues 目录，所以写到 .../issues 下
python3 scripts/new_issue.py --config /tmp/t.json --out /tmp/out/issues
python3 scripts/validate_issue.py /tmp/out/issues/*.md --config /tmp/t.json
python3 scripts/preview.py /tmp/out/issues/issue-1.md --config /tmp/t.json --open
```

4. 提交上游：fork 仓库 → 加预设文件（可选：加一个 golden 样本进 `tests/`）→
   跑 `tests/run_tests.sh` 全绿 → 发 PR，描述里附预览截图。

预设不应包含：私人仓库地址、真实读者姓名、与格式无关的业务数据。
