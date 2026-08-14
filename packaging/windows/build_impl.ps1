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

function Stop-Build {
    param([Parameter(Mandatory = $true)][string]$Message)

    throw "WireWizardGUI build: $Message"
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        Stop-Build "$FailureMessage (exit code $LASTEXITCODE)."
    }
}

function Find-InnoSetupCompiler {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $installRoots = @(
        ${env:ProgramFiles(x86)},
        $env:ProgramFiles
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    foreach ($installRoot in $installRoots) {
        $candidate = Join-Path $installRoot "Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    return $null
}

function Find-GraphvizRoot {
    param([Parameter(Mandatory = $true)][string]$SearchRoot)

    if (-not (Test-Path -LiteralPath $SearchRoot -PathType Container)) {
        return $null
    }

    $directDot = Join-Path $SearchRoot "bin\dot.exe"
    if (Test-Path -LiteralPath $directDot -PathType Leaf) {
        return (Resolve-Path -LiteralPath $SearchRoot).Path
    }

    $dot = Get-ChildItem -LiteralPath $SearchRoot -Filter "dot.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq "bin" } |
        Sort-Object { $_.FullName.Length } |
        Select-Object -First 1

    if ($null -eq $dot) {
        return $null
    }

    return (Split-Path -Parent (Split-Path -Parent $dot.FullName))
}

function Get-VendoredGraphviz {
    param(
        [Parameter(Mandatory = $true)][string]$VendorDirectory,
        [Parameter(Mandatory = $true)][string]$CacheDirectory
    )

    $graphvizVersion = "15.1.0"
    $archiveName = "windows_10_cmake_Release_Graphviz-$graphvizVersion-win64.zip"
    $downloadUrl = "https://gitlab.com/api/v4/projects/4207231/packages/generic/graphviz-releases/$graphvizVersion/$archiveName"
    $expectedSha256 = "c3ee71ff81ab97352082225574a140f20f5d6929d5f33d1097a1fe0e4161962a"
    $archivePath = Join-Path $CacheDirectory $archiveName
    $partialArchivePath = "$archivePath.download"

    $existingRoot = Find-GraphvizRoot -SearchRoot $VendorDirectory
    if (-not [string]::IsNullOrWhiteSpace($existingRoot)) {
        return $existingRoot
    }

    New-Item -ItemType Directory -Path $CacheDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $VendorDirectory -Force | Out-Null

    $archiveIsValid = $false
    if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
        $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $archiveIsValid = $actualHash -eq $expectedSha256
        if (-not $archiveIsValid) {
            Write-Warning "Cached Graphviz archive has the wrong SHA-256 and will be downloaded again."
            Remove-Item -LiteralPath $archivePath -Force
        }
    }

    if (-not $archiveIsValid) {
        if (Test-Path -LiteralPath $partialArchivePath -PathType Leaf) {
            Remove-Item -LiteralPath $partialArchivePath -Force
        }

        Write-Host "Downloading Graphviz $graphvizVersion from the official Graphviz GitLab package registry..."
        try {
            [Net.ServicePointManager]::SecurityProtocol =
                [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $downloadUrl -OutFile $partialArchivePath -UseBasicParsing | Out-Null
        } catch {
            if (Test-Path -LiteralPath $partialArchivePath -PathType Leaf) {
                Remove-Item -LiteralPath $partialArchivePath -Force
            }
            Stop-Build "could not download Graphviz from '$downloadUrl'. Check the network connection, place the official archive under '$CacheDirectory', or pass -GraphvizRoot. $($_.Exception.Message)"
        }

        $actualHash = (Get-FileHash -LiteralPath $partialArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedSha256) {
            Remove-Item -LiteralPath $partialArchivePath -Force
            Stop-Build "downloaded Graphviz archive failed SHA-256 verification. Expected $expectedSha256, received $actualHash. The archive was deleted."
        }

        Move-Item -LiteralPath $partialArchivePath -Destination $archivePath -Force
    }

    Write-Host "Extracting the verified Graphviz archive..."
    try {
        Expand-Archive -LiteralPath $archivePath -DestinationPath $VendorDirectory -Force
    } catch {
        Stop-Build "could not extract '$archivePath'. $($_.Exception.Message)"
    }

    $extractedRoot = Find-GraphvizRoot -SearchRoot $VendorDirectory
    if ([string]::IsNullOrWhiteSpace($extractedRoot)) {
        Stop-Build "the verified Graphviz archive was extracted, but no bin\dot.exe was found below '$VendorDirectory'."
    }

    return $extractedRoot
}

if ($env:OS -ne "Windows_NT") {
    Stop-Build "this script must be run in Windows PowerShell or PowerShell on Windows. PyInstaller cannot cross-compile a Windows application."
}

if ($Version -notmatch '^\d+\.\d+\.\d+(?:\.\d+)?$') {
    Stop-Build "Version '$Version' is invalid. Use three or four numeric components, for example 1.2.3 or 1.2.3.4."
}

$scriptDirectory = $PSScriptRoot
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDirectory "..\.."))
$entryPoint = Join-Path $repoRoot "wirewizard_gui\app.py"
$licensePath = Join-Path $repoRoot "LICENSE"
$noticesPath = Join-Path $repoRoot "THIRD_PARTY_NOTICES.md"
$eplLicensePath = Join-Path $repoRoot "packaging\licenses\EPL-2.0.txt"
$requirementsPath = Join-Path $scriptDirectory "requirements-build.txt"
$installerScript = Join-Path $scriptDirectory "installer.iss"
$specPath = Join-Path $repoRoot "packaging\pyinstaller\WireWizardGUI.spec"
$assetGenerator = Join-Path $repoRoot "packaging\common\generate_assets.py"
$versionGenerator = Join-Path $repoRoot "packaging\common\generate_windows_version.py"
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$workRoot = Join-Path $scriptDirectory ".build"
$cacheRoot = Join-Path $scriptDirectory ".cache"
$pyInstallerWorkRoot = Join-Path $workRoot "pyinstaller"
$generatedAssetsRoot = Join-Path $workRoot "assets"
$iconPath = Join-Path $generatedAssetsRoot "wirewizard.ico"
$versionFile = Join-Path $workRoot "version_info.txt"
$distRoot = Join-Path $scriptDirectory "dist"
$applicationDirectory = Join-Path $distRoot "WireWizardGUI"
$applicationExe = Join-Path $applicationDirectory "WireWizardGUI.exe"
$portableStagingRoot = Join-Path $workRoot "portable"
$portableDirectory = Join-Path $portableStagingRoot "WireWizardGUI"
$portableArchive = Join-Path $distRoot "WireWizardGUI-$Version-windows-x64-portable.zip"
$installerExe = Join-Path $distRoot "WireWizardGUI-$Version-windows-x64-setup.exe"

$requiredFiles = @(
    $entryPoint,
    $licensePath,
    $noticesPath,
    $eplLicensePath,
    $requirementsPath,
    $installerScript,
    $specPath,
    $assetGenerator,
    $versionGenerator
)
foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        Stop-Build "required file is missing: $requiredFile"
    }
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Stop-Build "project virtual environment was not found at '$pythonPath'. From the repository root run: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\prepare.ps1"
}

$dependencyCheck = @'
import importlib.util
import struct
import sys

required = {
    "Pillow": "PIL",
    "PyInstaller": "PyInstaller",
    "PySide6": "PySide6",
    "PyYAML": "yaml",
    "WireViz": "wireviz",
}
missing = [name for name, module in required.items() if importlib.util.find_spec(module) is None]
if missing:
    print("Missing build dependencies: " + ", ".join(missing), file=sys.stderr)
    raise SystemExit(2)
if struct.calcsize("P") * 8 != 64:
    print("A 64-bit Python interpreter is required for the x64 release.", file=sys.stderr)
    raise SystemExit(3)
print(sys.version.split()[0])
'@

Write-Host "Checking the project virtual environment..."
Invoke-CheckedCommand -FilePath $pythonPath -ArgumentList @("-c", $dependencyCheck) -FailureMessage "dependency check failed. Install them with: .\.venv\Scripts\python.exe -m pip install -r .\packaging\windows\requirements-build.txt"
Invoke-CheckedCommand -FilePath $pythonPath -ArgumentList @("-m", "pip", "check") -FailureMessage "the virtual environment contains incompatible packages"

New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null

Write-Host "Generating Windows icon and executable version metadata..."
Invoke-CheckedCommand -FilePath $pythonPath -ArgumentList @($assetGenerator, "--output", $generatedAssetsRoot) -FailureMessage "application icon generation failed"
Invoke-CheckedCommand -FilePath $pythonPath -ArgumentList @($versionGenerator, "--version", $Version, "--output", $versionFile) -FailureMessage "Windows version metadata generation failed"
if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
    Stop-Build "icon generator reported success, but '$iconPath' was not created."
}
if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
    Stop-Build "version generator reported success, but '$versionFile' was not created."
}

$graphvizWasSupplied = $PSBoundParameters.ContainsKey("GraphvizRoot") -and -not [string]::IsNullOrWhiteSpace($GraphvizRoot)
if ($graphvizWasSupplied) {
    $GraphvizRoot = [System.IO.Path]::GetFullPath($GraphvizRoot)
} else {
    $GraphvizRoot = Get-VendoredGraphviz -VendorDirectory (Join-Path $scriptDirectory "vendor\graphviz") -CacheDirectory $cacheRoot
}
$dotExe = Join-Path $GraphvizRoot "bin\dot.exe"

if (-not (Test-Path -LiteralPath $GraphvizRoot -PathType Container)) {
    Stop-Build "Graphviz directory was not found at '$GraphvizRoot'. Pass the root of an extracted official Windows ZIP with -GraphvizRoot C:\path\to\Graphviz."
}
if (-not (Test-Path -LiteralPath $dotExe -PathType Leaf)) {
    Stop-Build "'$GraphvizRoot' is not a usable Graphviz root: bin\dot.exe is missing. The expected layout is <GraphvizRoot>\bin\dot.exe."
}

Write-Host "Checking vendored Graphviz..."
Invoke-CheckedCommand -FilePath $dotExe -ArgumentList @("-V") -FailureMessage "vendored Graphviz could not start. Re-extract the official x64 Windows ZIP and make sure its bin and lib directories are intact"
$graphvizSmokeInput = Join-Path $workRoot "graphviz-smoke.dot"
[System.IO.File]::WriteAllText($graphvizSmokeInput, "digraph { a -> b }", [System.Text.Encoding]::ASCII)
foreach ($format in @("svg", "png")) {
    $graphvizSmokeOutput = Join-Path $workRoot "graphviz-smoke.$format"
    Invoke-CheckedCommand -FilePath $dotExe -ArgumentList @("-T$format", "-o", $graphvizSmokeOutput, $graphvizSmokeInput) -FailureMessage "vendored Graphviz could not render $format; its plugins or libraries are incomplete"
    if (-not (Test-Path -LiteralPath $graphvizSmokeOutput -PathType Leaf) -or (Get-Item -LiteralPath $graphvizSmokeOutput).Length -eq 0) {
        Stop-Build "vendored Graphviz reported success but produced no $format output."
    }
}

$previousGraphvizRoot = [Environment]::GetEnvironmentVariable("WW_GRAPHVIZ_ROOT", "Process")
$previousIconPath = [Environment]::GetEnvironmentVariable("WW_ICON_PATH", "Process")
$previousVersionFile = [Environment]::GetEnvironmentVariable("WW_VERSION_FILE", "Process")
try {
    [Environment]::SetEnvironmentVariable("WW_GRAPHVIZ_ROOT", $GraphvizRoot, "Process")
    [Environment]::SetEnvironmentVariable("WW_ICON_PATH", $iconPath, "Process")
    [Environment]::SetEnvironmentVariable("WW_VERSION_FILE", $versionFile, "Process")

    $pyInstallerArguments = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", $distRoot,
        "--workpath", $pyInstallerWorkRoot,
        $specPath
    )

    Write-Host "Building the Windows onedir application..."
    Invoke-CheckedCommand -FilePath $pythonPath -ArgumentList $pyInstallerArguments -FailureMessage "PyInstaller failed"
} finally {
    [Environment]::SetEnvironmentVariable("WW_GRAPHVIZ_ROOT", $previousGraphvizRoot, "Process")
    [Environment]::SetEnvironmentVariable("WW_ICON_PATH", $previousIconPath, "Process")
    [Environment]::SetEnvironmentVariable("WW_VERSION_FILE", $previousVersionFile, "Process")
}

if (-not (Test-Path -LiteralPath $applicationExe -PathType Leaf)) {
    Stop-Build "PyInstaller reported success, but '$applicationExe' was not created."
}

$bundledDotCandidates = @(
    (Join-Path $applicationDirectory "graphviz\bin\dot.exe"),
    (Join-Path $applicationDirectory "_internal\graphviz\bin\dot.exe")
)
$bundledDot = $bundledDotCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if ($null -eq $bundledDot) {
    Stop-Build "the application was built, but Graphviz was not copied into the onedir bundle."
}

Copy-Item -LiteralPath $licensePath -Destination (Join-Path $applicationDirectory "LICENSE.txt") -Force
Copy-Item -LiteralPath $noticesPath -Destination (Join-Path $applicationDirectory "THIRD_PARTY_NOTICES.md") -Force
$visibleLicensesDirectory = Join-Path $applicationDirectory "licenses"
New-Item -ItemType Directory -Path $visibleLicensesDirectory -Force | Out-Null
Copy-Item -LiteralPath $eplLicensePath -Destination (Join-Path $visibleLicensesDirectory "EPL-2.0.txt") -Force

if (Test-Path -LiteralPath (Join-Path $applicationDirectory "portable.flag") -PathType Leaf) {
    Stop-Build "the installer source unexpectedly contains portable.flag. Delete it and rebuild."
}

if (Test-Path -LiteralPath $portableStagingRoot -PathType Container) {
    Remove-Item -LiteralPath $portableStagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $portableDirectory -Force | Out-Null
Copy-Item -Path (Join-Path $applicationDirectory "*") -Destination $portableDirectory -Recurse -Force
New-Item -ItemType File -Path (Join-Path $portableDirectory "portable.flag") -Force | Out-Null

if (Test-Path -LiteralPath $portableArchive -PathType Leaf) {
    Remove-Item -LiteralPath $portableArchive -Force
}

Write-Host "Creating the portable ZIP..."
Compress-Archive -LiteralPath $portableDirectory -DestinationPath $portableArchive -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $portableArchive -PathType Leaf)) {
    Stop-Build "portable archive was not created at '$portableArchive'."
}

if ($SkipInstaller) {
    Write-Host "Skipping the installer because -SkipInstaller was supplied."
} else {
    $innoCompiler = Find-InnoSetupCompiler
    if ([string]::IsNullOrWhiteSpace($innoCompiler)) {
        Stop-Build "Inno Setup 6 was not found. Install it and rerun the script, or use -SkipInstaller to build only the onedir application and portable ZIP."
    }

    $innoArguments = @(
        "/DMyAppVersion=$Version",
        "/DAppSource=$applicationDirectory",
        "/DOutputDir=$distRoot",
        "/DLicensePath=$licensePath",
        "/DSetupIconPath=$iconPath",
        $installerScript
    )

    Write-Host "Building the Inno Setup installer..."
    Invoke-CheckedCommand -FilePath $innoCompiler -ArgumentList $innoArguments -FailureMessage "Inno Setup failed"
    if (-not (Test-Path -LiteralPath $installerExe -PathType Leaf)) {
        Stop-Build "Inno Setup reported success, but '$installerExe' was not created."
    }
}

Write-Host ""
Write-Host "Build completed successfully."
Write-Host "Onedir application: $applicationDirectory"
Write-Host "Portable archive:   $portableArchive"
if (-not $SkipInstaller) {
    Write-Host "Installer:          $installerExe"
}
