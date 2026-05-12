; Inno Setup script for DeltaSuite (Windows installer).
;
; Compile from a Developer PowerShell after running PyInstaller::
;
;   pyinstaller installer\deltasuite.spec --noconfirm
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\deltasuite.iss
;
; The compiler reads the version from the `MyAppVersion` define below
; (or `--define MyAppVersion=...` on the ISCC command line) so the same
; .iss is reused by the GitHub Actions release workflow.

#define MyAppName        "DeltaSuite"
#ifndef MyAppVersion
  #define MyAppVersion   "0.1.0"
#endif
#define MyAppPublisher   "DeltaSuite contributors"
#define MyAppURL         "https://github.com/ghvmof/deltasuite"
#define MyAppExeName     "DeltaSuite.exe"
#define MyAppId          "{{2BFB7D7E-2DA1-4D0A-99E0-7B86CF14B118}}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=dist\installer
OutputBaseFilename=DeltaSuite-{#MyAppVersion}-Setup
SetupIconFile=branding\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate";   Description: "Associate .deltasuite project files with {#MyAppName}"; \
  GroupDescription: "File associations:"

[Files]
Source: "dist\DeltaSuite\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md";    DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE";      DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; \
  Tasks: desktopicon

[Registry]
; Register the .deltasuite extension (the project metadata file).
Root: HKA; Subkey: "Software\Classes\.deltasuite"; \
  ValueType: string; ValueName: ""; ValueData: "DeltaSuite.Project"; \
  Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\DeltaSuite.Project"; \
  ValueType: string; ValueName: ""; ValueData: "DeltaSuite project"; \
  Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\DeltaSuite.Project\DefaultIcon"; \
  ValueType: string; ValueName: ""; \
  ValueData: "{app}\{#MyAppExeName},0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\DeltaSuite.Project\shell\open\command"; \
  ValueType: string; ValueName: ""; \
  ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: associate

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent
