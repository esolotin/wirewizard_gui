[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PythonInformation {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter()]
        [AllowEmptyCollection()]
        [string[]]$PrefixArguments = @()
    )

    # Windows PowerShell 5.1 can strip embedded double quotes when it builds a
    # native command line. Keep the Python probe on one line and use only
    # single-quoted Python literals so python -c receives it unchanged.
    $probe = "import json,struct,sys;print(json.dumps({'version':'.'.join(str(part) for part in sys.version_info[:3]),'bits':struct.calcsize('P')*8,'executable':sys.executable,'is_venv':sys.prefix!=sys.base_prefix},separators=(',',':')))"

    try {
        $output = @(& $FilePath @PrefixArguments "-c" $probe 2>&1)
        $exitCode = $LASTEXITCODE
    } catch {
        return [PSCustomObject]@{
            Success = $false
            Error = $_.Exception.Message
        }
    }

    $outputText = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        if ([string]::IsNullOrWhiteSpace($outputText)) {
            $outputText = "process exited with code $exitCode"
        }
        return [PSCustomObject]@{
            Success = $false
            Error = $outputText.Trim()
        }
    }

    try {
        $information = $outputText.Trim() | ConvertFrom-Json -ErrorAction Stop
        $version = [Version]$information.version
    } catch {
        return [PSCustomObject]@{
            Success = $false
            Error = "could not read the interpreter information: $outputText"
        }
    }

    return [PSCustomObject]@{
        Success = $true
        Version = $version
        Bits = [int]$information.bits
        Executable = [string]$information.executable
        IsVenv = [bool]$information.is_venv
    }
}

function Get-PythonRejectionReason {
    param(
        [Parameter(Mandatory = $true)]
        [PSCustomObject]$Information
    )

    if (-not $Information.Success) {
        return $Information.Error
    }
    if ($Information.Version -lt [Version]"3.10.1" -or $Information.Version -ge [Version]"3.15") {
        return "Python $($Information.Version) is unsupported; use Python >=3.10.1 and <3.15"
    }
    if ($Information.Bits -ne 64) {
        return "Python $($Information.Version) is $($Information.Bits)-bit; a 64-bit interpreter is required"
    }
    return $null
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    try {
        & $FilePath @ArgumentList
    } catch {
        throw "WireWizardGUI prepare: ${FailureMessage}: $($_.Exception.Message)"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "WireWizardGUI prepare: $FailureMessage (exit code $LASTEXITCODE)."
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "WireWizardGUI prepare: this script must be run on 64-bit Windows."
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$requirementsPath = Join-Path $repoRoot "requirements-build.txt"
$venvRoot = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "WireWizardGUI prepare: pinned requirements file is missing: $requirementsPath"
}

if (Test-Path -LiteralPath $venvRoot) {
    if (-not (Test-Path -LiteralPath $venvRoot -PathType Container)) {
        throw "WireWizardGUI prepare: '$venvRoot' exists but is not a directory. Rename or remove it, then run this script again."
    }
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "WireWizardGUI prepare: '$venvRoot' is incomplete and does not contain Scripts\python.exe. Rename or remove it, then run this script again."
    }

    $venvInformation = Get-PythonInformation -FilePath $venvPython
    $venvRejection = Get-PythonRejectionReason -Information $venvInformation
    if ($null -ne $venvRejection) {
        throw "WireWizardGUI prepare: the existing .venv cannot be used: $venvRejection. Rename or remove '$venvRoot', then run this script again."
    }
    if (-not $venvInformation.IsVenv) {
        throw "WireWizardGUI prepare: '$venvPython' is not a Python virtual environment. Rename or remove '$venvRoot', then run this script again."
    }

    Write-Host "Using existing Python $($venvInformation.Version) virtual environment: $venvRoot"
} else {
    $candidates = @()
    $launcher = Get-Command "py.exe" -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $launcher) {
        # Probe supported minor versions explicitly. A bare `py -3` may select
        # a newer, unsupported interpreter even when a usable one is installed.
        foreach ($pythonVersion in @("3.14", "3.13", "3.12", "3.11", "3.10")) {
            $candidates += [PSCustomObject]@{
                Label = "py -$pythonVersion"
                FilePath = $launcher.Source
                PrefixArguments = @("-$pythonVersion")
            }
        }
    }

    $python = Get-Command "python.exe" -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $python) {
        $candidates += [PSCustomObject]@{
            Label = "python"
            FilePath = $python.Source
            PrefixArguments = @()
        }
    }

    $selected = $null
    $rejections = @()
    foreach ($candidate in $candidates) {
        $information = Get-PythonInformation -FilePath $candidate.FilePath -PrefixArguments $candidate.PrefixArguments
        $rejection = Get-PythonRejectionReason -Information $information
        if ($null -eq $rejection) {
            $selected = $candidate
            $selected | Add-Member -NotePropertyName Information -NotePropertyValue $information
            break
        }
        $rejections += "$($candidate.Label): $rejection"
    }

    if ($null -eq $selected) {
        $details = if ($rejections.Count -gt 0) {
            " Checked candidates: " + ($rejections -join "; ") + "."
        } else {
            " Neither py.exe nor python.exe was found in PATH."
        }
        throw "WireWizardGUI prepare: no suitable 64-bit Python was found.$details Install 64-bit Python >=3.10.1 and <3.15 from https://www.python.org/downloads/windows/, enable the Python launcher or add python.exe to PATH, restart VS Code, and try again."
    }

    Write-Host "Creating .venv with $($selected.Label) (Python $($selected.Information.Version))..."
    $venvArguments = @($selected.PrefixArguments) + @("-m", "venv", $venvRoot)
    Invoke-CheckedCommand -FilePath $selected.FilePath -ArgumentList $venvArguments -FailureMessage "could not create '$venvRoot'"

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "WireWizardGUI prepare: Python reported success, but '$venvPython' was not created."
    }
}

Write-Host "Installing pinned application and build dependencies..."
Invoke-CheckedCommand -FilePath $venvPython -ArgumentList @(
    "-m", "pip", "install",
    "--disable-pip-version-check",
    "--requirement", $requirementsPath
) -FailureMessage "dependency installation failed"

Write-Host "Checking dependency compatibility..."
Invoke-CheckedCommand -FilePath $venvPython -ArgumentList @(
    "-m", "pip", "check",
    "--disable-pip-version-check"
) -FailureMessage "pip found incompatible packages"

$finalInformation = Get-PythonInformation -FilePath $venvPython
if (-not $finalInformation.Success) {
    throw "WireWizardGUI prepare: the prepared Python environment could not be verified: $($finalInformation.Error)"
}

Write-Host "WireWizardGUI build environment is ready."
Write-Host "Python: $($finalInformation.Version) ($($finalInformation.Bits)-bit)"
Write-Host "Virtual environment: $venvRoot"
