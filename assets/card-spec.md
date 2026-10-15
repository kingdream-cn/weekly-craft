# card 容器语法规范

## 语法

```markdown
::: card <type>
### N. [标签] [标题](url)
- **字段：** 内容
:::
```

- 开栏 `::: card <type>`：三个冒号 + 空格 + `card` + 空格 + type；独占一行。
- 闭栏 `:::`：独占一行，与最近的开栏配对；不嵌套。
- `card.containers=false` 时不使用容器，条目直接裸露在板块下（纯 GFM 兼容）。

## type 机制

- type 是自由字符串，但必须属于所在板块配置的 `sections[].card_types` 集合，
  否则校验报 E09。
- type → 视觉：`card.colors` 配置 `{type: {bg, border, dark_bg, dark_border}}`，
  preview.py 注入为 CSS 变量 `--card-bg` / `--card-border`（暗色走 media query）。
- VitePress 侧由主题把 `::: card <type>` 渲染为
  `<div class="news-card card-<type>">`；本 Skill 的 preview 复刻同一 class 命名，
  样式骨架见 `assets/preview-style.css`。

## 移植到 VitePress 主题的最小 CSS

```css
.news-card {
  border-radius: 10px;
  padding: 4px 16px 12px;
  margin: 16px 0;
  background: var(--card-bg, #f7f8fa);
  border: 1px solid var(--card-border, #e8eaee);
}
/* 每个 type 一组变量，例： */
.news-card.card-insight { --card-bg: #fff8e6; --card-border: #f3e3bd; }
.dark .news-card.card-insight { --card-bg: #2a2416; --card-border: #3d351f; }
```

## 校验规则关联

| 规则 | 检查点 |
|---|---|
| E09 | 开闭配对、type ∈ 板块 card_types、containers 开关与实际一致 |
| E10 | 容器内条目 H3 模式 |
| E14 | 容器不得为空；空板块用占位行且不包容器 |
