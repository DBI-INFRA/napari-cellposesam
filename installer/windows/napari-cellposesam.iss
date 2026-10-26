; Setup .exe for Windows: a small online installer that runs install.ps1, which downloads Python,
; napari, napari-cellposesam and the PyTorch build for this machine's GPU.
;
;   iscc installer\windows\napari-cellposesam.iss    (writes installer\windows\Output\)

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
; per user, no admin rights: the plugin manager and the cellpose 3 fetch write into the install
PrivilegesRequired=lowest
DefaultDirName={localappdata}\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename={#AppName}-setup
SetupIconFile=cellpose.ico
UninstallDisplayIcon={app}\cellpose.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"
Name: "model"; Description: "Download the Cellpose-SAM &model now (about 1.2 GB), instead of the first time you segment"

[Files]
Source: "..\install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "cellpose.ico"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\env\Scripts\pythonw.exe"; Parameters: "-m napari_cellposesam launch"; \
  Description: "Start {#AppName}"; Flags: postinstall nowait skipifsilent; Check: InstallSucceeded

[UninstallRun]
Filename: "{app}\env\Scripts\python.exe"; Parameters: "-m napari_cellposesam shortcut --remove"; \
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
    Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\install.ps1') + '"';
    if not WizardIsTaskSelected('desktopicon') then
      Params := Params + ' -NoDesktop';
    if WizardIsTaskSelected('model') then
      Params := Params + ' -Model yes'
    else
      Params := Params + ' -Model no';
    if not WizardSilent() then
      Params := Params + ' -PauseOnError';
    WizardForm.StatusLabel.Caption := 'Downloading and installing napari, cellpose and PyTorch. This takes a few minutes...';
    { a visible console, so the download progress shows }
    if not Exec('powershell.exe', Params, '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
      ResultCode := -1;
    InstallExitCode := ResultCode;
    if ResultCode <> 0 then
      SuppressibleMsgBox('Installing napari-cellposesam failed (exit code ' + IntToStr(ResultCode) + '). ' +
        'Check the internet connection and run the setup again.', mbError, MB_OK, IDOK);
  end;
end;
