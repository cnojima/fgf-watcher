<#
Runs a Python script in this project elevated (as Administrator), which the
game window requires — Windows blocks synthetic input (clicks/keys) from a
lower-integrity process to a higher-integrity (elevated) window (UIPI), and
this game runs elevated.

Usage:
    powershell -File run_admin.ps1 src\tracker.py config\regions.json
    powershell -File run_admin.ps1 src\calibrate.py shot "Foundation Galactic Frontier"

Triggers one UAC consent prompt per invocation (Windows requires this — it
cannot be scripted around, and it shouldn't be).
#>
param(
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$PythonExe = "C:\Users\cnoji\AppData\Local\Programs\Python\Python312\python.exe"
$ProjectDir = $PSScriptRoot

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    $argString = ($ScriptArgs | ForEach-Object { '"' + $_ + '"' }) -join ' '
    Start-Process -FilePath $PythonExe -ArgumentList $argString -Verb RunAs -WorkingDirectory $ProjectDir -Wait
} else {
    Push-Location $ProjectDir
    & $PythonExe @ScriptArgs
    Pop-Location
}
