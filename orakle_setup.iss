; orakle_setup.iss — Installeur Windows ORAKLE (Inno Setup 6)
; Compiler :  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" orakle_setup.iss
; Prérequis : dist\ORAKLE\ produit par PyInstaller (build.ps1)
; Sortie   : installer\ORAKLE_Setup_{version}.exe

#define AppName "ORAKLE"
#define AppVersion "0.1.1"
#define AppPublisher "22eme ARKANE"
#define AppExeName "ORAKLE.exe"

[Setup]
AppId={{6E3B2C71-9D44-4A5B-8F02-ORAKLE000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
; Icône de l'installeur lui-même = médaillon
SetupIconFile=resources\logo.ico
OutputDir=installer
OutputBaseFilename=ORAKLE_Setup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Lancer {#AppName} au démarrage de Windows"; GroupDescription: "Options :"

[Files]
; Tout le dossier onedir produit par PyInstaller
Source: "dist\ORAKLE\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
; Lancement au démarrage de Windows si coché. {commonstartup} (tous profils) :
; l'installeur tourne élevé (admin), {userstartup} viserait le profil élevé.
Name: "{commonstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Ne supprime PAS la config utilisateur (%APPDATA%\orakle) : données de
; l'utilisateur (réglages + dictionnaire), conservées pour une réinstallation.
Type: filesandordirs; Name: "{app}"
