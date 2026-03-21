# PR/Issue 模板与 Labels 配置

## 一、模板文件说明

项目已在 `.github/` 目录下配置了以下模板：

```
.github/
├── pull_request_template.md      # 创建 PR 时自动填充
└── ISSUE_TEMPLATE/
    ├── bug_report.md             # Bug 报告模板
    └── feature_request.md        # 功能需求模板
```

### PR 模板

文件：`.github/pull_request_template.md`

创建 PR 时，描述栏会自动填充模板内容，包含：
- 改动说明（做了什么、为什么）
- 关联 Issue（`Closes #N`）
- 测试说明（checklist）

团队成员只需按模板填写即可，无需记忆格式。

### Issue 模板

文件：`.github/ISSUE_TEMPLATE/` 目录

创建 Issue 时，GitHub 会显示模板选择界面：
- **Bug 报告**：自动添加 `bug` 标签，包含问题描述、复现步骤、环境信息
- **功能需求**：自动添加 `enhancement` 标签，包含需求描述、方案建议、验收标准

### 自定义模板

直接编辑 `.github/` 下对应的 `.md` 文件即可。Issue 模板的 YAML frontmatter 控制元数据：

```yaml
---
name: 模板名称          # 模板选择界面显示的名称
description: 一句话描述  # 模板选择界面显示的描述
labels: ["bug"]         # 自动添加的标签
---
```

## 二、Labels 初始化

GitHub 新仓库会有一些默认 Labels，但不完全符合本项目需求。运行以下脚本初始化：

```bash
# 删除不需要的默认标签（可选）
gh label delete "good first issue" --yes 2>/dev/null
gh label delete "help wanted" --yes 2>/dev/null
gh label delete "invalid" --yes 2>/dev/null
gh label delete "wontfix" --yes 2>/dev/null
gh label delete "duplicate" --yes 2>/dev/null
gh label delete "question" --yes 2>/dev/null

# 确保核心标签存在（已存在的会跳过）
gh label create "bug" --color "d73a4a" --description "缺陷报告" --force
gh label create "enhancement" --color "0075ca" --description "功能增强" --force
gh label create "documentation" --color "0e8a16" --description "文档相关" --force
gh label create "refactor" --color "d4c5f9" --description "代码重构" --force

# 优先级标签
gh label create "priority: high" --color "FF6600" --description "高优先级" --force
gh label create "priority: low" --color "cccccc" --description "低优先级" --force

# 状态标签
gh label create "blocked" --color "b60205" --description "被阻塞，等待依赖" --force
gh label create "in progress" --color "fbca04" --description "正在处理中" --force
```

> `--force` 参数：标签已存在时更新颜色和描述，不会报错。

### 查看现有标签

```bash
gh label list
```

## 三、Milestones 创建

建议按项目阶段创建里程碑。在网页端操作：

1. 打开仓库 → **Issues** → **Milestones** → **New milestone**
2. 创建以下里程碑：

| 里程碑名称 | 描述 |
|-----------|------|
| Phase 1: 工作流拆分与语义压缩 | P2-05 ~ P2-13 任务 |
| Phase 2: 中继传输与双机演示 | P2-11 ~ P2-12 任务 |
| Phase 3: 质量优化与工程精简 | P2-14 ~ P2-15 任务 |

3. 创建 Issue 时，在右侧面板选择对应 Milestone
4. 在 Milestones 页面可以查看每个阶段的完成进度百分比
