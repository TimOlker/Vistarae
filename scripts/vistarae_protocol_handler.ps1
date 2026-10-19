<#
.SYNOPSIS
    Handles vistarae-folder:// protocol URLs and opens Windows File Explorer.
.DESCRIPTION
    Receives raw URI from Chrome/Edge, strips protocol prefix, unescapes URL encoding,
    normalizes UNC or local drive path format, and launches explorer.exe.
#>

param(
    [Parameter(Position=0, Mandatory=$false)]
    [string]$RawUri = ""
)

if (-not $RawUri) {
    exit 0
}

try {
    # 1. Strip protocol scheme: "vistarae-folder://", "vistarae-folder:", etc.
    $uri = $RawUri -replace '^[a-zA-Z0-9_\-]+:\/{0,2}', ''

    # 2. URL-decode (handles %20 for spaces, %5C for backslashes, %27 for apostrophes, etc.)
    $decoded = [System.Uri]::UnescapeDataString($uri)

    # 3. Normalize path structure
    # Case A: UNC path starting with \\ or //
    if ($decoded -match '^[\\/]{2}(.+)$') {
        $folder = '\\' + ($matches[1] -replace '/', '\')
    }
    # Case B: Local drive letter like C:\path or C:/path or /C:/path
    elseif ($decoded -match '^[\\/]*([a-zA-Z]:.*)$') {
        $folder = $matches[1] -replace '/', '\'
    }
    # Case C: Bare IP address or hostname share (e.g. 192.168.2.50\homes\...)
    elseif ($decoded -match '^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}') {
        $folder = '\\' + ($decoded -replace '/', '\')
    }
    # Case D: Fallback replace forward slashes
    else {
        $folder = $decoded -replace '/', '\'
    }

    # Trim trailing slash unless it's a drive root like C:\
    if ($folder.Length -gt 3) {
        $folder = $folder.TrimEnd('\')
    }

    # 4. Launch Windows Explorer with quotes around folder path
    Start-Process "explorer.exe" -ArgumentList "`"$folder`""
}
catch {
    exit 1
}
