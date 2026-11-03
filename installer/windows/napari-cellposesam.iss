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
AppPublisherURL=https://github.com/DBI-INFRA/napari-cellposesam
; per user, no admin rights: napari's plugin manager writes into the install
PrivilegesRequired=lowest
; uv links each Python it installs through a junction, which RedirectionGuard (Inno Setup 6.7 and
; later, passed on to install.ps1) refuses to follow when a user without admin rights made it. It
; protects folders that other users can write to. The default install folder is the user's own, and
; a folder the user picks is their choice.
#if Ver >= 0x06070000
RedirectionGuard=no
#endif
DefaultDirName={localappdata}\napari-cellposesam
; the folder page shows on the first install, and updates go into the same folder
DisableDirPage=auto
; uv's links need a drive of this computer. FolderProblem in [Code] checks the rest.
AllowNetworkDrive=no
AllowUNCPath=no
DirExistsWarning=no
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
const
  DRIVE_REMOTE = 4;
  MarkerName = '.napari-cellposesam-install';

var
  InstallExitCode: Integer;

function GetDriveType(RootPathName: String): Cardinal;
  external 'GetDriveTypeW@kernel32.dll stdcall';
function GetVolumeInformation(RootPathName, VolumeNameBuffer: String; VolumeNameSize: Cardinal;
  var VolumeSerialNumber, MaximumComponentLength, FileSystemFlags: Cardinal;
  FileSystemNameBuffer: String; FileSystemNameSize: Cardinal): Boolean;
  external 'GetVolumeInformationW@kernel32.dll stdcall';

{ the file system of the drive that holds Dir, such as NTFS, or empty if Windows does not say }
function FileSystemOf(Dir: String): String;
var
  Serial, MaxLength, Flags: Cardinal;
  Name: String;
begin
  Name := StringOfChar(' ', 64);
  if GetVolumeInformation(AddBackslash(ExtractFileDrive(Dir)), '', 0, Serial, MaxLength, Flags, Name, 64) then
    Result := Trim(Copy(Name, 1, Pos(#0, Name + #0) - 1))
  else
    Result := '';
end;

function DirIsEmpty(Dir: String): Boolean;
var
  FindRec: TFindRec;
begin
  Result := True;
  if FindFirst(AddBackslash(Dir) + '*', FindRec) then
  try
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        Result := False;
    until (not Result) or (not FindNext(FindRec));
  finally
    FindClose(FindRec);
  end;
end;

{ whether this user can make a folder in Dir, or in the nearest folder above it that exists }
function CanMakeFolders(Dir: String): Boolean;
var
  Parent, Test: String;
begin
  Parent := Dir;
  while (not DirExists(Parent)) and (ExtractFileDir(Parent) <> Parent) do
    Parent := ExtractFileDir(Parent);
  Test := AddBackslash(Parent) + MarkerName + '-test';
  RemoveDir(Test);
  Result := CreateDir(Test);
  if Result then
    RemoveDir(Test);
end;

{ why the install cannot go into Dir, or empty if it can. Uninstalling deletes the whole folder, so
  it has to be a new or empty folder, or an earlier install of this app. }
function FolderProblem(Dir: String): String;
var
  FileSystem: String;
begin
  Result := '';
  Dir := RemoveBackslashUnlessRoot(Dir);
  FileSystem := FileSystemOf(Dir);
  if CompareText(Dir, AddBackslash(ExtractFileDrive(Dir))) = 0 then
    Result := 'Choose a folder in ' + Dir + ', not the drive itself.'
  else if GetDriveType(AddBackslash(ExtractFileDrive(Dir))) = DRIVE_REMOTE then
    Result := Dir + ' is on a network drive. Choose a folder on a drive of this computer.'
  else if (FileSystem <> '') and (CompareText(FileSystem, 'NTFS') <> 0) and
    (CompareText(FileSystem, 'ReFS') <> 0) then
    Result := ExtractFileDrive(Dir) + ' uses the ' + FileSystem + ' file system, which this install does not ' +
      'work on. Choose a folder on a drive that uses NTFS, such as C:.'
  else if DirExists(Dir) and (not FileExists(AddBackslash(Dir) + MarkerName)) and (not DirIsEmpty(Dir)) then
    Result := Dir + ' already has files in it. Choose a new or empty folder, because uninstalling deletes ' +
      'the whole folder.'
  else if not CanMakeFolders(Dir) then
    Result := 'You cannot add files to ' + Dir + '. Choose a folder you can write to.';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Problem: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Problem := FolderProblem(WizardDirValue);
    if Problem <> '' then
    begin
      SuppressibleMsgBox(Problem, mbError, MB_OK, IDOK);
      Result := False;
    end;
  end;
end;

{ the same check for silent installs, which can set the folder with /DIR= }
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := FolderProblem(ExpandConstant('{app}'));
end;

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
    SaveStringToFile(ExpandConstant('{app}\') + MarkerName, '', False);
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
    { install.ps1 goes on without the desktop shortcut when Windows does not let it write to the desktop }
    if (ResultCode = 0) and WizardIsTaskSelected('desktopicon') and
      (not FileExists(ExpandConstant('{userdesktop}\{#AppName}.lnk'))) then
      SuppressibleMsgBox('Windows did not let the setup add a desktop shortcut. ' +
        'Start {#AppName} from the Start menu instead.' + #13#10#13#10 +
        'Controlled folder access in Windows Security can block shortcuts on the desktop.', mbInformation, MB_OK, IDOK);
    { install.ps1 writes why it stopped to install.log: a failed download, or shortcuts it could not add }
    if ResultCode <> 0 then
      SuppressibleMsgBox('Installing {#AppName} did not finish (exit code ' + IntToStr(ResultCode) + ').' + #13#10#13#10 +
        'The end of ' + ExpandConstant('{app}\install.log') + ' says what went wrong. ' +
        'If a download failed, check the internet connection. Then run the setup again.', mbError, MB_OK, IDOK);
  end;
end;
