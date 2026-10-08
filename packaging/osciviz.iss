; Instalator Windows (Inno Setup 6) dla folderu zbudowanego przez PyInstaller.
;   iscc /DAppVersion=1.0.0 packaging\osciviz.iss
; Wynik: dist\OsciViz-Windows-x64-setup.exe
; Instalator jest „na użytkownika” (bez uprawnień administratora), dodaje skrót
; w menu Start i kojarzy pliki projektu .osv z OsciViz.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6E1C0F43-5B7E-4C1B-9D4C-0A5C2E9B7F21}
AppName=OsciViz
AppVersion={#AppVersion}
AppPublisher=jabol71
AppPublisherURL=https://github.com/jabol71/osciviz
DefaultDirName={autopf}\OsciViz
DefaultGroupName=OsciViz
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=OsciViz-Windows-x64-setup
SetupIconFile=OsciViz.ico
UninstallDisplayIcon={app}\OsciViz.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\OsciViz\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\OsciViz"; Filename: "{app}\OsciViz.exe"
Name: "{autodesktop}\OsciViz"; Filename: "{app}\OsciViz.exe"; Tasks: desktopicon

[Registry]
; Skojarzenie plików .osv (w gałęzi użytkownika albo maszyny, zależnie od trybu instalacji).
Root: HKA; Subkey: "Software\Classes\.osv"; ValueType: string; ValueName: ""; ValueData: "OsciViz.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\OsciViz.Project"; ValueType: string; ValueName: ""; ValueData: "OsciViz Project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\OsciViz.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\OsciViz.exe,0"
Root: HKA; Subkey: "Software\Classes\OsciViz.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\OsciViz.exe"" ""%1"""

[Run]
Filename: "{app}\OsciViz.exe"; Description: "{cm:LaunchProgram,OsciViz}"; Flags: nowait postinstall skipifsilent
