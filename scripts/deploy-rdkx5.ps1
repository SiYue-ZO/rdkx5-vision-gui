<#
.SYNOPSIS
Build a board release, upload it with scp, verify it over SSH, and start it.

.EXAMPLE
.\scripts\deploy-rdkx5.ps1 -Target sunrise@192.168.1.10
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Target,
    [string]$RemoteRoot = "rdkx5-vision",
    [string]$Python = "python3",
    [switch]$NoModels,
    [switch]$NoStart,
    [switch]$Binary
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-PosixSingleQuoted([string]$Value) {
    $singleQuote = [string][char]39
    $embeddedQuote = $singleQuote + [char]34 + $singleQuote + [char]34 + $singleQuote
    return $singleQuote + $Value.Replace($singleQuote, $embeddedQuote) + $singleQuote
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$packageScript = Join-Path $PSScriptRoot "package_rdkx5.py"
$archive = Join-Path $repoRoot "dist\rdkx5-vision.tar.gz"
$packageArgs = @($packageScript, "--output", $archive)
if ($NoModels) { $packageArgs += "--no-models" }

& python @packageArgs
if ($LASTEXITCODE -ne 0) { throw "Packaging failed." }

$archiveName = Split-Path -Leaf $archive
$remoteArchive = "/tmp/$archiveName"
& scp $archive "$($Target):$remoteArchive"
if ($LASTEXITCODE -ne 0) { throw "Upload failed." }

if ([System.IO.Path]::IsPathRooted($RemoteRoot)) {
    $rootExpression = ConvertTo-PosixSingleQuoted $RemoteRoot
} else {
    $rootExpression = '"$HOME"/' + (ConvertTo-PosixSingleQuoted $RemoteRoot.TrimStart("/", "\"))
}

$releaseId = "release-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$quotedArchive = ConvertTo-PosixSingleQuoted $remoteArchive
$quotedPython = ConvertTo-PosixSingleQuoted $Python
$pidFileName = "rdkx5-vision.pid"
$remoteLines = @(
    "set -eu",
    "root=$rootExpression",
    ('release="$root/releases/{0}"' -f $releaseId),
    'mkdir -p "$root/releases"',
    'mkdir "$release"',
    ('tar -xzf {0} -C "$release" --strip-components=1' -f $quotedArchive),
    'cd "$release"',
    "bash scripts/verify-rdkx5.sh $quotedPython",
    'active_release="$release"'
)
if ($Binary) {
    $remoteLines += @(
        "bash scripts/build-rdkx5-binary.sh $quotedPython",
        'active_release="$release/binary-dist/rdkx5-vision"',
        'test -x "$active_release/rdkx5-vision"'
    )
}
$remoteLines += 'ln -sfn "$active_release" "$root/current"'
if (-not $NoStart) {
    $remoteLines += @(
        ('pid_file="$root/{0}"' -f $pidFileName),
        'if test -s "$pid_file"; then',
        '  old_pid="$(cat "$pid_file")"',
        '  old_cwd="$(readlink -f "/proc/$old_pid/cwd" 2>/dev/null || true)"',
        '  case "$old_cwd" in',
        '    "$root"/*) kill "$old_pid" 2>/dev/null || true ;;',
        '  esac',
        'fi',
        'rm -f "$pid_file"'
    )
    $remoteLines += 'cd "$active_release"'
    $remoteLines += "mkdir -p logs"
    if ($Binary) {
        $remoteLines += "nohup ./rdkx5-vision > logs/launcher.log 2>&1 < /dev/null & echo `$! > `"`$pid_file`""
    } else {
        $remoteLines += "RDKX5_PYTHON=$quotedPython nohup bash scripts/run-rdkx5.sh > logs/launcher.log 2>&1 < /dev/null & echo `$! > `"`$pid_file`""
    }
    $mode = if ($Binary) { "binary" } else { "source" }
    $remoteLines += "echo 'Started $mode release $releaseId; log: $RemoteRoot/current/logs/launcher.log'"
} else {
    $mode = if ($Binary) { "binary" } else { "source" }
    $remoteLines += "echo 'Verified $mode release $releaseId; not started.'"
}
$remoteLines += 'find "$root/releases" -mindepth 1 -maxdepth 1 -type d ! -path "$release" -exec rm -rf -- {} +'

# ssh passes this string directly to the remote shell. Use LF explicitly:
# [Environment]::NewLine is CRLF on Windows and Bash treats the trailing CR
# as part of each token.
$remoteCommand = $remoteLines -join ([string][char]10)
& ssh $Target $remoteCommand
if ($LASTEXITCODE -ne 0) { throw "Remote verification or startup failed." }
Write-Host "Deployment completed: $Target -> $RemoteRoot/current"
