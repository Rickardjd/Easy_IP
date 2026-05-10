; ============================================================================
; Easy IP - Inno Setup installer script
; Requires: Inno Setup 6  https://jrsoftware.org/isinfo.php
;
; Run via build.bat, or manually:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
; ============================================================================

#define AppName      "Easy IP"
#define AppVersion   "1.0"
#define AppPublisher "i-PRO Tools"
#define AppExeName   "Easy_IP.exe"
#define AppURL       "https://github.com/your-org/easy-ip"

[Setup]
; ── Identity ────────────────────────────────────────────────────────────────
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
VersionInfoVersion={#AppVersion}.0.0

; ── Install location ─────────────────────────────────────────────────────────
; Use LocalAppData so the app can write its config and data files without
; requiring administrator rights.
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; ── Output ───────────────────────────────────────────────────────────────────
OutputDir=..\dist
OutputBaseFilename=Easy_IP_Setup_{#AppVersion}
SetupIconFile=..\assets\icon.ico

; ── Compression ──────────────────────────────────────────────────────────────
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; ── Appearance ───────────────────────────────────────────────────────────────
WizardStyle=modern
; Optionally supply custom wizard images:
;   WizardSmallImageFile=..\assets\wizard_small.bmp   ; 55×58 px
;   WizardImageFile=..\assets\wizard_side.bmp          ; 164×314 px

; ── Misc ─────────────────────────────────────────────────────────────────────
DisableWelcomePage=no
AllowNoIcons=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── Optional tasks shown in the installer wizard ─────────────────────────────
[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}";       \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "startmenuicon";  Description: "Create a Start Menu shortcut"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

; ── Files ────────────────────────────────────────────────────────────────────
[Files]
; Main application bundle (built by PyInstaller)
Source: "..\dist\Easy_IP\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; ── Directories ──────────────────────────────────────────────────────────────
[Dirs]
; Pre-create the data folder so the app can write on first launch.
Name: "{app}\data"; Permissions: users-full

; ── Shortcuts ────────────────────────────────────────────────────────────────
[Icons]
; Start Menu
Name: "{group}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"; \
    Comment: "i-PRO Camera & Recorder IP Setup Tool"; \
    Tasks: startmenuicon

Name: "{group}\Uninstall {#AppName}"; \
    Filename: "{uninstallexe}"

; Desktop
Name: "{autodesktop}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"; \
    Comment: "i-PRO Camera & Recorder IP Setup Tool"; \
    Tasks: desktopicon

; ── Run after install ────────────────────────────────────────────────────────
[Run]
Filename: "{app}\{#AppExeName}"; \
    Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

; ── Uninstall: remove generated files the user may not care about ─────────────
[UninstallDelete]
; Remove the data folder only if it is empty (don't delete user data silently).
; To also delete data, change Type to "filesandordirs".
Type: dirifempty; Name: "{app}\data"
