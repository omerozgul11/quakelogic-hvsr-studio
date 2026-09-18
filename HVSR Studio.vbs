' QuakeLogic HVSR Studio - start without a console window (double-click me)
Option Explicit
Dim shell, fso, root, py, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
py = root & "\runtime\win-x64\python\pythonw.exe"
If Not fso.FileExists(py) Then py = root & "\engine\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(py) Then py = "pythonw.exe"
shell.CurrentDirectory = root
cmd = """" & py & """ """ & root & "\launcher\launch.py"""
shell.Environment("PROCESS")("HVSR_QUIET") = "1"
shell.Run cmd, 0, False
