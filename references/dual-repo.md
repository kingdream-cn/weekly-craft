# 双仓库编刊

适用：公开仓库保存 Issue 投稿、期刊 Markdown 和 VitePress 网站；私有仓库已有 `private-ledger-v1` 台账（`automation/state:state.json`）。其他周刊仍可独立使用普通格式工具，无需采用此运营模型。

## 连接一次

```bash
python3 <skill目录>/scripts/editorial.py connect \
  --public-repo <公开仓库本地根目录> \
  --private-repo <私有仓库本地根目录>
```

配置默认写入私有仓库 `.weekly-private/weekly-craft.json`，记录两个检出的路径和 origin 身份。使用者负责选取自己的私有检出；本地目录名不证明 GitHub 可见性。接入真实项目时通过 GitHub 元数据确认运营仓库仍为 Private。

已有 `WEEKLY_CONFIG` 或当前工作目录 `weekly.config.json` 指向该连接时，每期命令可以省略 `--config`；可以在本地工作区用软链接指向私有配置，避免复制一份配置。

实际工作放在同一私有仓库 `.weekly-private/editorial/`。已有忽略规则保留；缺少规则时只在本地 Git exclude 补充该目录。配置无令牌，网络认证复用现有 Git 凭据。首次读取或需要更新来源时使用 prepare 的 `--refresh`。

## 每期两条命令

```bash
python3 <skill目录>/scripts/editorial.py prepare --config <私有配置> --refresh
# agent 或负责人编辑返回目录中的 pool.md
python3 <skill目录>/scripts/editorial.py build --config <私有配置> --number <prepare返回的期号>
```

`prepare` 默认选择北京时间当前收集周；历史回放或指定周期可传 `--week 2026-W46`。从该周冻结的 `target_issue_number`、`target_release_week` 读取期号与计划入刊周，默认日期为入刊周周一，也可用 `--date YYYY-MM-DD` 指定实际发布日期。期号不按 ISO 周号猜测，显式 `--number` 只能核对，不能覆盖台账。

`--refresh` fetch 公开 main 和私有 automation/state，仅更新本地跟踪引用。无该参数时使用现有本地引用，适合离线回放。一次准备锁定来源 commit，写入 manifest；来源已前进时再运行 prepare，人工编辑会保留。脚本不运行公开仓库代码，不执行台账分支中的程序。

## 编辑 pool.md

这是每期唯一需要直接编辑的源文件。补充开头的 `topics`、`description`、`tags`，随后调整条目：

- `[x]`：拟入刊；`[ ]`：保留候选，不生成正文。最终决定由负责人审核。
- `核心亮点`、`团队参考`、`载体` 进入正文；`核对摘录`、`投稿` 等辅助信息保留在私有池。
- `板块` 选配置中的标题；`类型` 对应 card 标识。七类网站支持 `practice` 独立栏目，空栏目省略。
- `核验状态` 可记录原文核对情况，仅用于私有审阅，不自动出现在正文。
- 未解决、重复或已刊候选放在「待审」；后续周计划的候选保留在原台账。

原文链接、摘录和投稿理由是输入证据，不证明结论为真。agent 核对原文后再润色摘要；未核实内容在池和审阅记录中写清状态。人工不需要填额外审批字段，也不要求固定摘要字数或阅读分钟数。

重复运行 prepare 保留已有条目及勾选；只追加新投稿。源内容或状态变化写入 `manifest.json` 的 `source_review`，最新投影放在 `sources` 供比对，不覆盖原摘要。处理后可删除已解决的 review 提醒。用户主动删除过的候选不会被重复加回。若要重新创建整期，先保留旧工作目录再重新准备。

## 出刊包

每期目录包含：

```text
issue-N/
  pool.md                 编辑源
  manifest.json           来源 commit、公开内容投影与变更提示
  issue-N.md              生成正文
  preview.html            单文件预览
  checks.json             实际校验与待审提示
  public/                 拟公开文件：正文、侧边栏、README
  public.patch            可在公开独立分支审阅应用的补丁
  bundle.json             公开文件清单、哈希及来源基线
```

检查失败时不生成有效 bundle/patch。修正池后重跑 build。不要直接编辑生成文件；修改 pool 后再 build，确保摘要、预览和公开包一致。

`public/` 只含三个目标：本期正文、`.vitepress/config.mjs`、`README.md`。README 更新近期三期与已有进度计数，保留其他说明。侧边栏使用对应年份分组；跨年首次需要在公开配置增加该年份组。其他网站可继续使用格式引擎，适配导航更新时改此适配器，不扩张通用格式规则。

## 应用与构建

负责人确认内容后，按当前授权在公开仓库独立分支操作。先核对 `bundle.json` 的 `public_head` 与目标基线，审阅 `public.patch`；有其他文档分支时按实际分支解决冲突，保护已有修改。

```bash
git -C <公开独立检出> apply --check <本期目录>/public.patch
git -C <公开独立检出> apply <本期目录>/public.patch
# 在该检出运行项目要求的检查及 npm run docs:build
```

完整包包含网站入口，使用普通 Git/PR 流程提交明确的三个路径。`publish.py` 只处理单份正文，不用它替代完整包的导航变更。合入 main 可能直接触发 Pages 部署；发布和通知按用户明确指令执行。原私有台账与通知状态不会被本工具回写。
