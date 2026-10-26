; Inno Setup script for TRIP streaming tool (Windows)
; The language chosen in the setup wizard (Italiano / English) becomes the program language:
; it is written to {app}\language.ini and can be changed later in Settings -> Interface.
; Build: iscc installer\windows\trip.iss   (after "pyinstaller trip.spec")

#define AppName "TRIP streaming tool"
#define AppVersion "1.0.1"
#define AppPublisher "Massimiliano Mascioli Trippa (Max Trip)"
#define AppExe "trip-streaming-tool.exe"

[Setup]
AppId={{6B7E1F52-9C1A-4D7B-A6E3-3F1D0C7A5B21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\TRIP streaming tool
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\..\assets\icon.ico
LicenseFile=..\..\LICENSE
OutputDir=Output
OutputBaseFilename=TRIP-streaming-tool-{#AppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
it.LaunchApp=Avvia TRIP streaming tool
en.LaunchApp=Launch TRIP streaming tool
it.Comment=Streaming audio dal vivo verso Icecast, SHOUTcast e WebRTC
en.Comment=Live audio streaming to Icecast, SHOUTcast and WebRTC

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\trip-streaming-tool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[INI]
; language selected in the installer -> used by the program until the user changes it
Filename: "{app}\language.ini"; Section: "TRIP"; Key: "language"; String: "{language}"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "{cm:Comment}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; also store the choice in the user's configuration (overrides an older choice)
Filename: "{app}\{#AppExe}"; Parameters: "--set-language {language}"; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
