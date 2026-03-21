# 邀请成员与权限管理

## 一、权限级别说明

GitHub 私有仓库的协作者权限：

| 权限 | 能做什么 | 不能做什么 |
|------|----------|------------|
| **Read** | 查看代码、Issue、PR | 不能推送代码 |
| **Write** | 推送代码、管理 Issue/PR、创建分支 | 不能修改仓库设置 |
| **Admin** | 所有权限，包括仓库设置、分支保护、管理协作者 | — |

**本项目建议**：
- 项目负责人：Admin
- 其他开发成员：Write（足够日常开发，不会误改仓库设置）

## 二、邀请协作者

### 方式一：GitHub 网页端

1. 打开仓库页面 → **Settings** → 左侧 **Collaborators**
2. 点击 **Add people**
3. 输入对方的 **GitHub 用户名** 或邮箱
4. 选择权限级别（默认 Write）
5. 点击 **Add \<username\> to this repository**

> 对方会收到邮件邀请，需要点击接受后才能访问仓库。

### 方式二：gh CLI

```bash
# 邀请协作者（默认 Write 权限）
gh api repos/chy5301/semantic-transmission/collaborators/对方用户名 \
  --method PUT \
  -f permission=push

# push = Write 权限，pull = Read 权限，admin = Admin 权限
```

### 成员接受邀请

被邀请的成员需要：
1. 检查邮箱，找到 GitHub 的邀请邮件
2. 点击邮件中的 **Accept invitation** 链接
3. 或直接访问 `https://github.com/chy5301/semantic-transmission/invitations`

接受后即可克隆和推送代码：
```bash
git clone https://github.com/chy5301/semantic-transmission.git
```

## 三、查看和管理现有协作者

### 查看协作者列表

```bash
gh api repos/chy5301/semantic-transmission/collaborators \
  --jq '.[] | "\(.login) - \(.role_name)"'
```

### 变更权限

```bash
# 将成员权限改为 Admin
gh api repos/chy5301/semantic-transmission/collaborators/用户名 \
  --method PUT \
  -f permission=admin
```

### 移除协作者

```bash
gh api repos/chy5301/semantic-transmission/collaborators/用户名 \
  --method DELETE
```

> 移除后对方将无法访问仓库（私有仓库）。操作前请确认。

## 四、成员入职清单

新成员加入后，建议按以下步骤完成入职：

- [ ] 接受仓库邀请
- [ ] 克隆仓库到本地
- [ ] 运行 `uv sync` 安装依赖
- [ ] 阅读 [团队协作指南](../README.md)（根据自身情况选择阅读路线）
- [ ] 尝试创建一个测试分支并推送，验证权限正常
