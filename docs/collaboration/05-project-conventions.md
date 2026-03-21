# 本项目协作约定

## 一、分支命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能开发 | `feature/vlm-integration` |
| `fix/` | Bug 修复 | `fix/receiver-timeout` |
| `docs/` | 文档更新 | `docs/add-collaboration-guide` |
| `refactor/` | 代码重构 | `refactor/api-client` |
| `test/` | 测试相关 | `test/add-sender-tests` |

命名要求：
- 使用英文小写 + 短横线连接
- 简短但能说明目的
- 如关联任务编号，可加上：`feature/P2-13-vlm-integration`

## 二、Commit Message 规范

本项目采用 **Angular Commit Message Convention**，Subject 和 Body 使用中文。

### 格式

```
<type>(<scope>): <subject>

<body>（可选）
```

### type 类型

| type | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(P2-13): 实现 VLM 图像描述生成` |
| `fix` | Bug 修复 | `fix(P2-09): 修复接收端参数传递错误` |
| `docs` | 文档更新 | `docs: 添加团队协作文档` |
| `refactor` | 重构（不改变功能） | `refactor: 重构 ComfyUI API 客户端` |
| `test` | 测试相关 | `test: 添加发送端工作流单元测试` |
| `chore` | 构建/工具变更 | `chore: 更新 pyproject.toml 依赖` |
| `style` | 代码格式调整 | `style: 统一缩进格式` |

### scope（可选）

- 使用任务编号：`P2-13`、`P2-09`
- 或使用模块名：`api`、`vlm`、`config`

### 示例

```bash
# 简单提交
git commit -m "feat(P2-13): 实现 VLM 图像描述生成"

# 带详细说明
git commit -m "fix(P2-09): 修复接收端工作流超时问题

将 WebSocket 超时时间从 30s 调整为 120s，
适配大尺寸图像的生成耗时"
```

## 三、PR 合并策略

建议使用 **Squash and merge**：

- 将功能分支的多个 commit 合并为一个提交进入 `main`
- 保持 `main` 分支历史简洁，每个合并对应一个完整的功能/修复
- 合并时可以编辑最终的 commit message

在仓库 Settings → General → Pull Requests 中，可以设置默认合并方式。

## 四、分支保护规则建议

对 `main` 分支设置保护，在 Settings → Branches → Add branch protection rule 中配置：

| 规则 | 建议设置 | 说明 |
|------|----------|------|
| **Require a pull request before merging** | 开启 | 禁止直接 push 到 main |
| **Require approvals** | 1 人 | 至少 1 人 approve 才能合并 |
| **Require status checks to pass** | 按需 | 如果配置了 CI，合并前需测试通过 |
| **Include administrators** | 建议开启 | 管理员也遵守规则 |

> 团队 2-3 人时，1 人 approve 即可，不需要太复杂的流程。

## 五、代码规范

### 工具链

| 工具 | 用途 | 命令 |
|------|------|------|
| **uv** | 包管理 | `uv add <pkg>`、`uv sync` |
| **ruff** | 代码检查和格式化 | `ruff check .`、`ruff format .` |
| **pytest** | 测试 | `uv run pytest tests/` |

### 提交前自检

```bash
# 代码格式化
uv run ruff format .

# 代码检查
uv run ruff check .

# 运行测试
uv run pytest tests/
```

## 六、协作流程总览

```mermaid
graph TD
    A[查看 Issue / TASK_STATUS.md] --> B[认领任务]
    B --> C[创建功能分支]
    C --> D[开发 + 本地测试]
    D --> E[ruff check + pytest]
    E --> F[Push + 创建 PR]
    F --> G[Code Review]
    G --> H{通过?}
    H -->|是| I[Squash Merge]
    H -->|否| J[根据反馈修改]
    J --> E
    I --> K[关闭 Issue]
    K --> L[更新 TASK_STATUS.md]
```

## 七、与现有工作流系统的配合

本项目使用 `docs/workflow/` 下的结构化工作流进行阶段管理：

- **TASK_STATUS.md**：记录整体任务进度和阶段状态
- **TASK_PLAN.md**：详细的任务规格说明

### 建议配合方式

1. **规划阶段**：在 TASK_PLAN.md 中定义任务规格
2. **执行阶段**：为每个任务创建 GitHub Issue，指派负责人
3. **开发阶段**：基于 Issue 创建分支和 PR
4. **完成阶段**：PR 合并后，更新 TASK_STATUS.md 中的状态
