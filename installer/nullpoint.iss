; Nullpoint per-user installer (no admin). Build: build.bat, or ISCC.exe installer\nullpoint.iss
#define AppVersion "2.1.3"

[Setup]
AppId={{6B0D8D2E-6E1B-4C55-9C1F-6B9D2C0A7E31}
AppName=Nullpoint
AppVersion={#AppVersion}
AppVerName=Nullpoint {#AppVersion}
AppPublisher=yensobased1
AppPublisherURL=https://github.com/yensobased1/nullpoint
AppSupportURL=https://github.com/yensobased1/nullpoint/issues
AppUpdatesURL=https://github.com/yensobased1/nullpoint/releases
PrivilegesRequired=lowest
DefaultDirName={autopf}\Nullpoint
DefaultGroupName=Nullpoint
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Nullpoint-Setup-{#AppVersion}
SetupIconFile=..\assets\nullpoint.ico
UninstallDisplayIcon={app}\Nullpoint.exe
WizardStyle=modern
WizardImageFile=..\assets\installer\wizard_large_100.bmp,..\assets\installer\wizard_large_125.bmp,..\assets\installer\wizard_large_150.bmp,..\assets\installer\wizard_large_200.bmp
WizardSmallImageFile=..\assets\installer\wizard_small_100.bmp,..\assets\installer\wizard_small_125.bmp,..\assets\installer\wizard_small_150.bmp,..\assets\installer\wizard_small_200.bmp
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
VersionInfoVersion={#AppVersion}
LicenseFile=..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked
Name: "startup"; Description: "Start Nullpoint with &Windows"; Flags: unchecked

[Files]
Source: "..\dist\Nullpoint.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nullpoint"; Filename: "{app}\Nullpoint.exe"
Name: "{autodesktop}\Nullpoint"; Filename: "{app}\Nullpoint.exe"; Tasks: desktopicon

[Registry]
; nullpoint://import/<code> links (per-user, removed on uninstall)
Root: HKCU; Subkey: "Software\Classes\nullpoint"; ValueType: string; ValueName: ""; ValueData: "URL:Nullpoint crosshair"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\nullpoint"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\nullpoint\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Nullpoint.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Nullpoint"; ValueData: """{app}\Nullpoint.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Nullpoint.exe"; Description: "Launch Nullpoint"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /im Nullpoint.exe /f"; Flags: runhidden; RunOnceId: "StopNullpoint"

[UninstallDelete]
Type: dirifempty; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Ask before touching the user's crosshairs: default is to keep them. }
    if DirExists(ExpandConstant('{userappdata}\Nullpoint')) and not UninstallSilent then
      if MsgBox('Also delete your Nullpoint settings, library and custom crosshairs?' + #13#10 +
                '(' + ExpandConstant('{userappdata}\Nullpoint') + ')', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{userappdata}\Nullpoint'), True, True, True);
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Nullpoint');
  end;
end;
