# 工作流状态机

```
research → pool? → draft → convert → validate → preview → confirm → publish → verify-CI
              ↑                    │(error)            
              └────────────────────┘  修复后回到 validate
```

`pool?` 为可选旁路：需要人工润色（尤其视频/图文条目）时先落盘素材池手搓，再确定性搬成骨架。

## 各阶段：产物、执行者、断点续跑

| 阶段 | 执行者 | 输入 | 产物 | 续跑判据 |
|---|---|---|---|---|
| research | agent + fetch_* 脚本 | 配置 sources | 候选 URL/素材清单 | 候选文件存在即跳过 |
| pool（可选） | 脚本 + **用户手搓** | 候选清单 | `sources/issue-N-pool.md` | 池中 `[x]` 条目齐、字段全即跳过 |
| draft | agent | 候选 + 去重结果 | 自由格式草稿 md | 草稿文件存在即跳过 |
| convert | agent / pool_to_issue 脚本 | 草稿或池 + 配置 | `issue-N.md` | 目标文件存在且过 validate 即跳过 |
| validate | 脚本 | issue-N.md | 校验报告 | error=0 才进入下一阶段 |
| preview | 脚本 | issue-N.md | 单文件 HTML | 用户目检通过 |
| confirm | **用户** | 预览 + 校验报告 | 明确同意 | 无同意不发布，任何情况下不代用户确认 |
| publish | 脚本 | issue-N.md + 同意 | dry-run 报告 → commit → push | 见 publish 输出 |
| verify-CI | agent | push 成功 | CI 绿 + 线上 URL 可见 | `gh run watch` 或轮询 API |

## research

1. `python3 scripts/fetch_arxiv.py --days 7`（配置了 `sources.arxiv_categories` 时）
2. `python3 scripts/fetch_github_trends.py`（配置了 `sources.github_topics` 时）
3. 手工来源（视频站/公众号等）由 agent 用 WebSearch/WebFetch 补充，见 content-sourcing.md
4. 全部候选写入 `candidates.txt`（每行 `URL` 或 `URL<TAB>标题`）
5. `python3 scripts/dedup_urls.py --candidates candidates.txt --fuzzy` → 只保留 NEW 行

## pool（素材落盘 → 手搓 → 搬骨架，可选）

想自己动手改（视频条目尤其如此）时，别让 agent 直接从候选写进 issue，先把候选落盘：

```bash
# 建池 + 导入候选（吃 dedup_urls / fetch_arxiv / fetch_github_trends 的纯文本输出）
python3 scripts/new_pool.py --number 44 --from candidates.txt
# 视频条目：抓 B 站元信息并追加到指定板块（板块标题需与预设一致）
python3 scripts/fetch_bilibili.py BV1diGX6rEN5 --pool sources/issue-44-pool.md --section "📚 精选教程 & 学习资源"
# 手搓后用池子确定性搬成 issue 骨架
python3 scripts/pool_to_issue.py sources/issue-44-pool.md
```

**池格式约定**（单文件 md）：

- frontmatter：`pool/number/date/topics/description/tags`；`pool_to_issue` 的期号/日期/topics/description/tags 都取自这里（可 `--number/--date/--topics` 覆盖）。
- `## <板块标题>` 需与预设板块一致；认不出的板块名会让条目「未归类」被跳过。
- 条目：`### [ ] N. 标题`，`[x]` 表示入选（只有 `[x]` 会进 issue）；`N` 可留空或任意，搬骨架时按板块内顺序重排。
- 字段：`- 键：值` 一行一个（也兼容 `- **键：** 值`）。基础键 `链接/来源/类型/标签/时长`，
  再加预设 `entry.required_fields`；`类型` 留空取该板块第一个 card type，`板块` 填了就按它归类。
- `## 待归类` 是暂存区：导入的候选先落这里，手搓时移到目标板块或加 `- 板块：<板块名>`。

**分工**：脚本只做确定性搬运（选条目、配 card 容器、套引用行/占位行、报告缺字段），
**不写摘要/亮点**——缺字段留空，validate 报 E12/W03，再由 agent 补齐语义内容。
返回码：0 = 生成成功；1 = 结构性问题（无 `[x]` 条目 / 未归类 / tags 或 description 越界 / 缺 topics）。

## draft → convert

- 草稿是自由的：分区可以不规范、字段可以缺，convert 阶段由 agent 归一。
- convert 规则见 SKILL.md「草稿转换规则」；写作细则见 style-guide.md。
- 期号：`new_issue.py` 自动取号（本地 issues/ 或 GitHub 只读查询）。手工指定用 `--number`。

## validate → preview

```bash
python3 scripts/validate_issue.py issue-N.md --with-history --strict
python3 scripts/preview.py issue-N.md --open
```

- error 必须清零；warning 逐条向用户说明后再决定是否修复。
- preview 目检清单：① 板块配色正确 ② card 圆角/边框 ③ 暗色模式可读
  ④ 链接可点（新标签页）⑤ 空板块显示斜体占位、无 `<pre>` 降级块。

## confirm → publish

**红线**：confirm 是用户专属阶段。agent 展示校验报告 + 预览路径后停下等确认。

```bash
# 第一步永远是 dry-run
python3 scripts/publish.py issue-N.md --repo-dir <周刊仓库>
# 用户看过 dry-run 输出（remote/branch/文件清单/diff 摘要）并同意后
python3 scripts/publish.py issue-N.md --repo-dir <周刊仓库> --push
```

拒绝路径与恢复见 publishing.md。

## verify-CI

1. push 成功后查询 Actions：`gh run list --repo <owner/repo> -L 3` 或 GitHub API。
2. CI 绿后访问线上 issue URL 确认渲染正常。
3. CI 红：读日志定位（通常是 VitePress 构建对 frontmatter/容器的解析问题），
   修复后走正常 commit + push（禁止 force）。

## 中断恢复

- 所有脚本幂等：重复运行 validate/preview/dedup 无副作用。
- publish 中断（如 push 网络失败）：先 `git -C <repo> status`，
  本地 commit 已存在则只需重跑 `--push`；rebase 进行中则 `git rebase --abort` 后重来。
- `.publish-history.jsonl`（publish 工作目录）记录每次尝试结果，可审计。
