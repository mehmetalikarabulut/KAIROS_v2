[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Add-Finding {
    param([string]$Path, [string]$Reason)
    $script:findings.Add([pscustomobject]@{ Path = $Path; Reason = $Reason })
}

function Test-TextForPrivateData {
    param([string]$Path, [string]$DisplayPath = $Path)

    $content = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $emails = [regex]::Matches($content, '(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b')
    foreach ($email in $emails) {
        if ($email.Value -notmatch '(?i)@example\.test$') {
            Add-Finding $DisplayPath "Non-synthetic email address: $($email.Value)"
        }
    }
    if ($content -match '(?<![\d.])(?:\+\d{1,3}[\s.-]|\(?0\d{2,4}\)?[\s.-])\d{2,4}[\s.-]\d{2,4}(?!\d)') {
        Add-Finding $DisplayPath 'Possible phone number'
    }
    if ($content -match '(?i)\b(?:student.?id|personnel.?id|national.?id|identity.?number|passport.?number)\b') {
        Add-Finding $DisplayPath 'Identifier-related field or value'
    }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git is required for the public-release audit.'
    }

    $script:findings = [System.Collections.Generic.List[object]]::new()
    $paths = @(git ls-files --cached --others --exclude-standard | Where-Object {
        $_ -and (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf)
    })
    $allowedBinaryPaths = @(
        'assets/favicon.png', 'assets/logo.png', 'assets/icon.svg', 'assets/logo.svg',
        'assets/kairos_input_template.xlsx',
        'src/timetabling/assets/fonts/DejaVuSans.ttf',
        'src/timetabling/assets/fonts/DejaVuSans-Bold.ttf'
    )
    $textExtensions = @('.py', '.ps1', '.md', '.txt', '.toml', '.yaml', '.yml', '.json', '.csv', '.svg', '.css', '.bat', '.dockerignore', '.gitignore')
    $textFileNames = @('LICENSE', 'Dockerfile')

    foreach ($relativePath in $paths) {
        $normalizedPath = $relativePath.Replace('\', '/')
        $fullPath = Join-Path $root $relativePath
        $extension = [IO.Path]::GetExtension($fullPath).ToLowerInvariant()

        if ($extension -in @('.pdf', '.jpg', '.jpeg', '.webp', '.mp4', '.mov')) {
            Add-Finding $normalizedPath "Disallowed publishable asset type: $extension"
        } elseif ($extension -eq '.xlsx') {
            if ($normalizedPath -notin $allowedBinaryPaths) {
                Add-Finding $normalizedPath 'Workbook is not in the public asset allowlist'
                continue
            }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $archive = [IO.Compression.ZipFile]::OpenRead($fullPath)
            try {
                foreach ($entry in $archive.Entries | Where-Object { $_.FullName -match '^xl/(sharedStrings|worksheets)/.*\.xml$' }) {
                    $reader = [IO.StreamReader]::new($entry.Open())
                    $temporaryPath = Join-Path $env:TEMP ('kairos-xlsx-audit-' + [guid]::NewGuid().ToString() + '.txt')
                    try {
                        [IO.File]::WriteAllText($temporaryPath, $reader.ReadToEnd())
                        Test-TextForPrivateData $temporaryPath $normalizedPath
                    } finally {
                        $reader.Dispose()
                        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
                    }
                }
            } finally {
                $archive.Dispose()
            }
        } elseif ($extension -in $textExtensions -or [IO.Path]::GetFileName($fullPath) -in $textFileNames) {
            Test-TextForPrivateData $fullPath $normalizedPath
        } elseif ($normalizedPath -notin $allowedBinaryPaths) {
            Add-Finding $normalizedPath 'Unknown binary or unapproved file type'
        }
    }

    if ($findings.Count) {
        Write-Error ('Public-release audit failed:' + [Environment]::NewLine + (($findings | ForEach-Object { " - $($_.Path): $($_.Reason)" }) -join [Environment]::NewLine))
        exit 1
    }
    Write-Host "Public-release audit passed: $($paths.Count) publishable files checked."
} finally {
    Pop-Location
}
