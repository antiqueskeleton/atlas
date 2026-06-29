; Atlas AI - Inno Setup Installer Script
; Firman Power Equipment
;
; Requires Inno Setup 6+  https://jrsoftware.org/isdl.php
; Build with:  ISCC.exe installer\atlas_installer.iss
; (or use build.bat which runs both PyInstaller and ISCC)

#define AppName      "Atlas AI"
#define AppVersion   "0.2"
#define AppPublisher "Firman Power Equipment"
#define AppExeName   "Atlas AI.exe"
#define BuildDir     "..\dist\Atlas AI"
#define OutDir       "..\dist\installer"

[Setup]
AppId={{E7C3B1A4-9F2D-4E87-B6AC-FPE20260629}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://www.firmanpowerequipment.com
AppSupportURL=https://www.firmanpowerequipment.com
AppUpdatesURL=https://www.firmanpowerequipment.com
DefaultDirName={autopf}\{#AppPublisher}\{#AppName}
DefaultGroupName={#AppPublisher}\{#AppName}
DisableProgramGroupPage=auto
OutputDir={#OutDir}
OutputBaseFilename=AtlasAI-v{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Main application (entire PyInstaller output folder)
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "Launch {#AppName} now"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove AppData config and database on uninstall (user prompted via Code section)
; We do NOT delete %APPDATA%\Atlas automatically — user data is preserved

[Code]
procedure InitializeWizard;
begin
  // Database and user config are created on first app launch in
  // %APPDATA%\Atlas\ — the installer does not need to set them up.
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
