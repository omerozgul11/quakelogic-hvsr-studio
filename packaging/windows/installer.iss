; QuakeLogic HVSR Studio — Inno Setup 6 script
; Compile after packaging/build_dist.py has produced dist/QuakeLogic-HVSR-Studio:
;   ISCC.exe /DAppVersion=1.0.0 /DStageDir=..\..\dist\QuakeLogic-HVSR-Studio /DOutDir=..\..\dist installer.iss
; Installs per-user (no administrator rights) into %LocalAppData%\Programs so the
; application folder stays writable (SQLite database, project folders, logs).

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef StageDir
  #define StageDir "..\..\dist\QuakeLogic-HVSR-Studio"
#endif
#ifndef OutDir
  #define OutDir "..\..\dist"
#endif

[Setup]
AppId={{D026E14D-8BCD-4537-B661-60D78B388D70}
AppName=QuakeLogic HVSR Studio
AppVersion={#AppVersion}
AppVerName=QuakeLogic HVSR Studio {#AppVersion}
AppPublisher=QuakeLogic Inc.
AppPublisherURL=https://www.quakelogic.net
DefaultDirName={localappdata}\Programs\QuakeLogic HVSR Studio
DefaultGroupName=QuakeLogic HVSR Studio
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#OutDir}
OutputBaseFilename=QuakeLogic-HVSR-Studio-{#AppVersion}-setup-win-x64
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes
LicenseFile={#StageDir}\LICENSE
UninstallDisplayName=QuakeLogic HVSR Studio
ChangesEnvironment=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#OutDir}\downloads\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: VCRedistNeeded

[Dirs]
Name: "{app}\data"
Name: "{app}\storage\logs"
Name: "{app}\storage\framework\cache\data"
Name: "{app}\storage\framework\sessions"
Name: "{app}\storage\framework\views"

[Icons]
Name: "{group}\QuakeLogic HVSR Studio"; Filename: "{app}\HVSR Studio.bat"; WorkingDir: "{app}"; IconFilename: "{app}\runtime\win-x64\php\php.exe"; Comment: "Start QuakeLogic HVSR Studio"
Name: "{group}\HVSR Studio User Guide"; Filename: "{app}\docs\user-guide.md"
Name: "{group}\Uninstall QuakeLogic HVSR Studio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\QuakeLogic HVSR Studio"; Filename: "{app}\HVSR Studio.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ runtime..."; Check: VCRedistNeeded; Flags: waituntilterminated
Filename: "{app}\HVSR Studio.bat"; Description: "Start QuakeLogic HVSR Studio now"; Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
Type: filesandordirs; Name: "{app}\storage\framework"
Type: filesandordirs; Name: "{app}\storage\logs"
; Project data in {app}\data is intentionally kept; the uninstaller tells the user where it is.

[Code]
function VCRedistNeeded(): Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
    Result := (Installed <> 1);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    MsgBox('Your projects and the SQLite database were left in:' + #13#10 + ExpandConstant('{app}\data') + #13#10 + 'Delete that folder manually if you no longer need them.', mbInformation, MB_OK);
end;
