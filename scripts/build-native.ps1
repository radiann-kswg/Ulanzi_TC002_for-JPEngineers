[CmdletBinding()]
param(
    [string] $IdeHome = $env:FLYTHINGS_HOME,
    [string] $Sample,
    [string] $Python,
    [switch] $Rebuild
)

$ErrorActionPreference = 'Stop'
if (-not $IdeHome) { throw 'Supply -IdeHome or set FLYTHINGS_HOME to the FlyThings installation directory.' }
# The standalone compiler always rebuilds the complete custom project, including with -Rebuild.
$arguments = @((Join-Path $PSScriptRoot 'build-device.py'), '--ide', $IdeHome)
if ($Sample) { $arguments += @('--sample', $Sample) }
if ($Python) {
    & $Python @arguments
} else {
    & py -3 @arguments
}
if ($LASTEXITCODE -ne 0) { throw "TC002Dev build failed (exit $LASTEXITCODE)." }
