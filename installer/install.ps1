#Requires -Version 5.1
<#
.SYNOPSIS
    Per-user installer for WorkBuddy Token Cost (Windows 10/11, no admin required).

.DESCRIPTION
    Copies the packaged executables into a per-user directory, creates Start Menu
    and Desktop shortcuts, and registers an entry in "Apps & features".
    The installer is intentionally idempotent: running it again upgrades in place.

.PARAMETER SourceDir
    Directory containing WorkBuddyTokenCost.exe and WorkBuddyTokenCost_CLI.exe.
    Defaults to the script directory, then ..\dist, then ..

.PARAMETER InstallDir
    Target directory. Defaults to %LOCALAPPDATA%\Programs\WorkBuddyTokenCost.

.PARAMETER AddToPath
    Append the install directory to the current user's PATH (new terminals only).

.PARAMETER NoShortcuts
    Do not create Desktop or Start Menu shortcuts (portable / CI use).

.PARAMETER Silent
    Do not prompt. Running instances are closed automatically.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Silent -AddToPath
#>
[CmdletBinding()]
param(
    [string]$SourceDir = "",
    [string]$InstallDir = "",
    [switch]$AddToPath,
    [switch]$NoShortcuts,
    [switch]$Silent
)

$ErrorActionPreference = "Stop"

$AppId = "WorkBuddyTokenCost"
$AppName = "WorkBuddy Token Cost"
$Publisher = "Aojiaojiejie"
$GuiExe = "WorkBuddyTokenCost.exe"
$CliExe = "WorkBuddyTokenCost_CLI.exe"
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

# ---------------------------------------------------------------- locate payload
if (-not $SourceDir) {
    $candidates = @(
        $PSScriptRoot,
        (Join-Path $PSScriptRoot "..\dist"),
        (Join-Path $PSScriptRoot "..")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path (Join-Path $candidate $GuiExe)) {
            $SourceDir = (Resolve-Path -LiteralPath $candidate).Path
            break
        }
    }
}

if (-not $SourceDir -or -not (Test-Path (Join-Path $SourceDir $GuiExe))) {
    Fail "Cannot find $GuiExe. Build it first (build.ps1) or pass -SourceDir <folder>."
}
$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path

$guiPath = Join-Path $SourceDir $GuiExe
$cliPath = Join-Path $SourceDir $CliExe
if (-not (Test-Path $cliPath)) {
    Fail "Cannot find $CliExe next to $GuiExe."
}

# ---------------------------------------------------------------- verify checksums
$sumFile = Join-Path $SourceDir "SHA256SUMS.txt"
if (Test-Path $sumFile) {
    Write-Step "Verifying SHA256 checksums"
    foreach ($line in Get-Content -LiteralPath $sumFile) {
        if ($line -match '^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$') {
            $expected = $matches[1].ToUpperInvariant()
            $name = $matches[2]
            $file = Join-Path $SourceDir $name
            if (Test-Path $file) {
                $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToUpperInvariant()
                if ($actual -ne $expected) {
                    Fail "Checksum mismatch for $name. Refusing to install."
                }
            }
        }
    }
}

# ---------------------------------------------------------------- resolve target
if (-not $InstallDir) {
    $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$AppId"
}
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\')

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
        Fail "Refusing to install into a protected directory: $InstallDir"
    }
}

# ---------------------------------------------------------------- version
$productVersion = (Get-Item -LiteralPath $guiPath).VersionInfo.ProductVersion
if (-not $productVersion) {
    $productVersion = "5.0.1.0"
}
$parts = $productVersion.Split('.')
$displayVersion = ($parts[0..([Math]::Min(2, $parts.Length - 1))] -join '.')

Write-Step "Installing $AppName $displayVersion"
Write-Host "    From : $SourceDir"
Write-Host "    To   : $InstallDir"

# ---------------------------------------------------------------- running instances
$running = @()
foreach ($name in @($AppId, "${AppId}_CLI")) {
    $running += @(Get-Process -Name $name -ErrorAction SilentlyContinue)
}
if ($running.Count -gt 0) {
    if ($Silent) {
        Write-Host "    Closing running instances..." -ForegroundColor Yellow
        Stop-RunningApp
    } else {
        $answer = Read-Host "WorkBuddy Token Cost is running. Close it and continue? [y/N]"
        if ($answer -notmatch '^(y|yes)$') {
            Fail "Aborted by user."
        }
        Stop-RunningApp
    }
}

# ---------------------------------------------------------------- copy files
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -LiteralPath $guiPath -Destination (Join-Path $InstallDir $GuiExe) -Force
Copy-Item -LiteralPath $cliPath -Destination (Join-Path $InstallDir $CliExe) -Force

foreach ($scriptName in @("install.ps1", "uninstall.ps1")) {
    $scriptPath = Join-Path $PSScriptRoot $scriptName
    if (Test-Path $scriptPath) {
        Copy-Item -LiteralPath $scriptPath -Destination (Join-Path $InstallDir $scriptName) -Force
    }
}

$licensePath = Join-Path $SourceDir "LICENSE"
if (Test-Path $licensePath) {
    Copy-Item -LiteralPath $licensePath -Destination (Join-Path $InstallDir "LICENSE") -Force
}
else {
    Write-Host "    [WARN] LICENSE not found in payload; MIT redistribution requires it." -ForegroundColor Yellow
}

# Marker used by the uninstaller to prove the directory belongs to this app.
Set-Content -LiteralPath (Join-Path $InstallDir ".workbuddy-token-cost") -Value $displayVersion -Encoding ASCII

# ---------------------------------------------------------------- shortcuts
if (-not $NoShortcuts) {
    Write-Step "Creating shortcuts"
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath("Desktop")
    $programs = [Environment]::GetFolderPath("Programs")
    $startDir = Join-Path $programs $AppId
    New-Item -ItemType Directory -Path $startDir -Force | Out-Null

    $links = @(
        @{ Path = (Join-Path $desktop "$AppName.lnk"); Target = (Join-Path $InstallDir $GuiExe); Args = ""; Desc = "WorkBuddy Token Cost dashboard" },
        @{ Path = (Join-Path $startDir "$AppName.lnk"); Target = (Join-Path $InstallDir $GuiExe); Args = ""; Desc = "WorkBuddy Token Cost dashboard" },
        @{ Path = (Join-Path $startDir "WorkBuddy Token Cost (CLI).lnk"); Target = (Join-Path $InstallDir $CliExe); Args = "--watch"; Desc = "WorkBuddy Token Cost live CLI" }
    )

    foreach ($link in $links) {
        $shortcut = $shell.CreateShortcut($link.Path)
        $shortcut.TargetPath = $link.Target
        $shortcut.Arguments = $link.Args
        $shortcut.WorkingDirectory = $InstallDir
        $shortcut.IconLocation = "$(Join-Path $InstallDir $GuiExe),0"
        $shortcut.Description = $link.Desc
        $shortcut.Save()
    }
}

# ---------------------------------------------------------------- PATH (optional)
if ($AddToPath) {
    Write-Step "Updating user PATH"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $userPath) { $userPath = "" }
    $entries = @($userPath.Split(';') | Where-Object { $_ -ne "" })
    $already = $false
    foreach ($entry in $entries) {
        if ($entry.TrimEnd('\') -ieq $InstallDir) { $already = $true }
    }
    if (-not $already) {
        $newPath = (@($entries) + $InstallDir) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "    Added to PATH (open a new terminal to use it)."
    }
    else {
        Write-Host "    Already present in PATH."
    }
}

# ---------------------------------------------------------------- Apps & features entry
Write-Step "Registering uninstall entry"
New-Item -Path $UninstallKey -Force | Out-Null

$uninstallCmd = "`"$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
$quietUninstallCmd = "$uninstallCmd -Silent"

$bytes = (Get-ChildItem -LiteralPath $InstallDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeKb = [int]($bytes / 1KB)

New-ItemProperty -Path $UninstallKey -Name "DisplayName" -Value $AppName -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "DisplayVersion" -Value $displayVersion -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "Publisher" -Value $Publisher -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "InstallLocation" -Value $InstallDir -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "DisplayIcon" -Value "$(Join-Path $InstallDir $GuiExe),0" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "UninstallString" -Value $uninstallCmd -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "QuietUninstallString" -Value $quietUninstallCmd -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "InstallDate" -Value (Get-Date -Format "yyyyMMdd") -PropertyType String -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "EstimatedSize" -Value $sizeKb -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "NoModify" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $UninstallKey -Name "NoRepair" -Value 1 -PropertyType DWord -Force | Out-Null

Write-Host ""
Write-Host "Installed $AppName $displayVersion" -ForegroundColor Green
Write-Host "  GUI : $(Join-Path $InstallDir $GuiExe)"
Write-Host "  CLI : $(Join-Path $InstallDir $CliExe)"
Write-Host "  Uninstall: Settings > Apps, or run uninstall.ps1 in the install folder."
exit 0
