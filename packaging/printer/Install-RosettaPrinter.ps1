# Adds a printer named "Rosetta Plotter" to this computer.
#
# Printing to it from any program (Illustrator, Rhino, a browser) writes the page as a PDF to
#   %ProgramData%\Rosetta Plotter\Print\print.pdf
# and Rosetta Plotter, when it is open, picks that up as a new drawing in its Jobs list
# (src\rosetta\app\printinbox.py watches the same path).
#
# It uses Windows' own "Microsoft Print To PDF" driver on a local port whose name is that file's path,
# so printing asks no questions. Nothing is downloaded and no third-party driver is installed.
#
# Needs administrator rights (adding a printer does). "Install Rosetta Printer.bat" asks for them.
# Written for Windows PowerShell 5.1.

$ErrorActionPreference = "Stop"
$PrinterName = "Rosetta Plotter"
$DriverName = "Microsoft Print To PDF"
$Folder = Join-Path $env:ProgramData "Rosetta Plotter\Print"
$PortName = Join-Path $Folder "print.pdf"

function Say($text) { Write-Host $text }
function Stop-WithMessage($text) {
    Write-Host ""
    Write-Host $text -ForegroundColor Red
    exit 1
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Stop-WithMessage "This needs administrator rights. Close this window, right-click 'Install Rosetta Printer.bat' and choose 'Run as administrator'."
}

$driver = Get-PrinterDriver -Name $DriverName -ErrorAction SilentlyContinue
if (-not $driver) {
    Stop-WithMessage ("Windows' 'Microsoft Print to PDF' feature is turned off on this computer, and the Rosetta Plotter printer is built on it.`n" +
        "Turn it on: Start > type 'Turn Windows features on or off' > tick 'Microsoft Print to PDF' > OK. Then run this again.")
}

Say "Making the folder the printer writes to: $Folder"
New-Item -ItemType Directory -Force -Path $Folder | Out-Null
# Everyone who uses this computer may read the prints (S-1-5-32-545 is the built-in Users group,
# named by its ID so this also works on Windows in other languages).
& icacls $Folder /grant "*S-1-5-32-545:(OI)(CI)M" /T /Q | Out-Null
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Couldn't set who may read the folder $Folder." }

if (-not (Get-PrinterPort -Name $PortName -ErrorAction SilentlyContinue)) {
    Say "Adding the printer port."
    try { Add-PrinterPort -Name $PortName }
    catch { Stop-WithMessage "Couldn't add the printer port. Windows said: $($_.Exception.Message)" }
}

$existing = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.PortName -ne $PortName -or $existing.DriverName -ne $DriverName) {
        Say "A printer named '$PrinterName' is already here with other settings: pointing it at Rosetta Plotter."
        try { Set-Printer -Name $PrinterName -DriverName $DriverName -PortName $PortName }
        catch { Stop-WithMessage "Couldn't change the existing '$PrinterName' printer. Windows said: $($_.Exception.Message)" }
    } else {
        Say "The '$PrinterName' printer is already installed."
    }
} else {
    Say "Adding the '$PrinterName' printer."
    try { Add-Printer -Name $PrinterName -DriverName $DriverName -PortName $PortName -Comment "Prints into the Rosetta Plotter app" }
    catch { Stop-WithMessage "Couldn't add the printer. Windows said: $($_.Exception.Message)" }
}

$check = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
if (-not $check -or $check.PortName -ne $PortName) {
    Stop-WithMessage "The printer didn't show up after adding it. Restart the computer and run this again."
}

Write-Host ""
Write-Host "Done. To use it:" -ForegroundColor Green
Say "  1. Open Rosetta Plotter."
Say "  2. In Illustrator, Rhino or any other program, choose Print and pick the '$PrinterName' printer."
Say "  3. The page appears in Rosetta Plotter's Jobs list a few seconds later."
Say ""
Say "Tips: print lines as vectors (in Rhino: Vector Output), at 100% scale, on a paper size that fits the drawing."
exit 0
