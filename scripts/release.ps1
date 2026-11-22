#!/usr/bin/env pwsh
<#
.SYNOPSIS
    给 Liner-CAD 打版本 tag 并创建 GitHub Release。

.DESCRIPTION
    一个版本收尾时执行：校验 -> 打 annotated tag -> 推送 -> 建 Release。
    校验项：在 main、工作区干净、与 origin/main 同步、pyproject 版本一致、
    docs/releases/<tag>.md 存在、tag 未被占用、main 最新 CI 全绿。

.PARAMETER Version
    版本号，带不带 v 都行：0.1.1 / v0.1.1。

.PARAMETER DryRun
    只做校验并打印将要执行的命令，不改仓库、不推送。

.EXAMPLE
    pwsh scripts/release.ps1 0.1.1 -DryRun

.EXAMPLE
    pwsh scripts/release.ps1 v0.1.1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    Write-Host "X $Message" -ForegroundColor Red
    exit 1
}

function Step([string]$Message) {
    Write-Host "> $Message" -ForegroundColor Cyan
}

$tag = if ($Version.StartsWith('v')) { $Version } else { "v$Version" }
$semver = $tag.Substring(1)

$root = (git rev-parse --show-toplevel).Trim()
Set-Location $root

# 1. 分支、工作区、与远端一致
Step "检查分支与工作区"
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne 'main') { Fail "当前在 $branch，先切到 main 并完成版本 PR 的合并" }
if (git status --porcelain) { Fail "工作区不干净，先提交或 stash" }

git fetch origin --quiet 2>$null
$local = (git rev-parse HEAD).Trim()
$remote = (git rev-parse origin/main).Trim()
if ($local -ne $remote) { Fail "本地 main 与 origin/main 不一致，先 git pull --ff-only" }

# 2. pyproject 版本号必须一致
Step "检查 pyproject.toml 版本号"
$pyproject = Get-Content (Join-Path $root 'pyproject.toml') -Raw -Encoding utf8
if ($pyproject -notmatch '(?m)^version\s*=\s*"([^"]+)"') { Fail "读不到 pyproject.toml 的 version" }
$pyVersion = $Matches[1]
if ($pyVersion -ne $semver) {
    Fail "pyproject version=$pyVersion 与 tag $tag 不一致；先改版本号、合并，再发布"
}

# 3. 发布说明必须存在
Step "检查发布说明"
$notes = Join-Path $root "docs/releases/$tag.md"
if (-not (Test-Path $notes)) { Fail "缺少发布说明 docs/releases/$tag.md" }

# 4. tag 不能被占用
Step "检查 tag 是否已存在"
if (git rev-parse -q --verify "refs/tags/$tag" 2>$null) { Fail "本地已存在 tag $tag" }
if ((git ls-remote --tags origin "refs/tags/$tag") -match '\S') { Fail "远端已存在 tag $tag" }

# 5. main 最新 CI 必须全绿
Step "检查 main 最新 CI"
$run = gh run list --branch main --workflow CI --limit 1 --json headSha,status,conclusion |
    ConvertFrom-Json | Select-Object -First 1
if (-not $run) { Fail "查不到 main 的 CI 记录" }
if ($run.headSha -ne $local) {
    Fail "main 最新 CI 停在 $($run.headSha.Substring(0, 7))，不是当前 commit；等它跑完再发布"
}
if ($run.status -ne 'completed' -or $run.conclusion -ne 'success') {
    Fail "main 最新 CI 未通过：$($run.status)/$($run.conclusion)"
}

$message = "$tag — 见 docs/releases/$tag.md"
$releaseArgs = @('release', 'create', $tag, '--title', "Liner-CAD $tag", '--notes-file', $notes, '--verify-tag')
if ($semver -match '-(rc|beta|alpha)\.\d+$') { $releaseArgs += '--prerelease' }

Step "计划"
Write-Host "  tag      : $tag ($local)"
Write-Host "  version  : $pyVersion"
Write-Host "  notes    : docs/releases/$tag.md"
Write-Host "  commands : git tag -a $tag -m '$message'; git push origin $tag; gh $($releaseArgs -join ' ')"

if ($DryRun) {
    Write-Host ""
    Write-Host "DryRun：未做任何改动。" -ForegroundColor Yellow
    exit 0
}

# 6. 打 tag、推送、建 Release
Step "创建 annotated tag"
git tag -a $tag -m $message
if ($LASTEXITCODE -ne 0) { Fail "git tag 失败" }

Step "推送 tag"
git push origin $tag
if ($LASTEXITCODE -ne 0) { Fail "推送 tag 失败（远端已存在？）" }

Step "创建 GitHub Release"
$url = gh @releaseArgs
if ($LASTEXITCODE -ne 0) { Fail "gh release create 失败" }

Write-Host ""
Write-Host "完成：$tag -> $url" -ForegroundColor Green
