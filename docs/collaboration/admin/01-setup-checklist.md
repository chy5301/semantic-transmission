# 多人协作配置清单

本文档是管理员将仓库从单人开发切换到多人协作的完整操作清单。

## 配置顺序

```mermaid
graph TD
    A[1. 邀请协作者] --> B[2. 提交模板和 CI 配置文件]
    B --> C[3. 等待 CI 首次运行完成]
    C --> D[4. 初始化 Labels]
    D --> E[5. 设置合并策略]
    E --> F[6. 创建分支保护规则]
    F --> G[7. 创建 Milestones]
    G --> H[8. 验证全流程]
```

## 操作清单

### 第一步：邀请协作者
> 详见 [02-成员管理](./02-collaborator-management.md)

- [ ] 在 Settings → Collaborators 中邀请团队成员
- [ ] 为成员分配合适的权限（开发者建议 Write）
- [ ] 确认成员已接受邀请并能访问仓库

### 第二步：提交配置文件到仓库
> 项目已创建以下配置文件，提交并推送即可生效

- [ ] `.github/pull_request_template.md` — PR 描述模板
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md` — Bug 报告模板
- [ ] `.github/ISSUE_TEMPLATE/feature_request.md` — 功能需求模板
- [ ] `.github/workflows/ci.yml` — CI 工作流

提交所有新增的配置文件和文档后推送即可。

### 第三步：等待 CI 首次运行
> 详见 [05-CI 配置](./05-ci-setup.md)

- [ ] 推送后进入 Actions 页面确认 CI 运行成功
- [ ] 如果 CI 失败，根据日志修复后重新推送

### 第四步：初始化 Labels
> 详见 [04-模板与标签](./04-templates-and-labels.md)

- [ ] 运行 Labels 初始化脚本

### 第五步：设置合并策略
> 详见 [03-仓库设置](./03-repo-settings.md#二合并策略设置)

- [ ] Settings → General → Pull Requests：默认 Squash merge
- [ ] 开启 "Automatically delete head branches"
- [ ] 开启 "Always suggest updating pull request branches"

### 第六步：创建分支保护规则
> 详见 [03-仓库设置](./03-repo-settings.md#一分支保护规则)

- [ ] Settings → Branches → Add rule → `main`
- [ ] 开启 "Require a pull request before merging"（1 approval）
- [ ] 开启 "Require status checks to pass"（选择 `lint-and-test`）
- [ ] 开启 "Do not allow bypassing the above settings"

### 第七步：创建 Milestones
> 详见 [04-模板与标签](./04-templates-and-labels.md#三milestones-创建)

- [ ] 按项目阶段创建里程碑

### 第八步：验证全流程

- [ ] 让一位成员创建分支 → 修改代码 → 推送 → 创建 PR
- [ ] 确认 PR 模板自动填充
- [ ] 确认 CI 自动运行
- [ ] 确认无法直接 push 到 main
- [ ] 完成 Code Review → 合并 PR
- [ ] 确认分支自动删除
