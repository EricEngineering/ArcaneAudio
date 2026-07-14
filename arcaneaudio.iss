#define MyAppName    "Arcane Audio"
#define MyAppDirName "ArcaneAudio"
; Version is the single source of truth in arcaneaudio\__init__.py — build_installer.bat
; and CI extract it and pass it as /DMyAppVersion. This fallback only applies to a bare
; ISCC run and should be kept roughly in sync.
#ifndef MyAppVersion
  #define MyAppVersion "0.8.0"
#endif
#define MyPublisher  "Eric Hernandez"
#define MyAppExeName "ArcaneAudio.exe"

; Point at the REAL files relative to this .iss (SourcePath == installer\)
#define IconFile    AddBackslash(SourcePath) + "..\\arcaneaudio\\resources\\installer.ico"
#define LicenseFile AddBackslash(SourcePath) + "..\\arcaneaudio\\resources\\AGPL_V3.txt"

[Setup]
; (A) Machine-wide install
PrivilegesRequired=admin
DefaultDirName={autopf}\{#MyAppDirName}

; (B) Per-user install (optional)
;PrivilegesRequired=lowest
;DefaultDirName={userpf}\{#MyAppDirName}

CloseApplications=yes
RestartApplications=yes
DefaultGroupName={#MyAppName}
AppId={{B9EB3FEB-A541-4410-85EC-40E9D00CFE6D}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
WizardStyle=modern
Compression=lzma
SolidCompression=yes
UsePreviousAppDir=yes

; Output beside this .iss (installer\output)
OutputDir={#SourcePath}output
OutputBaseFilename=ArcaneAudio-Setup-{#MyAppVersion}

#ifexist IconFile
  SetupIconFile={#IconFile}
#else
  #error "Installer Icon not found at: " + IconFile
#endif

#ifexist LicenseFile
  LicenseFile={#LicenseFile}
#else
  #error "License File not found at: " + LicenseFile
#endif

UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; PyInstaller output is one level up from installer\ (dist\ArcaneAudio\*)
Source: "{#SourcePath}..\dist\ArcaneAudio\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent