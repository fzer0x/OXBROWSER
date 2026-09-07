Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

strPythonw = strPath & "\.venv\Scripts\pythonw.exe"
strMain = strPath & "\main.py"

If objFSO.FileExists(strPythonw) Then
    objShell.CurrentDirectory = strPath
    objShell.Run Chr(34) & strPythonw & Chr(34) & " " & Chr(34) & strMain & Chr(34), 0, False
Else
    MsgBox "Python virtual environment not found at: " & vbCrLf & strPythonw, vbCritical, "OXBROWSER Error"
End If
