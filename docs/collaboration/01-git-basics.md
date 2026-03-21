# Git 基础操作速查

> 适合对 Git 还不太熟悉的成员。已经会 commit/push/pull/branch 的同学可以直接跳到 [02-GitHub Flow](./02-github-flow.md)。

## 1. 首次设置

### 配置用户信息

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

### 克隆项目到本地

```bash
# SSH 方式（推荐，需配置 SSH Key）
git clone git@github.com:用户名/semantic-transmission.git

# HTTPS 方式
git clone https://github.com/用户名/semantic-transmission.git
```

```bash
cd semantic-transmission
```

## 2. 日常开发流程

### 2.1 创建并切换到新分支

**场景**：开始一个新功能或修复之前，先从 `main` 创建分支。

```bash
# 确保在 main 分支且是最新的
git switch main
git pull

# 创建并切换到新分支
git switch -c feature/my-new-feature
```

> `git switch` 是 Git 2.23+ 推荐的分支切换命令，比 `git checkout` 语义更清晰。旧版写法 `git checkout -b` 也能用。

分支命名参考：`feature/xxx`（功能）、`fix/xxx`（修复）、`docs/xxx`（文档）

### 2.2 查看当前状态

**场景**：想知道哪些文件被修改了、哪些还没提交。

```bash
git status
```

输出示例：
```
On branch feature/my-new-feature
Changes not staged for commit:
  modified:   src/main.py          ← 已修改，未暂存
Untracked files:
  src/new_file.py                  ← 新文件，未跟踪
```

### 2.3 暂存并提交

**场景**：完成了一部分工作，想保存一个提交。

```bash
# 暂存指定文件
git add src/main.py src/new_file.py

# 提交（写清楚做了什么）
git commit -m "feat: 添加新功能的核心逻辑"
```

> 本项目的 commit message 遵循 Angular 规范，详见 [05-项目协作约定](./05-project-conventions.md)。

### 2.4 推送到远程

**场景**：把本地的提交同步到 GitHub。

```bash
# 首次推送新分支（-u 建立跟踪关系）
git push -u origin feature/my-new-feature

# 后续推送
git push
```

### 2.5 拉取最新代码

**场景**：同步远程仓库的最新变更。

```bash
# 拉取当前分支的更新
git pull

# 拉取 main 分支最新代码并合并到当前分支
git switch main
git pull
git switch feature/my-new-feature
git merge main
```

## 3. 常见场景

### 3.1 切换分支

```bash
# 查看所有分支
git branch -a

# 切换到已有分支
git switch feature/other-branch

# 切换到远程分支（本地不存在时）
git switch -c feature/other-branch origin/feature/other-branch
```

> 切换前确保当前分支的修改已提交或暂存，否则会报错。

### 3.2 撤销修改

```bash
# 撤销工作区的修改（未 add 的文件，恢复到上次提交的状态）
git restore src/main.py

# 撤销暂存（已 add 但未 commit，把文件从暂存区移出）
git restore --staged src/main.py

# 撤销最近一次提交（保留修改在工作区）
git reset --soft HEAD~1
```

### 3.3 暂存工作进度（stash）

**场景**：正在开发，但需要临时切到别的分支处理事情。

```bash
# 保存当前修改
git stash

# 切换到别的分支处理
git switch main
# ...处理完毕...

# 切回来，恢复之前的修改
git switch feature/my-new-feature
git stash pop
```

### 3.4 解决合并冲突

**场景**：合并或拉取时，两个人修改了同一个文件的同一位置。

```bash
git merge main
# 输出：CONFLICT (content): Merge conflict in src/main.py
```

打开冲突文件，会看到：
```
<<<<<<< HEAD
你的代码
=======
别人的代码
>>>>>>> main
```

**解决步骤**：
1. 手动编辑文件，保留正确的代码，删除 `<<<<<<`、`======`、`>>>>>>` 标记
2. 暂存并提交：
   ```bash
   git add src/main.py
   git commit -m "fix: 解决合并冲突"
   ```

### 3.5 查看历史

```bash
# 查看提交历史
git log --oneline -10

# 查看某个文件的修改历史
git log --oneline src/main.py

# 查看某次提交的具体改动
git show abc1234
```

## 4. 速查表

| 操作 | 命令 |
|------|------|
| 克隆仓库 | `git clone <url>` |
| 创建分支 | `git switch -c <branch>` |
| 切换分支 | `git switch <branch>` |
| 查看状态 | `git status` |
| 暂存文件 | `git add <file>` |
| 提交 | `git commit -m "msg"` |
| 推送 | `git push` |
| 拉取 | `git pull` |
| 查看日志 | `git log --oneline` |
| 暂存进度 | `git stash` / `git stash pop` |
| 撤销修改 | `git restore <file>` |
| 查看分支 | `git branch -a` |
