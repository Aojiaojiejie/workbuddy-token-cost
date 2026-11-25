#Requires -Version 5.1
<#
.SYNOPSIS
    Build the WorkBuddy Token Cost executables, checksums, and release zip.

.DESCRIPTION
    Runs tests and static checks, builds the CLI and GUI with PyInstaller,
    writes SHA256SUMS.txt, and packages a release zip under dist/.

.PARAMETER SkipTests
    Skip pytest and pyflakes (use only when iterating locally).

.PARAMETER CliOnly
    Build only WorkBuddyTokenCost_CLI.exe.

.PARAMETER NoZip
    Do not create the release zip.

.PARAMETER Python
    Path to the Python interpreter to use. Defaults to WORKBUDDY_PYTHON, then
    python/python3/py from PATH, then a WorkBuddy-bundled interpreter.

.EXAMPLE
    .\build.ps1

.EXAMPLE
    .\build.ps1 -SkipTests -CliOnly

.EXAMPLE
    .\build.ps1 -Python C:\Python313\python.exe
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$CliOnly,
    [switch]$NoZip,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Fail {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Test-Python {
    param([string]$Exe)
    if (-not $Exe) { return $false }
    $exists = (Test-Path -LiteralPath $Exe) -or [bool](Get-Command $Exe -ErrorAction SilentlyContinue)
    if (-not $exists) { return $false }
    try {
        & $Exe -c "import sys" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Resolve-Python {
    param([string]$Explicit)
    $candidates = New-Object System.Collections.ArrayList

    if ($Explicit) { [void]$candidates.Add($Explicit) }
    if ($env:WORKBUDDY_PYTHON) { [void]$candidates.Add($env:WORKBUDDY_PYTHON) }

    foreach ($name in @("python", "python3", "py")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { [void]$candidates.Add($command.Source) }
    }

    $bundled = Join-Path $env:USERPROFILE ".workbuddy\binaries\python\current\python.exe"
    if (Test-Path $bundled) { [void]$candidates.Add($bundled) }
    $versions = Join-Path $env:USERPROFILE ".workbuddy\binaries\python\versions"
    if (Test-Path $versions) {
        Get-ChildItem -Path $versions -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $exe = Join-Path $_.FullName "python.exe"
                if (Test-Path -LiteralPath $exe) { [void]$candidates.Add($exe) }
            }
    }

    foreach ($candidate in $candidates) {
        if (Test-Python $candidate) { return $candidate }
    }
    return $null
}

$python = Resolve-Python -Explicit $Python
if (-not $python) {
    Fail "No working Python 3.10+ found. Pass -Python <path> or set WORKBUDDY_PYTHON."
}
Write-Host "Using Python: $python" -ForegroundColor DarkGray

if (-not $SkipTests) {
    Write-Step "Running tests"
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { Fail "pytest failed." }

    Write-Step "Running pyflakes"
    & $python -m pyflakes token_cost.py gui_app.py scripts tests
    if ($LASTEXITCODE -ne 0) { Fail "pyflakes reported issues." }
}

Write-Step "Building CLI"
& $python -m PyInstaller --noconfirm --clean WorkBuddyTokenCost_CLI.spec
if ($LASTEXITCODE -ne 0) { Fail "CLI build failed." }
if (-not (Test-Path "dist\WorkBuddyTokenCost_CLI.exe")) {
    Fail "dist\WorkBuddyTokenCost_CLI.exe was not produced."
}

if (-not $CliOnly) {
    Write-Step "Building GUI"
    & $python -m PyInstaller --noconfirm --clean WorkBuddyTokenCost.spec
    if ($LASTEXITCODE -ne 0) { Fail "GUI build failed." }
    if (-not (Test-Path "dist\WorkBuddyTokenCost.exe")) {
        Fail "dist\WorkBuddyTokenCost.exe was not produced."
    }
}

Write-Step "Writing checksums"
Copy-Item -LiteralPath "LICENSE" -Destination "dist\LICENSE" -Force

$exes = @()
if (Test-Path "dist\WorkBuddyTokenCost.exe") { $exes += Get-Item "dist\WorkBuddyTokenCost.exe" }
$exes += Get-Item "dist\WorkBuddyTokenCost_CLI.exe"

$lines = foreach ($file in $exes) {
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    "$hash  $($file.Name)"
}
Set-Content -LiteralPath "dist\SHA256SUMS.txt" -Value $lines -Encoding ASCII

if ($NoZip) {
    Write-Step "Done (zip skipped)"
    $exes | ForEach-Object { Write-Host ("  {0}  {1:N1} MB" -f $_.Name, ($_.Length / 1MB)) }
    exit 0
}

if ($CliOnly) {
    Write-Step "Done (CLI only, zip skipped)"
    exit 0
}

Write-Step "Packaging release zip"
$productVersion = (Get-Item "dist\WorkBuddyTokenCost.exe").VersionInfo.ProductVersion
if ($productVersion -match '^(\d+\.\d+\.\d+)') {
    $shortVersion = $matches[1]
}
else {
    $shortVersion = "0.0.0"
}

$stage = Join-Path $PSScriptRoot "build\package"
if (Test-Path $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Path $stage -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stage "installer") -Force | Out-Null

Copy-Item "dist\WorkBuddyTokenCost.exe" $stage -Force
Copy-Item "dist\WorkBuddyTokenCost_CLI.exe" $stage -Force
Copy-Item "dist\SHA256SUMS.txt" $stage -Force
Copy-Item "LICENSE" $stage -Force
Copy-Item "README.md" $stage -Force
Copy-Item "docs\INSTALL.md" (Join-Path $stage "INSTALL.md") -Force
Copy-Item "installer\*.ps1" (Join-Path $stage "installer") -Force
Copy-Item "installer\*.cmd" (Join-Path $stage "installer") -Force

$zipPath = Join-Path $PSScriptRoot "dist\WorkBuddyTokenCost-$shortVersion-win64.zip"
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Step "Build complete"
Write-Host "  GUI   : dist\WorkBuddyTokenCost.exe"
Write-Host "  CLI   : dist\WorkBuddyTokenCost_CLI.exe"
Write-Host "  Sums  : dist\SHA256SUMS.txt"
Write-Host "  Zip   : $zipPath"
exit 0
