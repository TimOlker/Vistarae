<#
.SYNOPSIS
    Registers the vistarae-folder:// URL protocol in the current user's registry (HKCU).
.DESCRIPTION
    No administrator privileges are required. This associates vistarae-folder:// URLs with
    VistaraeFolderOpener.exe to launch Windows File Explorer directly from the browser.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExeHandler = Join-Path $ScriptDir "VistaraeFolderOpener.exe"
$CsSource = Join-Path $ScriptDir "VistaraeFolderOpener.cs"
$CscPath = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

# Compile if binary is missing
if (-not (Test-Path $ExeHandler) -and (Test-Path $CsSource) -and (Test-Path $CscPath)) {
    Write-Host "Compiling native VistaraeFolderOpener.exe..." -ForegroundColor Cyan
    & $CscPath /target:winexe /optimize /out:"$ExeHandler" "$CsSource" | Out-Null
}

if (Test-Path $ExeHandler) {
    $CommandStr = "`"$ExeHandler`" `"%1`""
} else {
    $PsHandler = Join-Path $ScriptDir "vistarae_protocol_handler.ps1"
    $CommandStr = "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File `"$PsHandler`" `"%1`""
}

$RegKey = "HKCU:\Software\Classes\vistarae-folder"
$ShellKey = "$RegKey\shell\open\command"

try {
    if (-not (Test-Path $RegKey)) {
        New-Item -Path $RegKey -Force | Out-Null
    }
    Set-ItemProperty -Path $RegKey -Name "(Default)" -Value "URL:Vistarae Folder Protocol"
    Set-ItemProperty -Path $RegKey -Name "FriendlyTypeName" -Value "Vistarae Folder Opener"
    Set-ItemProperty -Path $RegKey -Name "URL Protocol" -Value ""

    if (-not (Test-Path $ShellKey)) {
        New-Item -Path $ShellKey -Force | Out-Null
    }
    Set-ItemProperty -Path $ShellKey -Name "(Default)" -Value $CommandStr

    if (Test-Path $ExeHandler) {
        $AppKey = "HKCU:\Software\Classes\Applications\VistaraeFolderOpener.exe"
        if (-not (Test-Path $AppKey)) {
            New-Item -Path $AppKey -Force | Out-Null
        }
        Set-ItemProperty -Path $AppKey -Name "FriendlyAppName" -Value "Vistarae Folder Opener"
    }

    Write-Host "Successfully registered 'vistarae-folder://' protocol in HKCU." -ForegroundColor Green
    Write-Host "Handler executable: $CommandStr" -ForegroundColor DarkGray
} catch {
    Write-Error "Failed to register protocol: $_"
    exit 1
}
