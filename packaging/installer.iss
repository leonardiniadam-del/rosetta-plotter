; Inno Setup script for the student installer: one offline RosettaPlotterSetup-<version>.exe (design spec section 2).
;
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" /DAppVersion=0.1.0 packaging\installer.iss
;
; (scripts\build_installer.ps1 runs it after PyInstaller.) It packs the PyInstaller one-folder build
; (build\pyinstaller\dist\Rosetta Plotter), LICENSE, THIRD-PARTY-NOTICES.txt, the Quick Start page and Microsoft's offline WebView2
; Runtime installer (packaging\vendor, not in git), which runs only when the laptop doesn't have WebView2.
; The installer is unsigned: students click "More info", then "Run anyway" (QuickStart.html).

#define AppName "Rosetta Plotter"
#define AppExe "RosettaPlotter.exe"
#ifndef AppBuildDir
  #define AppBuildDir "..\build\pyinstaller\dist\Rosetta Plotter"
#endif
#ifndef AppVersion
  #define AppVersion GetVersionNumbersString(AppBuildDir + "\" + AppExe)
#endif
#define WebView2Installer "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"

[Setup]
; Never change AppId: Windows uses it to find the installed app for upgrades and uninstalling.
AppId={{817F7B01-5321-4E1C-8D6E-BE075E27A695}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Rosetta Plotter
AppCopyright=Copyright (C) 2026 Adam M. Leonardini. AGPL-3.0-or-later.
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
; Per-user by default (no admin password); the dialog offers "Install for all users" to administrators.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
OutputDir=..\dist-installer
OutputBaseFilename=RosettaPlotterSetup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Ticked by default. Adding a printer needs administrator rights, so the [Code] below asks Windows for them once,
; at the end of setup; if that's refused, everything else is still installed and the Start menu shortcut can add
; the printer later.
Name: "printer"; Description: "Add the ""Rosetta Plotter"" printer, so any program can print into the app (Windows asks for permission)"; GroupDescription: "Printing:"

[Files]
Source: "{#AppBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
; Copyright notices and licenses for the bundled third-party software (written by scripts\make_notices.py).
Source: "THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "QuickStart.html"; DestDir: "{app}"; Flags: ignoreversion
; The optional "Rosetta Plotter" printer (print from any program into the app). The "printer" task adds it at
; the end of setup (see [Code]); the Start menu shortcut below adds it later if that was skipped or refused.
Source: "printer\*"; DestDir: "{app}\Printer"; Flags: ignoreversion
; Extracted to {tmp} and run by the [Code] below only when WebView2 is missing.
Source: "vendor\{#WebView2Installer}"; Flags: dontcopy

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} Quick Start"; Filename: "{app}\QuickStart.html"
Name: "{group}\Install the {#AppName} printer"; Filename: "{app}\Printer\Install Rosetta Printer.bat"; Comment: "Print from any program straight into Rosetta Plotter"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\QuickStart.html"; Description: "Open the Quick Start guide"; Flags: postinstall shellexec nowait skipifsilent
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: postinstall nowait skipifsilent unchecked

[Code]
const
  WebView2ClientKey = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2Version(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

{ Microsoft's documented check: a per-machine runtime registers under WOW6432Node on 64-bit Windows,
  a per-user one under HKCU. }
function WebView2Installed: Boolean;
begin
  Result := HasWebView2Version(HKLM64, 'SOFTWARE\WOW6432Node\' + WebView2ClientKey)
    or HasWebView2Version(HKLM32, 'SOFTWARE\' + WebView2ClientKey)
    or HasWebView2Version(HKCU, 'Software\' + WebView2ClientKey);
end;

procedure InstallWebView2;
var
  ResultCode: Integer;
  Ran: Boolean;
begin
  WizardForm.StatusLabel.Caption := 'Installing Microsoft Edge WebView2 Runtime (this can take a minute)...';
  ExtractTemporaryFile('{#WebView2Installer}');
  Ran := Exec(ExpandConstant('{tmp}\{#WebView2Installer}'), '/silent /install', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  if WebView2Installed then
    Exit;
  Log(Format('WebView2 Runtime install did not take (ran: %d, exit code: %d)', [Ord(Ran), ResultCode]));
  if not IsAdminInstallMode then
    SuppressibleMsgBox('Rosetta Plotter is installed, but it also needs Microsoft Edge WebView2 Runtime, ' +
      'and installing that on this laptop needs administrator rights.' + #13#10#13#10 +
      'Ask your instructor or IT help desk to run this installer again and choose "Install for all users". ' +
      'Until then, Rosetta Plotter''s window can''t open.', mbInformation, MB_OK, IDOK)
  else
    SuppressibleMsgBox('Rosetta Plotter is installed, but Microsoft Edge WebView2 Runtime could not be ' +
      'installed (code ' + IntToStr(ResultCode) + ').' + #13#10#13#10 +
      'Rosetta Plotter''s window can''t open without it. Try running this installer again, or ask your ' +
      'IT help desk to install WebView2 Runtime.', mbError, MB_OK, IDOK);
end;

const
  PrinterKey = 'SYSTEM\CurrentControlSet\Control\Print\Printers\Rosetta Plotter';
  ErrorCancelled = 1223;  { the student chose No in Windows' permission prompt }

function PrinterInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM64, PrinterKey);
end;

{ Runs printer\Install-RosettaPrinter.ps1 with administrator rights ("runas" makes Windows ask for them; an
  administrator install already has them, so Windows doesn't ask again), then checks the printer is there. }
procedure InstallPrinter;
var
  Params: String;
  ResultCode: Integer;
  Ran: Boolean;
begin
  WizardForm.StatusLabel.Caption := 'Adding the Rosetta Plotter printer...';
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\Printer\Install-RosettaPrinter.ps1') + '"';
  Ran := ShellExec('runas', ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Params, '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  if PrinterInstalled then
    Exit;
  Log(Format('Printer install did not take (ran: %d, code: %d)', [Ord(Ran), ResultCode]));
  if (not Ran) and (ResultCode = ErrorCancelled) then
    SuppressibleMsgBox('Rosetta Plotter is installed. The Rosetta Plotter printer was not added, because ' +
      'Windows'' permission wasn''t given.' + #13#10#13#10 +
      'To add it later, open the Start menu and run "Install the Rosetta Plotter printer". ' +
      'If you don''t have administrator rights, ask your instructor or IT help desk.', mbInformation, MB_OK, IDOK)
  else
    SuppressibleMsgBox('Rosetta Plotter is installed, but the Rosetta Plotter printer could not be added.' + #13#10#13#10 +
      'Open the Start menu and run "Install the Rosetta Plotter printer": it shows the reason. ' +
      'Everything else in Rosetta Plotter works without the printer.', mbInformation, MB_OK, IDOK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then
    Exit;
  if not WebView2Installed then
    InstallWebView2;
  if WizardIsTaskSelected('printer') and not PrinterInstalled then
    InstallPrinter;
end;
