[Setup]
AppId={{B567D9EF-6C73-48CA-B058-57F19C2741D1}
AppName=S15.3 Research Terminal
AppVersion=0.0.1
AppPublisher=Tancodes
DefaultDirName={autopf}\S15.3 Research Terminal
DefaultGroupName=S15.3 Research Terminal
OutputDir=..\..\dist_installer
OutputBaseFilename=S153ResearchTerminal-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\S153ResearchTerminal.exe

[Files]
Source: "..\..\dist\S153ResearchTerminal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\S15.3 Research Terminal"; Filename: "{app}\S153ResearchTerminal.exe"
Name: "{autodesktop}\S15.3 Research Terminal"; Filename: "{app}\S153ResearchTerminal.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\S153ResearchTerminal.exe"; Description: "Launch S15.3 Research Terminal"; Flags: nowait postinstall skipifsilent
