#define MyAppName    "Arcane Audio"
#define MyAppDirName "ArcaneAudio"
#define MyAppVersion "1.0.1"
#define MyPublisher  "Eric Hernandez"
#define MyAppExeName "ArcaneAudio.exe"

; Point at the REAL files relative to this .iss (SourcePath == installer\)
#define IconFile    AddBackslash(SourcePath) + "..\\arcaneaudio\\resources\\installer.ico"
#define LicenseFile AddBackslash(SourcePath) + "..\\arcaneaudio\\resources\\GPL_V3.txt"

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
AppId={{PUT-A-NEW-GUID-HERE}}
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

#pragma message "DEBUG: SourcePath = " + SourcePath
#pragma message "DEBUG: IconFile   = " + IconFile
#pragma message "DEBUG: LicenseFile= " + LicenseFile

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