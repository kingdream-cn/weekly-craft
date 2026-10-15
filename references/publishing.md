# 发布与目标仓库

## 目标仓库结构（VitePress 站点约定）

```
<weekly-repo>/
├── issues/issue-N.md        # 期刊源文件（issues_subdir 可配置）
├── .vitepress/
│   ├── theme/
│   │   ├── style.css        # 含 .news-card / .dark 样式
│   │   ├── issues.data.ts   # createContentLoader 读 issues/*.md frontmatter
│   │   └── components/      # 归档页网格等
│   └── config.*             # 站点配置
└── .github/workflows/deploy.yml   # push → 构建 → GitHub Pages
```

数据契约：归档页只读 frontmatter（title/date/description/tags），
所以 E01–E04 校验失败不仅影响单期渲染，还会破坏归档列表。

## publish.py 行为明细

流程：validate 前置 → 准备工作区（`--repo-dir` > 配置 `repo.workdir` > 临时 clone）→
`pull --rebase` 同步 → 写入 issues/ → commit（默认 message `publish: <title>`）→
dry-run 报告（默认到此为止）→ `--push` 时打印 remote/branch/文件清单 → 再次 rebase 同步 →
`git push origin <branch>`（无 force 入口）→ 写 `.publish-history.jsonl`。

### 三种拒绝路径

| 场景 | 表现 | 恢复 |
|---|---|---|
| 期号冲突 | 目标文件已存在且内容不同，exit 1 | `next_number.py` 重新取号；确要覆盖先人工核对远端版本 |
| 脏工作区 | `git status` 有其他改动，exit 1 | 处理/提交/stash 无关改动；知情后 `--allow-dirty` |
| rebase 冲突 | 同步阶段 `pull --rebase` 失败，自动 abort，exit 1，日志记 sync-conflict | 人工在仓库里 rebase 解决后重跑 |

### commit 约定

- 默认 `publish: <title>`（如 `publish: 2026具身周刊 - 第 43 期`）。
- 可用 `--message` 覆盖；修复类提交走仓库常规约定（fix:/docs: 等）。

## 回滚（禁 force push）

线上内容错误时的安全回滚 = 一个新的 revert commit：

```bash
cd <weekly-repo>
git log --oneline -- issues/issue-N.md      # 找到 publish commit
git revert <commit>                          # 生成反向提交
git push origin <branch>                     # 正常推送，CI 自动重建
```

- 只想改内容不想撤期：直接编辑 issue-N.md → validate → commit `fix: ...` → push。
- 期号已占用不可复用：删除内容但保留占位（frontmatter + 空板块），避免归档页跳号错乱。

## 凭据

- 全部走系统 git 凭据（HTTPS PAT 或 SSH key），脚本不接触、不存储任何 token。
- fetch_github_trends.py 可选读 `GITHUB_TOKEN` 环境变量提高限速，仅用于只读 API。

## 无 VitePress 站点的降级方案

1. **纯 Markdown 直发**：issue-N.md 本身是合法 GFM（card 容器退化为普通文本），
   可直接放任何静态博客/Hugo/Hexo 仓库；配置 `card.containers=false` 即完全兼容。
2. **单文件 HTML**：`preview.py` 产物是自包含 HTML（内联 CSS），
   可直接作为 release 附件或丢进任意静态托管。
3. **最小 VitePress 移植**：新建仓库 → `npm i -D vitepress` → 复制本预设的
   card 配色到 theme/style.css（`assets/card-spec.md` 给了 CSS 变量骨架）→
   issues/ 目录结构不变，本 Skill 全部脚本照常工作。
