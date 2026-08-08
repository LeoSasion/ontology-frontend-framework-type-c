---
name: AIBI-C
description: 克制、清晰、以证据和操作边界为中心的本地分析工作台
colors:
  canvas: "#f5f7fb"
  surface: "#ffffff"
  surface-subtle: "#f8fafd"
  border: "#d7e0ec"
  border-strong: "#b9c6d6"
  text: "#172033"
  text-muted: "#5f6b7b"
  text-soft: "#667386"
  accent: "#0e7490"
  accent-strong: "#155e75"
  accent-soft: "#e7f6f8"
  on-accent: "#ffffff"
  danger: "#a83f38"
  danger-soft: "#fff0ee"
  success: "#15803d"
  success-soft: "#edf9f1"
  warning: "#b45309"
  warning-soft: "#fff7e8"
  chart-success-overlay: "rgba(42, 115, 74, 0.24)"
  chart-success-overlay-strong: "rgba(42, 115, 74, 0.28)"
  editor-danger-strong: "#8f342e"
  editor-trust-ring: "rgba(19, 127, 138, 0.35)"
  editor-trust-fill: "rgba(19, 127, 138, 0.08)"
  editor-warning-ring: "rgba(168, 122, 35, 0.28)"
  editor-warning-fill: "rgba(168, 122, 35, 0.08)"
  editor-warning-ring-strong: "rgba(168, 122, 35, 0.3)"
  editor-warning-fill-strong: "rgba(168, 122, 35, 0.1)"
  editor-warning-ring-soft: "rgba(168, 122, 35, 0.25)"
  editor-warning-fill-soft: "rgba(168, 122, 35, 0.12)"
  monitor-warning: "#c88716"
  field-profile-info: "#245c88"
  import-success-fill: "rgba(16, 185, 129, 0.08)"
  import-danger-fill: "#fff7f6"
  dark-text-muted: "#31403c"
  destructive-red: "rgb(220 38 38)"
  theme-slate: "#28424d"
  theme-deep-teal: "#0f2d37"
typography:
  display:
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "clamp(22px, calc(18px + 1cqi), 30px)"
    fontWeight: 750
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  headline:
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "clamp(16px, calc(14px + 0.45cqi), 20px)"
    fontWeight: 700
    lineHeight: 1.2
  title:
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "clamp(15px, calc(14px + 0.3cqi), 17px)"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "clamp(13px, calc(12px + 0.18cqi), 14px)"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif'
    fontSize: "clamp(11px, calc(10px + 0.14cqi), 12px)"
    fontWeight: 700
    lineHeight: 1.25
  code:
    fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", monospace'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  micro: "2px"
  graph: "3px"
  indicator: "4px"
  compact: "6px"
  sm: "7px"
  md: "8px"
  icon: "9px"
  lg: "10px"
  panel-sm: "11px"
  panel-md: "12px"
  panel-lg: "14px"
  dialog: "16px"
  pill: "999px"
spacing:
  xs: "clamp(3px, 0.45cqi, 4px)"
  sm: "clamp(6px, 0.85cqi, 8px)"
  md: "clamp(9px, 1.25cqi, 12px)"
  lg: "clamp(12px, 1.7cqi, 16px)"
  page-inline: "clamp(18px, 3cqi, 36px)"
  page-block: "clamp(22px, 2.7cqi, 32px)"
  card: "clamp(18px, 2.2cqi, 26px)"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "38px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "38px"
  field:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
  navigation-active:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-strong}"
    rounded: "{rounded.sm}"
    padding: "7px 10px"
    height: "40px"
  task-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "{spacing.card}"
---

# Design System: AIBI-C

## Overview

**Creative North Star: “可核对的工作台”**

AIBI-C 的界面像一张整理清楚的分析工作台：当前任务始终占据视觉中心，证据、状态和写入边界紧邻决策出现，高级能力退到用户主动展开的位置。它不是展示型数据大屏，也不是聊天气泡堆叠，而是让业务用户能快速读懂、核对并继续工作的 Operate 型界面。

整体以冷静的浅色纸面、低饱和青色强调和紧凑但不拥挤的信息密度建立可信感。装饰只服务于状态、层级或聚焦；同类对象共享稳定的形状、间距和语言，使用户在复杂分析中把注意力留给数据本身。

**Key Characteristics:**

- 单一主任务先行，高级工具渐进披露。
- 中性浅色表面承载内容，青色只标识关键动作和当前状态。
- 紧凑角色字体与流式间距共同适配分析密度。
- 证据、错误和写入边界以语义与文字双重表达。

## Colors

调色板以冷纸面和深墨文字为底，用克制的青色建立可信操作焦点；成功、警告和危险色只承担状态语义。

### Primary

- **可信青**（`accent` / `accent-strong`）：用于主操作、当前导航、焦点和可信流程进度。
- **证据青雾**（`accent-soft`）：用于已选择、已完成或需要轻量强调的背景，不承担正文对比。

### Neutral

- **冷纸底**（`canvas`）：应用画布和区域间留白。
- **证据纸面**（`surface` / `surface-subtle`）：主要内容与输入区域的两级表面。
- **深墨**（`text`）：标题、主要正文和关键数字。
- **石板说明**（`text-muted` / `text-soft`）：辅助文字、标签和元数据；不得弱化到不可读。
- **结构线**（`border` / `border-strong`）：分组、输入边界和高优先级容器边界。

### Status

- **阻断红**（`danger` / `danger-soft`）：失败、危险和需要恢复的状态。
- **完成绿**（`success` / `success-soft`）：完成、可用和通过状态。
- **注意琥珀**（`warning` / `warning-soft`）：等待、风险和需要人工核对的状态。

**The Semantic Color Rule.** 状态颜色必须同时配有文字、图标或结构信号；不能只靠色相传达含义。

## Typography

**Display Font:** Inter，回退到系统无衬线、Segoe UI 与 Microsoft YaHei

**Body Font:** 与 Display 相同
**Label Font:** 与 Body 相同

**Character:** 单一字体家族保持中英文和数据标签的稳定度；层级由角色字号、字重、空间和色调共同形成，不通过增加字体家族制造个性。

### Hierarchy

- **Display**（`display`）：页面标题和工作区首要命题，使用紧凑行高与轻微负字距。
- **Headline**（`headline`）：模块标题和工作台段落入口。
- **Title**（`title`）：任务卡、状态卡和图表标题。
- **Body**（`body`）：说明、结果摘要和表单正文；长段落控制在约 45–75 个字符的舒适阅读宽度。
- **Label**（`label`）：字段名、状态名和元数据，依靠字重而不是全大写建立辨识度。

**The One-Family Rule.** Operate 界面不为装饰引入第二字体；数字、中文和英文必须在同一角色层级中保持可扫描。仅代码、SQL、指纹和严格测量值使用 SFMono / Consolas 等宽回退。

## Layout

桌面使用固定范围侧栏与弹性主工作区；内容容器通过 container query 根据自身可用宽度重排。页面间距、段落间距和卡片内边距采用流式令牌，短边不小于 720px 时保持结构性适配，横向 1280×720 和竖向 720×1280 都是正式验收尺寸。

主路径顺序固定为：页面上下文 → 可信流程 → 当前唯一任务 → 次要工具。相关信息优先通过邻近和间距分组，只有需要状态边界或独立滚动时才增加容器。窄屏将侧栏改为顶部导航，卡片与表单重排为单列；短边低于 720px 时维持 720px 逻辑画布并整体等比缩放。

**The One Current Task Rule.** 首屏只能有一个视觉上占主导的下一步；次要动作不得与主操作拥有相同重量。

## Elevation & Depth

系统以结构线和浅色表面分层为主，阴影为辅。常驻工作区与任务卡默认保持平面；阴影只用于临时浮层、菜单或确实需要从背景中抬起的独立面板。

### Shadow Vocabulary

- **Ambient panel**（`--shadow`）：只用于需要独立层级的面板或浮层，不用于堆叠所有卡片。

**The Flat-by-Default Rule.** 先用间距、边界和色阶说明结构；阴影不是默认容器装饰。

## Shapes

形状以 7–10px 的轻度圆角为主：导航和小控件更紧，输入与按钮保持中等圆角，主任务卡使用较宽但不过度柔软的圆角。2–6px 只用于图表标记、迷你条和紧凑指示器；11–16px 只用于复杂面板、审计区和对话容器。圆形仅用于步骤标记、状态点和计数徽章；大面积胶囊形不得替代常规按钮或标签结构。

## Components

### Buttons

- **Shape:** 紧凑矩形，中等圆角；正文标签与图标保持同一基线。
- **Primary:** 可信青背景、白色文字，主任务区域只保留一个。
- **Hover / Focus:** hover 加深到 `accent-strong`；键盘焦点始终显示 2px 青色轮廓。
- **Secondary:** 纸面背景、强结构线和深墨文字，不与主操作争夺视觉权重。

### Cards / Containers

- **Corner Style:** 一般容器使用 `rounded.md`，主任务使用 `rounded.lg`。
- **Background:** 主要内容使用 `surface`，输入或次级区域使用 `surface-subtle`。
- **Shadow Strategy:** 默认平面；浮层才使用 ambient panel。
- **Border:** 普通分组使用 `border`，当前主任务或输入边界使用 `border-strong`。
- **Internal Padding:** 采用 `spacing.card`，随容器宽度在安全范围内流动。

### Inputs / Fields

- **Style:** 次级纸面、明确边界和持久标签；placeholder 只作为示例。
- **Focus:** 边界切换为可信青，并出现柔和 focus ring。
- **Error / Disabled:** 错误紧邻字段并保留用户输入；禁用态降低权重但保持可读。

### Navigation

桌面侧栏始终显示图标与文字，当前项使用青雾背景和可信青文字。窄屏重排为五项顶部导航，保持相同信息架构与 DOM 顺序，不隐藏核心入口。

### Trusted Journey

四步可信流程用数字/完成标记、连线、标题和说明共同表达进度。不可执行的未来步骤保持可见但不可操作；当前步骤使用 `aria-current` 和明确文本，不依赖颜色判断。

## Do's and Don'ts

### Do:

- **Do** 将状态、证据来源、口径和下一步放在同一决策上下文中。
- **Do** 复用语义颜色、角色字体、流式间距和容器查询。
- **Do** 为键盘焦点、长文本、双语扩展、错误恢复和缩放保留空间。
- **Do** 用一个主操作配合最多两到三个次要选择控制认知负担。

### Don't:

- **Don't** 把工作台做成营销大屏、装饰性渐变或等权卡片墙。
- **Don't** 用图标、颜色、hover 或缩写独自承担关键信息。
- **Don't** 为单个页面创造新的青色、圆角、阴影或字体角色。
- **Don't** 在小窗口隐藏核心能力；应重排，低于正式下限后再整体缩放。
