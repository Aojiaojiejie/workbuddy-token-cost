#Requires -Version 5.1
<#
.SYNOPSIS
    Per-user uninstaller for WorkBuddy Token Cost.

.DESCRIPTION
    Removes the installed files, shortcuts, optional PATH entry, and the
    "Apps & features" registration. Refuses to delete directories that do not
    carry the installer marker, so a mistyped path cannot wipe unrelated data.

.PARAMETER InstallDir
    Override the recorded install directory (normally read from the registry).

.PARAMETER Silent
    Do not prompt for confirmation.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1 -Silent
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [switch]$Silent
)

$ErrorActionPreference = "Stop"

$AppId = "WorkBuddyTokenCost"
$AppName = "WorkBuddy Token Cost"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Fail {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Stop-RunningApp {
    foreach ($name in @($AppId, "${AppId}_CLI")) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        if ($procs) {
            $procs | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 300
        }
    }
}

# ---------------------------------------------------------------- resolve install dir
if (-not $InstallDir) {
    if (Test-Path $UninstallKey) {
        $recorded = (Get-ItemProperty -Path $UninstallKey -Name "InstallLocation" -ErrorAction SilentlyContinue).InstallLocation
        if ($recorded) { $InstallDir = $recorded }
    }
}
if (-not $InstallDir) {
    $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$AppId"
}
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\')

# ---------------------------------------------------------------- safety guards
$forbidden = @(
    [System.IO.Path]::GetPathRoot($InstallDir),
    $env:SystemRoot,
    $env:ProgramFiles,
    ${env:ProgramFiles(x86)},
    $env:LOCALAPPDATA,
    $env:APPDATA,
    $env:USERPROFILE
)
foreach ($path in $forbidden) {
    if ($path -and ($InstallDir -ieq ([System.IO.Path]::GetFullPath($path)).TrimEnd('\'))) {
        Fail "Refusing to remove a protected directory: $InstallDir"
    }
}

$marker = Join-Path $InstallDir ".workbuddy-token-cost"
$hasMarker = Test-Path $marker
$hasExe = (Test-Path (Join-Path $InstallDir "WorkBuddyTokenCost.exe")) -or (Test-Path (Join-Path $InstallDir "WorkBuddyTokenCost_CLI.exe"))
# Marker is authoritative; without it, require both our folder name and our exe
# so a mistyped -InstallDir can never wipe an unrelated directory.
$looksLikeOurs = $hasMarker -or (((Split-Path $InstallDir -Leaf) -ieq $AppId) -and $hasExe)
if (-not $looksLikeOurs) {
    Fail "Refusing to remove '$InstallDir': no installer marker or expected executable found."
}

Write-Step "Uninstalling $AppName"
Write-Host "    Directory: $InstallDir"

if (-not $Silent) {
    $answer = Read-Host "Remove $AppName and all shortcuts? [y/N]"
    if ($answer -notmatch '^(y|yes)$') {
        Write-Host "Cancelled."
        exit 0
    }
}

# ---------------------------------------------------------------- stop processes
Stop-RunningApp

# ---------------------------------------------------------------- shortcuts
Write-Step "Removing shortcuts"
$desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
Remove-Item -LiteralPath $desktopLink -Force -ErrorAction SilentlyContinue

$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) $AppId
if (Test-Path $startDir) {
    Remove-Item -LiteralPath $startDir -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------- PATH entry
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath) {
    $entries = @($userPath.Split(';') | Where-Object { $_ -ne "" -and ($_.TrimEnd('\') -ine $InstallDir) })
    $newPath = $entries -join ';'
    if ($newPath -ne $userPath) {
        Write-Step "Removing PATH entry"
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    }
}

# ---------------------------------------------------------------- registry
Write-Step "Removing Apps & features entry"
Remove-Item -LiteralPath $UninstallKey -Recurse -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- files
if (Test-Path $InstallDir) {
    Write-Step "Removing files"
    Set-Location $env:TEMP
    Remove-Item -LiteralPath $InstallDir -Recurse -Force
}
else {
    Write-Host "    Directory already absent."
}

$logPath = Join-Path $env:TEMP "WorkBuddyTokenCost_gui_error.log"
Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Uninstalled $AppName." -ForegroundColor Green
exit 0
