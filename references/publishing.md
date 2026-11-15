# 提交与发布

## 先选择产物

双仓库编刊输出正文、侧边栏及 README，按 [双仓库编刊](dual-repo.md) 的完整包应用到独立公开分支，运行网站构建，再走现有 Git/PR 流程。`publish.py` 适合只发布一份正文的普通周刊。

## 单文件发布

目标必须是已有 Git 检出。`--repo-dir` 优先于配置 `repo.workdir`；`repo.remote` 用来核对 origin，`repo.branch` 核对当前分支。HTTPS 与 SSH 的同一 GitHub 地址视为同一个目标。

```bash
python3 <skill目录>/scripts/publish.py issue-N.md --repo-dir <目标检出> --config <配置>
# 明确需要本地提交时
python3 <skill目录>/scripts/publish.py issue-N.md --repo-dir <目标检出> --config <配置> --commit
# 已获本次发布授权时，提交并推送
python3 <skill目录>/scripts/publish.py issue-N.md --repo-dir <目标检出> --config <配置> --push
```

默认预演仅报告：不 fetch、pull、clone、创建目标文件、暂存、提交、推送或写审计文件。它基于当前检出，不声明远端最新状态。

`--commit` 明确创建本地提交；`--push` 包含提交操作，并先 fetch 检查远端基线。脚本不自动 rebase；远端较新或冲突时，先由调用者在明确目标分支上同步。推送被拒时保留本地提交，核对后可重试。没有 force push 入口。

默认要求工作区干净。确需保留其他工作时可显式 `--allow-dirty`，但本期目标文件本身有未提交改动则停止；提交仅包含本期文件，其他暂存/未暂存改动保留。推送还会拒绝携带其他文件的本地未发布提交，避免连带发布。

内容已一致时不重复提交。期号已存在且内容不同时停止，已有内容修改按项目正常修订流程处理，不通过覆盖已有期号绕过。校验失败默认停止；兼容旗标 `--force-content --push` 仅在用户明确要求绕过内容检查时使用。

实际提交或推送写目标仓库 Git 元数据目录中的 `.publish-history.jsonl`，不制造额外工作区改动；纯预演无日志。Git 凭据由现有 Git 配置管理，脚本不保存令牌。

## 发布后

按已授权流程核对 CI 和真实页面。报告已提交、已推送、已合并和已部署的实际状态；单次命令成功不证明网站已经上线。线上修订使用普通修复或 revert 提交。
