# Removes the "Rosetta Plotter" printer that Install-RosettaPrinter.ps1 added, and its port.
# The folder %ProgramData%\Rosetta Plotter\Print and any print left in it stay; delete them by hand if wanted.
# Needs administrator rights. Written for Windows PowerShell 5.1.

$ErrorActionPreference = "Stop"
$PrinterName = "Rosetta Plotter"
$PortName = Join-Path (Join-Path $env:ProgramData "Rosetta Plotter\Print") "print.pdf"

function Stop-WithMessage($text) {
    Write-Host ""
    Write-Host $text -ForegroundColor Red
    exit 1
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Stop-WithMessage "This needs administrator rights. Close this window, right-click 'Remove Rosetta Printer.bat' and choose 'Run as administrator'."
}

$printer = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
if ($printer -and $printer.PortName -ne $PortName) {
    Stop-WithMessage "A printer named '$PrinterName' is here, but it isn't the one this installer made (its port is '$($printer.PortName)'). Leaving it alone."
}
if ($printer) {
    try { Remove-Printer -Name $PrinterName -Confirm:$false }
    catch { Stop-WithMessage "Couldn't remove the printer. Windows said: $($_.Exception.Message)" }
    Write-Host "Removed the '$PrinterName' printer."
} else {
    Write-Host "There is no '$PrinterName' printer on this computer."
}

if (Get-PrinterPort -Name $PortName -ErrorAction SilentlyContinue) {
    try { Remove-PrinterPort -Name $PortName -Confirm:$false }
    catch { Write-Host "The printer is gone, but its port couldn't be removed yet (Windows frees it after a restart)." }
}
Write-Host "Done." -ForegroundColor Green
exit 0
