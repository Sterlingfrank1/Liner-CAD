# 版本发布与打标签

> 每个版本收尾时按本文件执行。目的：**任何历史版本都能一键定位、对比和回滚**。
> 相关：`docs/ROADMAP.md` §2 生命周期里的 “HANDOVER + tag”；质量门禁 G5 / G6。

## 1. 命名约定

| 类型 | 形式 | 例子 | 说明 |
|---|---|---|---|
| 版本 tag | `vMAJOR.MINOR.PATCH` | `v0.1.0`、`v0.1.1` | **每个版本必须有**；annotated tag；打 tag 的同时建 GitHub Release |
| 预发布 tag | `vMAJOR.MINOR.PATCH-rcN` | `v0.2.0-rc1` | 自动标为 pre-release；同一版本号只发一次正式版 |
| 里程碑 tag | `vMAJOR.MINOR-mN` | `v0.1-m3` | 可选，只标里程碑验收点，**不替代**版本 tag |

硬约束：

- **tag 与 `pyproject.toml` 的 `version` 必须一致**。`scripts/release.ps1` 会先校验，不一致直接拒绝发布。
- tag 一律用 annotated：`git tag -a <tag> -m "..."`，消息写 `vX.Y.Z — <一句话>（见 docs/releases/vX.Y.Z.md）`。
- **已推送的 tag 不可删除、不可移动**（ruleset `protect-version-tags` 保护 `refs/tags/v*`）。发布后发现错误只能发新版本（patch）。
- tag 只从 `main` 打，且打之前 `main` 必须 CI 全绿——CI 不在 tag 上跑，只跑 PR 和 push main。

## 2. 版本收尾检查单

1. 版本内容完成：`main` CI 全绿，G5 验收证据在 `docs/milestones/.../evidence/`，HANDOVER 已合并。
2. 改 `pyproject.toml` 的 `version`（如 `0.1.0` → `0.1.1`）。
3. 写 `docs/releases/vX.Y.Z.md`：范围、里程碑交付、安装、质量与证据、已知缺口、与上一版本的差异。
4. 更新 `docs/ROADMAP.md` 看板：状态、tag 列。
5. 开 PR（分支 `mN/release-vX.Y.Z`），CI 全绿后 squash 合并。
6. 在 `main` 上跑 `pwsh scripts/release.ps1 X.Y.Z`：脚本会再校验一遍（分支/工作区/同步/版本号/发布说明/tag 未被占用/main CI 全绿），然后打 annotated tag、推送、建 GitHub Release。先加 `-DryRun` 可以只看计划。
7. 到 <https://github.com/Sterlingfrank1/Liner-CAD/releases> 核对标题、说明、是不是 Latest。

## 3. 命令

首选脚本（校验项全过才会动手）：

```powershell
git switch main
git pull --ff-only
uv run pytest -q ; uv run ruff check      # 最后一次本地确认
pwsh scripts/release.ps1 0.1.1 -DryRun    # 只看计划
pwsh scripts/release.ps1 0.1.1            # 打 tag + 推送 + 建 Release
```

手工等价操作（脚本不可用时）：

```powershell
git tag -a v0.1.1 -m "v0.1.1 — 见 docs/releases/v0.1.1.md"
git push origin v0.1.1
gh release create v0.1.1 --verify-tag --title "Liner-CAD v0.1.1" --notes-file docs/releases/v0.1.1.md
```

预发布：

```powershell
pwsh scripts/release.ps1 0.2.0-rc1        # 自动加 --prerelease
```

## 4. 查看与回滚

```powershell
git tag -n --sort=-creatordate           # 所有 tag + 消息
gh release list                          # GitHub 上的版本与 Latest
git log --oneline v0.1.0..v0.1.1         # 两个版本之间的提交
git diff --stat v0.1.0 v0.1.1            # 两个版本之间的文件差异
git switch --detach v0.1.0               # 只看/复现某个版本（不建分支）
git switch -c hotfix/0.1.x v0.1.0        # 从旧版本开修复分支
```

回滚原则：**不 force push main、不改旧 tag**。线上回滚 = 从旧 tag 拉 hotfix 分支、走 PR 修、发新的 patch 版本（`v0.1.2`），让历史保持线性可读。

## 5. 当前 tag 现状（2026-11-22）

| tag | 类型 | 指向 | 备注 |
|---|---|---|---|
| `v0.1-m0` | annotated | `654117d` | M0 验收 |
| `v0.1-m1` | annotated | `c96daa6` | M1 验收 |
| `v0.1-m2` | annotated | `aec7160` | M2 验收 |
| `v0.1-m3` | **lightweight** | `b250295` | M3 验收；与 m0–m2 不一致（建议补成 annotated） |
| `v0.1.0` | annotated | `8f36cbc` | M3 验收 + 发布说明；**#72 “v0.1.0 人工评审收口” 在其之后**，严格来说 tag 少了 3 个 commit |
| `v0.1.1` | — | 未打 | 开发中，收尾时按第 2 节执行 |
