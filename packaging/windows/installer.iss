#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#ifndef AppSource
  #define AppSource "dist\WireWizardGUI"
#endif

#ifndef OutputDir
  #define OutputDir "dist"
#endif

#ifndef LicensePath
  #define LicensePath "..\..\LICENSE"
#endif

[Setup]
AppId={{D2C8EC68-13A8-4DB6-B269-61DDDE027921}
AppName=WireWizardGUI
AppVersion={#MyAppVersion}
AppVerName=WireWizardGUI {#MyAppVersion}
AppPublisher=WireWizardGUI contributors
DefaultDirName={localappdata}\Programs\WireWizardGUI
DefaultGroupName=WireWizardGUI
DisableProgramGroupPage=yes
AllowNoIcons=yes
LicenseFile={#LicensePath}
OutputDir={#OutputDir}
OutputBaseFilename=WireWizardGUI-{#MyAppVersion}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName=WireWizardGUI {#MyAppVersion}
UninstallDisplayIcon={app}\WireWizardGUI.exe
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no
ChangesEnvironment=no
#ifdef SetupIconPath
SetupIconFile={#SetupIconPath}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WireWizardGUI"; Filename: "{app}\WireWizardGUI.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\WireWizardGUI"; Filename: "{app}\WireWizardGUI.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\WireWizardGUI.exe"; Description: "{cm:LaunchProgram,WireWizardGUI}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
