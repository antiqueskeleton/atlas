; Atlas AI - Inno Setup Installer Script
; dweeb.co
;
; Requires Inno Setup 6+  https://jrsoftware.org/isdl.php
; Build with:  ISCC.exe installer\atlas_installer.iss
; (or use build.bat which runs ICO generation, PyInstaller, and ISCC)

#define AppName      "Atlas AI"
#define AppVersion   "1.2.0"
#define AppPublisher "dweeb.co"
#define AppExeName   "Atlas AI.exe"
#define BuildDir     "..\dist\Atlas AI"
#define OutDir       "..\dist\installer"

[Setup]
AppId={{E7C3B1A4-9F2D-4E87-B6AC-FPE20260629}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://dweeb.co
AppSupportURL=https://dweeb.co
AppUpdatesURL=https://dweeb.co
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=auto
OutputDir={#OutDir}
OutputBaseFilename=AtlasAI-v{#AppVersion}-Setup
SetupIconFile=atlas.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Main application (entire PyInstaller output folder)
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "Launch {#AppName} now"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; User data in %APPDATA%\Atlas is preserved on uninstall

[Code]
procedure InitializeWizard;
begin
  // Database and user config are created on first launch in %APPDATA%\Atlas\
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  AppDataDir: String;
begin
  // Pre-create %APPDATA%\Atlas so the app can write its DB on first launch
  AppDataDir := ExpandConstant('{userappdata}\Atlas');
  if not DirExists(AppDataDir) then
    CreateDir(AppDataDir);
  Result := '';
end;
