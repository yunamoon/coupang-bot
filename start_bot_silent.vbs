' Run bot silently with auto-update.
' Double-click: pulls latest code, installs deps, launches GUI without console window.

Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = folder

' Pull latest code (hidden, wait for completion)
shell.Run "cmd /c git pull > nul 2>&1", 0, True

' Install/update dependencies (hidden, wait)
shell.Run "cmd /c pip install -r requirements.txt -q > nul 2>&1", 0, True

' pyw.exe = no-console Python launcher (auto-installed by python.org)
shell.Run "pyw bot_gui.py", 0, False
