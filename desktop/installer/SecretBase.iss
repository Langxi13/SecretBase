#ifndef MyAppVersion
  #error MyAppVersion is required
#endif
#ifndef MySourceDir
  #error MySourceDir is required
#endif
#ifndef MyOutputDir
  #error MyOutputDir is required
#endif
#ifndef MyProjectRoot
  #error MyProjectRoot is required
#endif
#ifndef MyLanguageFile
  #error MyLanguageFile is required
#endif

#define MyAppName "SecretBase"
#define MyAppExeName "SecretBase.exe"

[Setup]
AppId={{D03B47A4-2BF0-4891-B7A0-A792A5462978}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=SecretBase
AppPublisherURL=https://github.com/Langxi13/SecretBase
AppSupportURL=https://github.com/Langxi13/SecretBase/issues
AppUpdatesURL=https://github.com/Langxi13/SecretBase/releases
DefaultDirName={localappdata}\Programs\SecretBase
DefaultGroupName=SecretBase
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#MyOutputDir}
OutputBaseFilename=SecretBase-v{#MyAppVersion}-windows-x64-setup
SetupIconFile={#MyProjectRoot}\desktop\assets\secretbase.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile={#MyProjectRoot}\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
AppMutex=Local\SecretBase.Desktop.Mutex
UsePreviousAppDir=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoDescription=SecretBase Windows Desktop Installer
VersionInfoCompany=SecretBase
VersionInfoCopyright=SecretBase Contributors
MinVersion=10.0

[Languages]
Name: "chinesesimp"; MessagesFile: "{#MyLanguageFile}"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式"; Flags: checkedonce

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SecretBase"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\SecretBase"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 SecretBase"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\SecretBase"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\SecretBase"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Code]
var
  PurgeLocalData: Boolean;

function ConfirmUninstallOptions: Boolean;
var
  Form: TSetupForm;
  WarningLabel, PathLabel, ConfirmationLabel: TNewStaticText;
  PurgeCheckBox: TNewCheckBox;
  ConfirmationEdit: TNewEdit;
  ContinueButton, CancelButton: TNewButton;
  ModalResult, ButtonWidth: Integer;
begin
  Result := False;
  Form := CreateCustomForm(ScaleX(520), ScaleY(270), True, True);
  try
    Form.Caption := '卸载 SecretBase';

    WarningLabel := TNewStaticText.Create(Form);
    WarningLabel.Parent := Form;
    WarningLabel.Left := ScaleX(18);
    WarningLabel.Top := ScaleY(18);
    WarningLabel.Width := Form.ClientWidth - ScaleX(36);
    WarningLabel.Height := ScaleY(48);
    WarningLabel.AutoSize := False;
    WarningLabel.WordWrap := True;
    WarningLabel.Caption := '默认只卸载程序并保留密码库。删除本地数据不可恢复，请先确认已经保存需要的加密备份。';

    PathLabel := TNewStaticText.Create(Form);
    PathLabel.Parent := Form;
    PathLabel.Left := WarningLabel.Left;
    PathLabel.Top := WarningLabel.Top + WarningLabel.Height + ScaleY(8);
    PathLabel.Width := WarningLabel.Width;
    PathLabel.Height := ScaleY(34);
    PathLabel.AutoSize := False;
    PathLabel.WordWrap := True;
    PathLabel.Caption := '数据目录：' + ExpandConstant('{localappdata}\SecretBase');

    PurgeCheckBox := TNewCheckBox.Create(Form);
    PurgeCheckBox.Parent := Form;
    PurgeCheckBox.Left := WarningLabel.Left;
    PurgeCheckBox.Top := PathLabel.Top + PathLabel.Height + ScaleY(10);
    PurgeCheckBox.Width := WarningLabel.Width;
    PurgeCheckBox.Height := ScaleY(22);
    PurgeCheckBox.Caption := '同时删除 vault、备份、AI 设置、日志、偏好和 WebView 缓存';
    PurgeCheckBox.Checked := False;

    ConfirmationLabel := TNewStaticText.Create(Form);
    ConfirmationLabel.Parent := Form;
    ConfirmationLabel.Left := WarningLabel.Left;
    ConfirmationLabel.Top := PurgeCheckBox.Top + PurgeCheckBox.Height + ScaleY(12);
    ConfirmationLabel.Width := WarningLabel.Width;
    ConfirmationLabel.Caption := '如需删除全部数据，请输入 DELETE：';

    ConfirmationEdit := TNewEdit.Create(Form);
    ConfirmationEdit.Parent := Form;
    ConfirmationEdit.Left := WarningLabel.Left;
    ConfirmationEdit.Top := ConfirmationLabel.Top + ConfirmationLabel.Height + ScaleY(6);
    ConfirmationEdit.Width := ScaleX(210);
    ConfirmationEdit.Height := ScaleY(24);

    ContinueButton := TNewButton.Create(Form);
    ContinueButton.Parent := Form;
    ContinueButton.Caption := '继续卸载';
    ContinueButton.Top := Form.ClientHeight - ScaleY(40);
    ContinueButton.ModalResult := mrOk;
    ContinueButton.Default := True;

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Caption := '取消';
    CancelButton.Top := ContinueButton.Top;
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;

    ButtonWidth := Form.CalculateButtonWidth([ContinueButton.Caption, CancelButton.Caption]);
    CancelButton.Width := ButtonWidth;
    ContinueButton.Width := ButtonWidth;
    CancelButton.Left := Form.ClientWidth - ButtonWidth - ScaleX(18);
    ContinueButton.Left := CancelButton.Left - ButtonWidth - ScaleX(8);

    repeat
      ModalResult := Form.ShowModal;
      if ModalResult <> mrOk then
        Exit;
      if not PurgeCheckBox.Checked then
      begin
        PurgeLocalData := False;
        Result := True;
        Exit;
      end;
      if CompareText(Trim(ConfirmationEdit.Text), 'DELETE') = 0 then
      begin
        PurgeLocalData := True;
        Result := True;
        Exit;
      end;
      MsgBox('确认词不正确。请输入 DELETE，或取消删除本地数据。', mbError, MB_OK);
      Form.ActiveControl := ConfirmationEdit;
    until False;
  finally
    Form.Free;
  end;
end;

function InitializeUninstall: Boolean;
begin
  PurgeLocalData := False;
  if UninstallSilent then
  begin
    PurgeLocalData :=
      (CompareText(ExpandConstant('{param:PURGEDATA|0}'), '1') = 0) and
      (CompareText(ExpandConstant('{param:CONFIRMDELETE|}'), 'DELETE') = 0);
    Result := True;
  end
  else
    Result := ConfirmUninstallOptions;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: String;
begin
  if (CurUninstallStep = usPostUninstall) and PurgeLocalData then
  begin
    DataPath := ExpandConstant('{localappdata}\SecretBase');
    if DirExists(DataPath) and not DelTree(DataPath, True, True, True) then
      MsgBox('部分本地数据无法删除，请手动检查：' + DataPath, mbError, MB_OK);
  end;
end;
