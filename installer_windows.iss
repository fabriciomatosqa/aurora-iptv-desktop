#define MyAppName "AURORA IPTV"
#define MyAppVersion "0.5.0"
#define MyAppExeName "AURORA-IPTV.exe"
[Setup]
AppId={{7E9AAB61-4913-4F3F-965F-3D7459381745}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=AURORA IPTV
DefaultDirName={localappdata}\Programs\AURORA IPTV
DefaultGroupName=AURORA IPTV
PrivilegesRequired=lowest
OutputDir=installer_out
OutputBaseFilename=AURORA-IPTV-Desktop-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=yes
SetupIconFile=assets\aurora_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
[Files]
Source: "dist\AURORA-IPTV\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\AURORA IPTV"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\AURORA IPTV"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir AURORA IPTV"; Flags: nowait postinstall skipifsilent
