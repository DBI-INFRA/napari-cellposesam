; Setup .exe for Windows: a small online installer that runs install.ps1, which downloads Python,
; napari, napari-cellposesam and the PyTorch build for this machine's GPU.
;
;   iscc installer\windows\napari-cellposesam.iss    (writes installer\windows\Output\)
;
; Made with napari-installer-template; update with `copier update -a installer/.copier-answers.yml`.
; This file is UTF-8 with a byte order mark, which Inno Setup needs to read non-ASCII names.

#define AppName "napari-cellposesam"
#ifndef AppVersion
  #define AppVersion "0"
#endif

[Setup]
AppId={{6A0C3B7E-3D59-4C55-9F4B-8C1C7E2B5F31}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=napari-cellposesam contributors
AppPublisherURL=https://github.com/jeskowagner/napari-cellposesam
; per user, no admin rights: napari's plugin manager writes into the install
PrivilegesRequired=lowest
; uv links each Python it installs through a junction, which RedirectionGuard (Inno Setup 6.7 and
; later, passed on to install.ps1) refuses to follow when a user without admin rights made it. It
; protects folders that other users can write to, and this install is in the user's own folder.
#if Ver >= 0x06070000
RedirectionGuard=no
#endif
DefaultDirName={localappdata}\napari-cellposesam
DisableDirPage=yes
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=napari-cellposesam-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"
Name: "extrasetup"; Description: "Download the Cellpose-SAM model (about 1.2 GB) &now"

[Files]
Source: "..\install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; DestName: "icon.ico"; Flags: ignoreversion
; napari's license, which covers icon.ico
Source: "icon-license.txt"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\env\Scripts\pythonw.exe"; Parameters: "-m napari_launcher launch -w napari-cellposesam ""cellpose"""; \
  Description: "Start {#AppName}"; Flags: postinstall nowait skipifsilent; Check: InstallSucceeded

[UninstallRun]
Filename: "{app}\env\Scripts\python.exe"; Parameters: "-m napari_launcher shortcut remove --name ""{#AppName}"""; \
  Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "RemoveShortcuts"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  InstallExitCode: Integer;

function InstallSucceeded: Boolean;
begin
  Result := InstallExitCode = 0;
end;

{ the setup's own exit code, so silent installs can tell that install.ps1 failed }
function GetCustomSetupExitCode: Integer;
begin
  Result := InstallExitCode;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: String;
begin
  if CurStep = ssInstall then
  begin
    { tells install.ps1 that this folder is its own }
    ForceDirectories(ExpandConstant('{app}'));
    SaveStringToFile(ExpandConstant('{app}\.napari-cellposesam-install'), '', False);
  end;
  if CurStep = ssPostInstall then
  begin
    Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\install.ps1') + '"' +
      ' -Root "' + ExpandConstant('{app}') + '"';
    if not WizardIsTaskSelected('desktopicon') then
      Params := Params + ' -NoDesktop';
    if WizardIsTaskSelected('extrasetup') then
      Params := Params + ' -ExtraSetup yes'
    else
      Params := Params + ' -ExtraSetup no';
    if not WizardSilent() then
      Params := Params + ' -PauseOnError';
    WizardForm.StatusLabel.Caption := 'Downloading and installing napari, napari-cellposesam and PyTorch. This takes a few minutes...';
    { a visible console, so the download progress shows }
    if not Exec('powershell.exe', Params, '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
      ResultCode := -1;
    InstallExitCode := ResultCode;
    { install.ps1 writes why it stopped to install.log: a failed download, or shortcuts it could not add }
    if ResultCode <> 0 then
      SuppressibleMsgBox('Installing {#AppName} did not finish (exit code ' + IntToStr(ResultCode) + ').' + #13#10#13#10 +
        'The end of ' + ExpandConstant('{app}\install.log') + ' says what went wrong. ' +
        'If a download failed, check the internet connection. Then run the setup again.', mbError, MB_OK, IDOK);
  end;
end;
