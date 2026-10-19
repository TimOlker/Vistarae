' Vistarae Protocol Handler Silent Launcher
' Executes vistarae_protocol_handler.ps1 completely silently without console window flash

Set objShell = CreateObject("Wscript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objArgs = Wscript.Arguments

strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strLog = objFSO.BuildPath(strScriptDir, "debug_log.txt")

Set objLog = objFSO.OpenTextFile(strLog, 8, True)
objLog.WriteLine Now & " [VBS] Arg count: " & objArgs.Count

If objArgs.Count > 0 Then
    strArg = objArgs(0)
    objLog.WriteLine Now & " [VBS] Raw arg 0: " & strArg
    strPsScript = objFSO.BuildPath(strScriptDir, "vistarae_protocol_handler.ps1")
    
    If objFSO.FileExists(strPsScript) Then
        ' Notice: escape any double quotes in strArg
        strSafeArg = Replace(strArg, """", "\""")
        strCmd = "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File """ & strPsScript & """ """ & strSafeArg & """"
        objLog.WriteLine Now & " [VBS] Executing: " & strCmd
        intRet = objShell.Run(strCmd, 0, True)
        objLog.WriteLine Now & " [VBS] Return code: " & intRet
    Else
        objLog.WriteLine Now & " [VBS] Script not found: " & strPsScript
    End If
Else
    objLog.WriteLine Now & " [VBS] No arguments passed!"
End If
objLog.Close
