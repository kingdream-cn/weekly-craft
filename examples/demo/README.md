# 演示资料

全部投稿人、内容与 `example.com` 链接均为虚构示例。这里展示输出格式，不代表真实论文、开源项目或入刊决定。

- [pool.md](pool.md)：4 个候选的编辑源，2 个勾选拟入刊。
- [review.md](review.md)：由 `_review.render` 生成的负责人审核表；姓名为示例标签。
- [issue-1.md](issue-1.md)：由 `pool_to_issue.py` 生成的周刊正文。
- [preview.html](preview.html)：由 `preview.py` 生成的单文件预览。
- [checks.json](checks.json)：此示例的格式检查结果。
- [config.json](config.json)：继承现役七类预设，仅修改示例站点名。

[本地交互演示](../../docs/demo.html)将审核表的 HTML 渲染与原样周刊预览放入两个视图，便于切换查看。它是文档演示页，真实编刊仍由脚本与 agent 完成。

在仓库根目录可以生成自己的示例副本：

```bash
python3 scripts/pool_to_issue.py examples/demo/pool.md \
  --config examples/demo/config.json --out issue-1.md
python3 scripts/validate_issue.py issue-1.md --config examples/demo/config.json
python3 scripts/preview.py issue-1.md --config examples/demo/config.json --open
```

README 截图来自该演示页。修改示例并更新展示资料时，一并核对审核表、正文、预览和截图中的内容。

维护者可以运行 `python3 docs/build_demo.py` 重建固定虚构样例、检查记录和双视图 HTML；该脚本同样只使用 Python 标准库。重建后用浏览器打开演示页，分别切换两个视图更新截图。
