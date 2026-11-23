[CmdletBinding()]
param([Parameter(Mandatory)][ipaddress]$DeviceIp,
      [string]$IdeRoot = $env:FLYTHINGS_HOME, [switch]$CheckLiveFeed,
      [switch]$DeveloperPreview)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $IdeRoot) {
    $savedPaths = Join-Path $root 'build/studio-paths.json'
    if (Test-Path -LiteralPath $savedPaths -PathType Leaf) {
        $IdeRoot = (Get-Content -LiteralPath $savedPaths -Raw -Encoding UTF8 | ConvertFrom-Json).ide
    }
}
if (-not $IdeRoot) { throw 'Specify -IdeRoot or save the IDE folder in the Windows settings app.' }
$out = Join-Path $root 'build/native-tests'
New-Item -ItemType Directory -Force $out | Out-Null
$compiler = Join-Path $IdeRoot 'sdk/toolchains/z21/bin/arm-pc-linux-gnueabihf-g++.exe'
$adb = Join-Path $IdeRoot 'sdk/platform-tools/adb/adb.exe'
$serial = "$($DeviceIp):5555"
& $adb connect $serial
if ($LASTEXITCODE) { throw 'ADB connection failed' }
$suites = @(Get-ChildItem -LiteralPath "$PSScriptRoot/native" -Filter '*.cpp')
if ($CheckLiveFeed) { $suites += Get-Item -LiteralPath "$PSScriptRoot/system/live_feed.cpp" }
if ($DeveloperPreview) { $suites += Get-Item -LiteralPath "$PSScriptRoot/system/developer_preview.cpp" }
foreach ($test in $suites) {
    $exe = Join-Path $out $test.BaseName
    & $compiler -std=c++11 -O2 -Wall -Wextra -Werror -Wno-psabi -I "$root/build/TC002Dev/src/tc" $test.FullName -o $exe
    if ($LASTEXITCODE) { throw "Compile failed: $($test.Name)" }
    $remote = "/tmp/tc002-check-$($test.BaseName)"
    & $adb -s $serial push $exe $remote
    if ($LASTEXITCODE) { throw "Upload failed: $($test.Name)" }
    # The factory adbd uses the legacy shell protocol. Check a success marker.
    $result = & $adb -s $serial shell "chmod 700 $remote && $remote && echo TC002_PASS"
    if ($LASTEXITCODE -or (($result -join ' ').Trim() -ne 'TC002_PASS')) {
        throw "Test failed: $($test.Name) $result"
    }
    Write-Host "PASS $($test.Name) (ARM)"
}
if ($DeveloperPreview) {
    & $adb -s $serial pull /tmp/tc002-views.rgb (Join-Path $out 'developer-preview.rgb')
    if ($LASTEXITCODE) { throw 'Reading the preview frames failed.' }
}
