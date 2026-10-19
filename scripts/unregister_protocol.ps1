<#
.SYNOPSIS
    Unregisters the vistarae-folder:// URL protocol from HKCU.
#>

$RegKey = "HKCU:\Software\Classes\vistarae-folder"

if (Test-Path $RegKey) {
    Remove-Item -Path $RegKey -Recurse -Force
    Write-Host "Successfully unregistered 'vistarae-folder://' protocol." -ForegroundColor Green
} else {
    Write-Host "'vistarae-folder://' protocol is not currently registered." -ForegroundColor Yellow
}
