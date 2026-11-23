[CmdletBinding()]
param(
    [string] $IdeHome = $env:FLYTHINGS_HOME,
    [string] $Workspace = (Join-Path (Split-Path $PSScriptRoot -Parent) 'flythings-workspace')
)

$ErrorActionPreference = 'Stop'
if (-not $IdeHome) { throw 'Supply -IdeHome or set FLYTHINGS_HOME to the FlyThings installation directory.' }
$ide = Join-Path $IdeHome 'bin/ide.exe'
if (-not (Test-Path -LiteralPath $ide -PathType Leaf)) {
    throw "FlyThings IDE is missing at $ide"
}
Start-Process -FilePath $ide -ArgumentList "-data `"$Workspace`" -nl en" -WindowStyle Normal
