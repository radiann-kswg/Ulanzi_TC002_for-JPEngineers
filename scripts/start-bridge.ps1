[CmdletBinding()]
param([string]$Python, [switch]$Stop, [switch]$Status)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state = Join-Path $project 'build/bridge'
$pidFile = Join-Path $state 'runner.pid'
# A per-checkout marker also guards against Windows reusing a stale process ID.
$config = Join-Path $project 'bridge/local.json'
if (Test-Path -LiteralPath $pidFile) {
    $savedPid = [int](Get-Content -LiteralPath $pidFile -Raw)
    $worker = Get-CimInstance Win32_Process -Filter "ProcessId = $savedPid"
    if ($worker -and $worker.CommandLine -like '*-m bridge --config*' -and $worker.CommandLine.Contains($config)) {
        if ($Stop) {
            Set-Content -LiteralPath (Join-Path $state "stop-$savedPid") -Value 'stop'
            Wait-Process -Id $savedPid -Timeout 45 -ErrorAction SilentlyContinue
            if (Get-Process -Id $savedPid -ErrorAction SilentlyContinue) { Write-Output 'Finishing current requests.' }
            else { Write-Output 'PC bridge stopped.' }
        }
        else { Write-Output "PC bridge already running (PID $savedPid)." }
        return
    }
}
if ($Stop) { Write-Output 'PC bridge is stopped.'; return }
if ($Status) { Write-Output 'PC bridge is stopped.'; return }
New-Item -ItemType Directory -Force -Path $state | Out-Null
if (-not $Python) {
    $Python = (& py -3.12 -c 'import sys; print(sys.executable)')
    if ($LASTEXITCODE -ne 0 -or -not $Python) { throw 'Specify -Python with the Python 3.12 executable.' }
}
$worker = Start-Process -FilePath $Python -ArgumentList ('-u -m bridge --config "'+$config+'" run') `
    -WorkingDirectory $project -RedirectStandardOutput (Join-Path $state 'runner.log') `
    -RedirectStandardError (Join-Path $state 'runner.err') -WindowStyle Hidden -PassThru
Start-Sleep -Milliseconds 1200
$worker.Refresh()
if ($worker.HasExited) {
    throw 'Bridge startup failed. See build/bridge/runner.err for details.'
}
Set-Content -LiteralPath $pidFile -Value $worker.Id
Write-Output "PC bridge started (PID $($worker.Id))."
