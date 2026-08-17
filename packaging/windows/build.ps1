[CmdletBinding()]
param(
    [Parameter()]
    [string]$Version = "0.1.0",

    [Parameter()]
    [string]$GraphvizRoot,

    [Parameter()]
    [switch]$SkipInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "WireWizardGUI build: this script must be run on Windows. PyInstaller cannot cross-compile a Windows application."
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$versionChecker = Join-Path $repoRoot "packaging\common\check_version.py"
$implementation = Join-Path $PSScriptRoot "build_impl.ps1"

foreach ($requiredFile in @($versionChecker, $implementation)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "WireWizardGUI build: required file is missing: $requiredFile"
    }
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "WireWizardGUI build: project virtual environment was not found at '$pythonPath'. From the repository root run: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\prepare.ps1"
}

Write-Host "Checking release version consistency..."
& $pythonPath $versionChecker "--expected" $Version
if ($LASTEXITCODE -ne 0) {
    throw "WireWizardGUI build: Version '$Version' does not match the project metadata. Update the project version or pass the matching -Version value."
}

$oldPath = $env:PATH
try {
    if (-not $SkipInstaller -and $null -eq (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue)) {
        $programFilesRoots = @(
            [Environment]::GetEnvironmentVariable("ProgramFiles(x86)"),
            [Environment]::GetEnvironmentVariable("ProgramFiles")
        ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

        $innoDirectories = @("Inno Setup 7", "Inno Setup 6")
        $compiler = $null
        foreach ($programFilesRoot in $programFilesRoots) {
            foreach ($innoDirectory in $innoDirectories) {
                $candidate = Join-Path $programFilesRoot "$innoDirectory\ISCC.exe"
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    $compiler = $candidate
                    break
                }
            }
            if ($null -ne $compiler) {
                break
            }
        }

        if ($null -eq $compiler) {
            throw "WireWizardGUI build: Inno Setup 7 or 6.3+ was not found. Install it, add ISCC.exe to PATH, or use -SkipInstaller."
        }

        $compilerDirectory = Split-Path -Parent $compiler
        $env:PATH = $compilerDirectory + [IO.Path]::PathSeparator + $env:PATH
    }

    if (-not $SkipInstaller) {
        $resolvedCompiler = (Get-Command "ISCC.exe" -ErrorAction Stop).Source
        $productVersion = (Get-Item -LiteralPath $resolvedCompiler).VersionInfo.ProductVersion
        $versionMatch = [regex]::Match([string]$productVersion, '\d+\.\d+(?:\.\d+)?')
        if (-not $versionMatch.Success) {
            throw "WireWizardGUI build: could not determine the Inno Setup version for '$resolvedCompiler'. Inno Setup 6.3+ is required."
        }
        $innoVersion = [Version]$versionMatch.Value
        if ($innoVersion -lt [Version]"6.3") {
            throw "WireWizardGUI build: Inno Setup $innoVersion is too old; version 6.3 or newer is required."
        }
    }

    $implementationParameters = @{
        Version = $Version
        SkipInstaller = $SkipInstaller
    }
    if ($PSBoundParameters.ContainsKey("GraphvizRoot")) {
        $implementationParameters["GraphvizRoot"] = $GraphvizRoot
    }

    & $implementation @implementationParameters

    $applicationDirectory = Join-Path $PSScriptRoot "dist\WireWizardGUI"
    $portableArchive = Join-Path $PSScriptRoot "dist\WireWizardGUI-$Version-windows-x64-portable.zip"
    $portableMarker = Join-Path $applicationDirectory "portable.flag"
    if (Test-Path -LiteralPath $portableMarker -PathType Leaf) {
        throw "WireWizardGUI build: portable.flag leaked into the installer source directory."
    }

    $bundledLicenseCandidates = @(
        (Join-Path $applicationDirectory "licenses\EPL-2.0.txt"),
        (Join-Path $applicationDirectory "_internal\licenses\EPL-2.0.txt")
    )
    $bundledLicense = $bundledLicenseCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
    if ($null -eq $bundledLicense) {
        throw "WireWizardGUI build: the onedir application does not contain licenses\EPL-2.0.txt."
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($portableArchive)
    try {
        $portableFlags = @(
            $archive.Entries | Where-Object {
                $_.FullName.Replace("\", "/") -match '(^|/)portable\.flag$'
            }
        )
        $portableLicenses = @(
            $archive.Entries | Where-Object {
                $_.FullName.Replace("\", "/") -match '(^|/)licenses/EPL-2\.0\.txt$'
            }
        )
        if ($portableFlags.Count -ne 1) {
            throw "WireWizardGUI build: portable ZIP must contain exactly one portable.flag beside the application."
        }
        if ($portableLicenses.Count -lt 1) {
            throw "WireWizardGUI build: portable ZIP does not contain licenses/EPL-2.0.txt."
        }
    } finally {
        $archive.Dispose()
    }
} finally {
    $env:PATH = $oldPath
}
