' Run bot silently with auto-update.
' Double-click: pulls latest code, installs deps, launches GUI without console window.
'
' Failures in pull/install are logged to setup.log but don't block bot launch —
' a stale-but-working bot is better than a black screen.

Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
logPath = folder & "\setup.log"

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = folder

' Force-sync to origin/main. Friend's PC never edits code, so a hard reset is
' simpler and safer than --ff-only (which gets permanently stuck on any conflict).
' Group both commands in (...) so fetch's output is also captured to the log.
shell.Run "cmd /c (git fetch origin && git reset --hard origin/main) > """ & logPath & """ 2>&1", 0, True

' Install/update dependencies. py -m pip works even when pip.exe isn't on PATH.
shell.Run "cmd /c py -m pip install -r requirements.txt >> """ & logPath & """ 2>&1", 0, True

' pythonw = no-console Python. python.org installer puts both pythonw and pyw on PATH;
' try pythonw first, fall back to pyw, and log any final error.
' Wait for the bot to exit so we can detect a startup-time crash and surface it.
exitCode = shell.Run("cmd /c (pythonw bot_gui.py || pyw bot_gui.py) 2>> """ & logPath & """", 0, True)
If exitCode <> 0 Then
    MsgBox "탄이 봇이 시작 중 문제가 발생했어요." & vbCrLf & vbCrLf & _
           "폴더 안의 setup.log 를 사장님께 보내주세요.", _
           vbExclamation, "탄이 봇"
End If
