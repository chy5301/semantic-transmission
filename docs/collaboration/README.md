# 团队协作指南

本目录包含语义传输项目的多人协作文档，帮助团队快速上手 Git + GitHub 协作流程。

## 文档索引

| 文档 | 内容 | 适合谁 |
|------|------|--------|
| [01-Git 基础操作](./01-git-basics.md) | clone、branch、commit、push 等命令速查 | Git 不太熟悉的成员 |
| [02-GitHub Flow](./02-github-flow.md) | 分支协作的完整流程（从创建分支到合并 PR） | 所有成员 |
| [03-PR 与 Code Review](./03-pull-request-guide.md) | 如何创建 PR、如何做代码审查 | 所有成员 |
| [04-Issue 管理](./04-issue-management.md) | 用 Issue 跟踪 Bug、需求和任务 | 所有成员 |
| [05-项目协作约定](./05-project-conventions.md) | 本项目的分支命名、Commit 规范、工具链等 | 所有成员 |

## 管理员文档

> 适合仓库管理员，用于配置多人协作所需的 GitHub 设置。

| 文档 | 内容 |
|------|------|
| [配置总清单](./admin/01-setup-checklist.md) | 从单人到多人协作的完整配置步骤（按顺序勾选） |
| [成员管理](./admin/02-collaborator-management.md) | 邀请协作者、权限分配、成员入职清单 |
| [仓库设置](./admin/03-repo-settings.md) | 分支保护规则、合并策略配置 |
| [模板与标签](./admin/04-templates-and-labels.md) | PR/Issue 模板说明、Labels 初始化脚本 |
| [CI 配置](./admin/05-ci-setup.md) | GitHub Actions 工作流说明、CI 失败排查 |

## 建议阅读路线

**Git 基础不太熟悉**：01 → 02 → 03 → 05 → 04

**已经会 Git 基础操作**：02 → 03 → 05 → 04

## 官方学习资源

### GitHub 官方文档（支持中文）

> 以下链接的 `/en/` 可替换为 `/zh/` 查看中文版。

- [GitHub Flow](https://docs.github.com/zh/get-started/using-github/github-flow) — GitHub 推荐的协作工作流
- [Pull Request 文档](https://docs.github.com/zh/pull-requests) — PR 的完整使用指南
- [Code Review 文档](https://docs.github.com/zh/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests) — 代码审查操作指南
- [Issues 文档](https://docs.github.com/zh/issues) — Issue 功能完整文档
- [Projects 项目管理](https://docs.github.com/zh/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) — 看板式项目管理
- [分支保护规则](https://docs.github.com/zh/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) — 受保护分支配置
- [组织最佳实践](https://docs.github.com/zh/organizations/collaborating-with-groups-in-organizations/best-practices-for-organizations) — 团队组织管理

### 交互式学习

- [GitHub Skills](https://skills.github.com/) — 官方免费交互式课程，在真实仓库中练习
- [GitHub Learn](https://learn.github.com/) — 个性化学习路径

### 社区中文教程

- [Git 工作流教程（中文）](https://github.com/xirong/my-git/blob/master/git-workflow-tutorial.md) — 详细的 Git 工作流对比
- [GitHub 多人协作开发](https://gist.github.com/belm/6989341) — 简明协作流程总结
- [新手参与代码协作指南](https://gist.github.com/Abirdcfly/b942d4e9d44f3fb71344b92b979c8d40) — 面向新手的详细步骤
