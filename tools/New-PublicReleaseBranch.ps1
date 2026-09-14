[CmdletBinding()]
param(
    [string]$Remote = 'origin',
    [string]$TargetBranch = 'main',
    [switch]$Push
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    & (Join-Path $PSScriptRoot 'Audit-PublicRelease.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Public-release audit failed.' }

    $remoteUrl = git remote get-url $Remote
    if ($LASTEXITCODE -ne 0 -or -not $remoteUrl) { throw "Remote '$Remote' was not found." }

    $staging = Join-Path $root '.publish-staging'
    if (Test-Path -LiteralPath $staging) {
        throw "Staging folder already exists: $staging. Review and remove it before creating another public release."
    }
    New-Item -ItemType Directory -Path $staging | Out-Null
    $files = @(git ls-files --cached --others --exclude-standard | Where-Object {
        $_ -and (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf)
    })
    foreach ($relativePath in $files) {
        $destination = Join-Path $staging $relativePath
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $root $relativePath) -Destination $destination
    }

    git -C $staging init --initial-branch $TargetBranch
    git -C $staging add --all
    git -C $staging -c user.name='KAIROS Contributors' -c user.email='kairos@example.test' commit -m 'Public sanitized release'
    git -C $staging remote add $Remote $remoteUrl
    Write-Host "Created audited one-commit release at $staging."

    if (-not $Push) {
        Write-Host "Review it, then re-run with -Push to publish $TargetBranch."
        exit 0
    }
    $answer = Read-Host "Push this sanitized release to $Remote/$TargetBranch using --force-with-lease? Type PUSH to continue"
    if ($answer -ne 'PUSH') {
        Write-Host 'Push cancelled. The staged release remains available for review.'
        exit 0
    }
    git -C $staging push $Remote "HEAD:refs/heads/$TargetBranch" --force-with-lease
} finally {
    Pop-Location
}
