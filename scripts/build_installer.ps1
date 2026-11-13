# Build the student installer end to end:
#   1. the page (npm run build in ui\)
#   2. the one-folder app (PyInstaller, packaging\rosetta.spec)
#   3. a smoke check of the frozen app (--smoke-check: a stand-in plotter, no serial port is ever opened,
#      so it is safe with an AxiDraw plugged in)
#   4. packaging\THIRD-PARTY-NOTICES.txt (scripts\make_notices.py, from what PyInstaller bundled)
#   5. the installer (Inno Setup, packaging\installer.iss) -> dist-installer\RosettaPlotterSetup-<version>.exe
#
#   powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 [-Iscc <path to ISCC.exe>] [-SkipUi]
#
# Needs: .venv (with PyInstaller), npm, Inno Setup 6, and Microsoft's offline WebView2 Runtime installer at
# packaging\vendor\MicrosoftEdgeWebView2RuntimeInstallerX64.exe (not in git: too big).
param(
    [string]$Iscc = "",
    [switch]$SkipUi
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$AppDir = Join-Path $Root "build\pyinstaller\dist\Rosetta Plotter"
$AppExe = Join-Path $AppDir "RosettaPlotter.exe"
$WebView2 = Join-Path $Root "packaging\vendor\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host $text -ForegroundColor Red; exit 1 }

if (-not $Iscc) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $Iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Iscc -or -not (Test-Path $Iscc)) { Fail "Inno Setup 6 (ISCC.exe) not found; pass -Iscc <path>." }
if (-not (Test-Path $Python)) { Fail ".venv not found: create it first (see README)." }
if (-not (Test-Path $WebView2)) { Fail "Missing $WebView2 (Microsoft's offline WebView2 Runtime installer, x64)." }

$Version = & $Python -c "import sys; sys.path.insert(0, r'$Root\src'); import rosetta; print(rosetta.__version__)"
if ($LASTEXITCODE -ne 0 -or -not $Version) { Fail "Couldn't read the version from src\rosetta\__init__.py." }
$Version = $Version.Trim()
Write-Host "Rosetta Plotter $Version"

if (-not $SkipUi) {
    Step "Building the page (npm run build)"
    Push-Location (Join-Path $Root "ui")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { Fail "npm run build failed." }
    } finally { Pop-Location }
}

Step "Freezing the app (PyInstaller)"
& $Python -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $Root "build\pyinstaller\dist") `
    --workpath (Join-Path $Root "build\pyinstaller\work") `
    (Join-Path $Root "packaging\rosetta.spec")
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed." }
if (-not (Test-Path $AppExe)) { Fail "PyInstaller didn't produce $AppExe." }

Step "Smoke-checking the frozen app"
$Result = Join-Path $Root "build\smoke-frozen.json"
if (Test-Path $Result) { Remove-Item $Result }
$process = Start-Process -FilePath $AppExe -ArgumentList @("--smoke-check", "`"$Result`"") -PassThru -Wait
if (-not (Test-Path $Result)) { Fail "The smoke check wrote no result (exit code $($process.ExitCode))." }
$smoke = Get-Content $Result -Raw | ConvertFrom-Json
Get-Content $Result | Write-Host
if ($process.ExitCode -ne 0 -or -not $smoke.ready -or -not $smoke.shell -or @($smoke.missing).Count -gt 0) {
    Fail "The frozen app failed its smoke check."
}

Step "Writing third-party notices"
& $Python (Join-Path $Root "scripts\make_notices.py")
if ($LASTEXITCODE -ne 0) { Fail "make_notices.py failed: a bundled package may be missing its license text." }

Step "Building the installer (Inno Setup)"
& $Iscc "/DAppVersion=$Version" (Join-Path $Root "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { Fail "ISCC failed." }

$Setup = Join-Path $Root "dist-installer\RosettaPlotterSetup-$Version.exe"
if (-not (Test-Path $Setup)) { Fail "ISCC didn't produce $Setup." }
Step ("Done: {0} ({1:N0} MB)" -f $Setup, ((Get-Item $Setup).Length / 1MB))
