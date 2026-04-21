---
name: x-main-sync
description: |
  将 dev 分支上的代码提交同步到 origin/main 的发布型 skill。只要用户提到“推到 main”“同步到 origin/main”“发布到 main”“把代码提交到 main”“只把代码上 main”“从 dev 发 main”，或场景明显是在 dev 分支上做代码/开发文档双提交后，只希望把代码那条提交送到 main，就必须使用本 skill。
  这个 skill 专门服务于“dev 保留开发文档，main 只收代码”的分支策略：先确认当前工作在 dev，识别 code commit 和 docs commit，只迁移 code commit 到最新 origin/main，保留原始 commit message，不把开发文档和任务记录带进 main。
  如果当前分支不是 dev，或用户要整条 dev 历史合并到 main，或用户要把开发文档也发到 main，本 skill不适用，应先停下并说明原因。
---

# x-main-sync

## 目标

把 `dev` 上刚完成的代码提交安全同步到 `origin/main`，同时满足这几条约束：

1. `dev` 保留代码和开发文档两类提交
2. `main` 只接代码提交
3. 迁移到 `main` 的 commit message 与 `dev` 上对应代码提交保持一致
4. 不把 `.claude/tasks/**`、`docs/**` 这类开发文档和任务记录带进 `main`

## 适用前提

只有在下面条件同时成立时使用本 skill：

1. 当前工作分支是 `dev`
2. 用户目标是同步到 `origin/main`
3. 当前改动已经按“代码提交 / 文档提交”分开提交，或准备由你先分开提交

遇到下面任一情况，停止执行并直接说明：

1. 当前分支不是 `dev`
2. 用户要把整个 `dev` 合并到 `main`
3. 用户明确要把开发文档也同步到 `main`
4. 当前工作树还有未提交改动，且用户还没有让你先提交

## 核心原则

1. 始终以最新 `origin/main` 为落点
2. 只迁移 code commit
3. docs commit 留在 `dev`
4. 对已分叉的 `dev/main`，优先做定向迁移，避免整分支 merge
5. 迁移后的 commit message 保持和 `dev` 上代码提交一致
6. 不强推 `main`，除非用户明确要求

## 标准流程

### 第一步：确认分支和工作树状态

执行并检查：

```powershell
git branch --show-current
git status --short --branch
```

要求：

1. 当前分支必须是 `dev`
2. 工作树应当干净

如果工作树不干净，先判断用户是不是要你先提交。是，就先走提交流程；否则停下说明当前不能直接同步。

### 第二步：识别本次要同步的 code commit

优先来源：

1. 用户刚刚确认过的代码提交 hash
2. 最近两次或最近几次提交里，按仓库规则分离出的 code commit

辅助检查：

```powershell
git log --oneline -5
git show --stat <code-commit>
```

确认该提交只包含代码、脚本、插件元数据、构建配置等应进入 `main` 的内容。

如果最近同时有 docs commit，记录它，但不要把它迁到 `main`。

## 代码 / 文档分类约定

优先使用项目根的 `.commit-separator.json`。在本仓库里：

1. `.claude-plugin/**` 属于代码
2. `skills/**` 属于代码
3. `.claude/tasks/**` 属于文档
4. `docs/**` 属于文档
5. 根目录 `README*.md` 属于文档

对未覆盖路径，按仓库现有规则和实际用途判断。拿不准时先问用户。

### 第三步：拉取最新 origin/main

执行：

```powershell
git fetch origin main
```

然后检查：

```powershell
git log --oneline --left-right dev...origin/main
git cherry -v origin/main dev
```

这一步的目的：

1. 确认 `dev` 和 `main` 是否分叉
2. 识别哪些旧提交已经有等价补丁存在于 `main`
3. 避免把整条 `dev` 历史误推到 `main`

### 第四步：基于 origin/main 创建临时同步分支

推荐分支名：

```text
codex/sync-main
```

执行：

```powershell
git switch -c codex/sync-main origin/main
```

如果分支已存在，先检查它是否干净、是否基于最新 `origin/main`。必要时切换到新的临时分支名，例如：

```text
codex/sync-main-20260421
```

### 第五步：只迁移 code commit

执行：

```powershell
git cherry-pick <code-commit>
```

如果有多个代码提交要发到 `main`，按原始顺序逐个 cherry-pick。

不要 cherry-pick docs commit。

## 冲突处理

发生冲突时：

1. 先看 `origin/main` 当前版本
2. 再看 `dev` 上 code commit 的目标版本
3. 只合并本次代码提交真正要带上的改动
4. 保持 commit message 不变

常见场景：

1. `main` 上同一文件已有后续版本号或说明文案调整
2. `dev` 上代码提交修改了插件元数据，`main` 上也有相邻更新

处理规则：

1. 保留 `main` 上已经存在且与本次任务无关的更新
2. 引入本次 code commit 的目标改动
3. 解决后继续 `git cherry-pick --continue`

### 第六步：推送到 origin/main

先确认临时分支只包含预期代码提交：

```powershell
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD
```

确认无误后执行：

```powershell
git push origin HEAD:main
```

如果用户明确要求使用特定分支名，也可以：

```powershell
git push origin <temp-branch>:main
```

### 第七步：切回 dev

执行：

```powershell
git switch dev
```

保持用户继续在 `dev` 上工作。

## 什么时候选 cherry-pick

对本仓库的 `dev/main` 策略，默认使用 cherry-pick。原因很明确：

1. `dev` 和 `main` 经常分叉
2. 两条线里可能存在“内容等价但 hash 不同”的旧提交
3. `dev` 还会保留开发文档历史

因此同步到 `main` 时，目标是“迁移这次 code commit 的内容”，不是“搬运整条 `dev` 历史”。

## 输出要求

完成后向用户汇报：

1. 哪个 code commit 被同步到 `main`
2. 对应的新 hash 是多少
3. commit message 是否保持一致
4. 是否发生冲突，冲突文件有哪些
5. 当前是否已切回 `dev`

建议格式：

```markdown
已同步到 origin/main。

- dev 上代码提交：<old-hash> <subject>
- main 上对应提交：<new-hash> <subject>
- docs commit：保留在 dev，未同步到 main
- 当前分支：dev
```

## 禁止事项

1. 不把 docs commit 发到 `main`
2. 不直接 merge 整个 `dev` 到 `main`
3. 不在未检查 `origin/main` 最新状态时直接推
4. 不强推 `main`
5. 不把“相同 message”误当成“相同提交”

## 典型触发语句

这些场景都应该触发本 skill：

1. “推送到 origin/main”
2. “把这次代码发到 main”
3. “dev 上的代码同步到 main，文档别带过去”
4. “只把 code commit pick 到 main”
5. “发布到 main，message 保持一样”
