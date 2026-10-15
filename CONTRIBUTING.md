# Contributing to weekly-craft

感谢愿意贡献！本项目欢迎以下类型的改动：

- **新预设**（最欢迎）：为某种周刊风格（社区周刊 / 英文技术周刊 / 读书周刊……）制作 presets 文件
- **新校验规则**：发现了现有 21 条规则没覆盖的格式问题
- **Bug 修复**与文档改进（含英文翻译）
- **新素材源脚本**（如 RSS、Hacker News 检索）

## 开发环境

```bash
git clone https://github.com/kingdream-cn/weekly-craft.git
cd weekly-craft
python3 --version   # 需要 3.9+（3.9 / 3.10 / 3.11 / 3.12 均受支持）
```

无第三方依赖，不需要安装任何东西。

## 跑测试（提交前必须）

```bash
bash tests/run_tests.sh
```

全绿输出 `ALL TESTS PASSED` 才算通过。CI（GitHub Actions）会在 Python 3.9–3.12 矩阵上重复这一过程。

测试构成：

- `tests/test_common.py`：核心纯函数单测（配置合并、extends 链、URL 归一化等）
- `tests/golden/`：合法样本回归（neutral 零配置 + embodied 预设，任何改动不得让它们失败）
- `tests/bad/`：坏样本必须触发对应 rule id

## 添加预设

1. 复制 `presets/minimal.json` 为 `presets/<你的预设名>.json`（kebab-case）
2. 只写与默认不同的字段（字段全表见 `references/presets-guide.md`）
3. 自测：

```bash
echo '{"extends": "<你的预设名>"}' > /tmp/t.json
python3 scripts/new_issue.py --config /tmp/t.json --out /tmp/preset-check
python3 scripts/validate_issue.py /tmp/preset-check/*.md --config /tmp/t.json
python3 scripts/preview.py /tmp/preset-check/*.md --config /tmp/t.json
```

4. 可选但强烈建议：用你的风格写一份真实样本放进 `tests/golden/`，并在 `tests/run_tests.sh` 加一行校验
5. PR 描述里附：预设名、风格一句话描述、预览截图或演示站链接

预设里**不要**包含：私人仓库地址、真实姓名、与格式无关的业务数据。

## 添加校验规则

1. 规则 ID 顺延（当前最大：E16 / W05，新规则用 E17+ / W06+）
2. 规则必须**配置驱动**：阈值默认 0 或空字符串 = 关闭该检查，禁止硬编码
3. 在 `tests/bad/` 加坏样本，并在 `tests/run_tests.sh` 增加 `check_rule` 断言
4. 同步更新 `SKILL.md` 的规则摘要与 `references/style-guide.md`（如涉及写作规范）

## 代码规范

- 仅用 Python 标准库；保持 3.9 语法兼容（`from __future__ import annotations` 已可用）
- 退出码约定：`0` 成功 / `1` 业务失败（校验不通过等）/ `2` 环境错误（参数、网络、文件缺失）
- 脚本输出面向 LLM 与终端人类：不打印 traceback，错误信息以 `[ERROR]` 开头，重要脚本支持 `--json`
- 中文注释与消息为主（项目文档语言为中文），代码标识符用英文

## 提交与 PR

- 提交信息用前缀风格：`feat:` / `fix:` / `docs:` / `test:` / `chore:`
- 一个 PR 做一件事；预设提交单独开 PR
- PR 描述里贴 `bash tests/run_tests.sh` 的输出（或 CI 绿标）

## 行为准则

友好、就事论事。对格式设计的争论，优先拿真实周刊样本说话。
