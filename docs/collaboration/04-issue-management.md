# Issue 任务管理

## Issue 是什么

Issue 是 GitHub 内置的任务跟踪系统。可以用来：
- 报告 Bug
- 提出功能需求
- 记录待办任务
- 讨论技术方案

每个 Issue 有唯一编号（如 `#1`、`#12`），可以在 commit 和 PR 中引用。

## 一、创建 Issue

### 网页端创建

1. 进入仓库页面，点击 "Issues" 标签
2. 点击 "New issue"
3. 填写标题和描述
4. 在右侧面板设置：
   - **Assignees**：指派给谁处理
   - **Labels**：打标签分类
   - **Milestone**：关联里程碑（可选）
5. 点击 "Submit new issue"

### 命令行创建（gh CLI）

```bash
# 基本创建
gh issue create --title "Bug: 接收端工作流超时" --body "## 问题描述
调用接收端 ComfyUI 工作流时，超过 60 秒未返回结果。

## 复现步骤
1. 运行 demo 脚本
2. 等待接收端响应

## 预期行为
应在 30 秒内返回生成结果"

# 带标签和指派
gh issue create --title "标题" --body "描述" --label "bug" --assignee "@me"
```

### Issue 描述要素

> 项目已配置 Issue 模板（`.github/ISSUE_TEMPLATE/`），创建 Issue 时会显示模板选择界面，包含 Bug 报告和功能需求两种模板。详见 [管理员文档 - 模板与标签](./admin/04-templates-and-labels.md)。

## 二、Labels（标签）

Labels 用于分类和筛选 Issue。建议使用以下标签：

| 标签 | 颜色建议 | 用途 |
|------|----------|------|
| `bug` | 红色 | 缺陷报告 |
| `enhancement` | 蓝色 | 功能增强 |
| `documentation` | 绿色 | 文档相关 |
| `question` | 紫色 | 需要讨论的问题 |
| `priority: high` | 橙色 | 高优先级 |
| `priority: low` | 灰色 | 低优先级 |

### 管理标签

```bash
# 查看现有标签
gh label list

# 创建标签
gh label create "priority: high" --color "FF6600" --description "高优先级任务"
```

## 三、Milestones（里程碑）

Milestone 用于按阶段组织 Issue，追踪整体进度。

**示例**：为本项目的各阶段创建里程碑

Milestone 目前没有 `gh` 直接子命令，推荐在网页端操作：

1. 进入仓库 → Issues → Milestones → New milestone
2. 填写标题（如 "Phase 1: 工作流拆分与语义压缩"）、描述和截止日期
3. 创建后，在 Issue 右侧面板选择对应 Milestone 进行关联

在 Issues 页面可以按 Milestone 筛选，查看该阶段的完成进度。

## 四、Issue 与 PR 的关联

### 在 PR 中关闭 Issue

在 PR 描述中使用关键词，PR 合并时会自动关闭对应 Issue：

```markdown
Closes #12
Fixes #5
Resolves #8
```

也可以同时关闭多个：
```markdown
Closes #12, Closes #13
```

### 在 commit 中引用 Issue

```bash
git commit -m "feat(P2-13): 实现 VLM 描述生成 (#5)"
```

`#5` 会自动变成可点击的链接，方便追溯。

## 五、常用 gh CLI 命令

```bash
# 查看 Issue 列表
gh issue list

# 按标签筛选
gh issue list --label "bug"

# 查看 Issue 详情
gh issue view 5

# 在浏览器中打开
gh issue view 5 --web

# 关闭 Issue
gh issue close 5

# 给 Issue 添加评论
gh issue comment 5 --body "已定位问题，正在修复"
```

## 六、Issue vs 本项目的 TASK_STATUS.md

本项目已有 `docs/workflow/TASK_STATUS.md` 进行任务跟踪。两者的关系：

| | GitHub Issue | TASK_STATUS.md |
|---|---|---|
| 适合场景 | Bug 报告、功能需求、跨任务讨论 | 结构化的阶段任务管理 |
| 可见性 | GitHub 页面可查看，支持筛选和通知 | 需要打开文件查看 |
| 关联能力 | 与 PR 自动关联 | 手动记录 |
| 建议用法 | 日常协作中的新需求和问题 | 已规划的阶段性任务 |

建议：**TASK_STATUS.md 中的大任务可以拆分为多个 GitHub Issue**，便于分配和追踪。
