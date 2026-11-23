$ErrorActionPreference = 'Stop'
$target = Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\tc002-http.ps1'
$calls = New-Object 'System.Collections.Generic.List[object]'
$scenario = 'ok'

function Assert([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
}

# Shadow the transport so every test stays offline.
function Invoke-RestMethod {
    param($Method, $Uri, $Body, $ContentType, $TimeoutSec, $ErrorAction)
    $calls.Add(@{ Method = $Method; Uri = $Uri; Body = $Body; ContentType = $ContentType; TimeoutSec = $TimeoutSec })
    if ($scenario -eq 'connection-error') { throw 'mock connection failure' }
    if ($Method -eq 'Post') {
        if ($scenario -eq 'post-error') { return [pscustomobject]@{ code = 400 } }
        if ($scenario -eq 'no-code') { return [pscustomobject]@{ message = 'accepted' } }
        return [pscustomobject]@{ code = 200; message = 'ok' }
    }
    return [pscustomobject]@{ appVer = 'V1.4.0'; mcuVer = 'T1.0.13' }
}

$plan = @(& $target -DeviceIp 192.0.2.1 -DryRun)
Assert ($plan.Count -eq 2) 'Default plan must contain two reads.'
Assert ($plan[0].Method -eq 'Get' -and $plan[0].Uri -eq 'http://192.0.2.1/getBase') 'Device read is incorrect.'
Assert ($plan[1].Method -eq 'Get' -and $plan[1].Uri -eq 'http://192.0.2.1/api/customList') 'App-list read is incorrect.'

$plan = @(& $target -DeviceIp 192.0.2.1 -Hello -DryRun)
Assert ($plan.Count -eq 4) 'Hello plan must contain two reads, creation, and switching.'
Assert ($plan[2].Method -eq 'Post' -and $plan[2].Uri -eq 'http://192.0.2.1/api/custom?name=tc002_dev_hello') 'Hello creation is incorrect.'
Assert ($plan[3].Method -eq 'Post' -and $plan[3].Uri -eq 'http://192.0.2.1/api/switchDiyApp?name=tc002_dev_hello') 'Hello switching is incorrect.'
$payload = $plan[2].Body | ConvertFrom-Json
Assert ($payload.text.Count -eq 1 -and $payload.text[0].content -eq 'HELLO' -and $payload.text[0].fontHeight -eq 10) 'Hello payload is incorrect.'
Assert ($plan[2].ContentType -eq 'application/json' -and $plan[2].Body -ne '{}') 'Creation must use nonempty JSON.'
Assert ($calls.Count -eq 0) 'DryRun must not contact the device.'

foreach ($invalid in @('0.0.0.0', '224.0.0.1', '239.255.255.250', '255.255.255.255', '::1', 'not-an-ip')) {
    $rejected = $false
    try { & $target -DeviceIp $invalid -DryRun | Out-Null } catch { $rejected = $true }
    Assert $rejected "Invalid address was accepted: $invalid"
}
Assert (@(& $target -DeviceIp 127.0.0.1 -DryRun).Count -eq 2) 'Loopback must remain available for local testing.'

$responses = @(& $target -DeviceIp 192.0.2.1)
Assert ($responses.Count -eq 2 -and $calls.Count -eq 2) 'Default execution must issue two reads.'
Assert (@($calls | Where-Object { $_.Method -ne 'Get' -or $_.TimeoutSec -ne 10 }).Count -eq 0) 'Default execution must stay read-only and bounded.'

$calls.Clear()
$responses = @(& $target -DeviceIp 192.0.2.1 -Hello)
Assert ($responses.Count -eq 4 -and $calls.Count -eq 4) 'Hello execution must issue four requests.'
Assert ($calls[2].Body -eq $plan[2].Body -and $calls[3].Uri -eq $plan[3].Uri) 'Hello execution must match its preview.'

$calls.Clear()
$scenario = 'post-error'
$rejected = $false
try { & $target -DeviceIp 192.0.2.1 -Hello | Out-Null } catch { $rejected = $_.Exception.Message -like '*code=400*' }
Assert ($rejected -and $calls.Count -eq 3) 'A rejected creation must stop before switching.'

$calls.Clear()
$scenario = 'connection-error'
$rejected = $false
try { & $target -DeviceIp 192.0.2.1 -Hello | Out-Null } catch { $rejected = $_.Exception.Message -eq 'mock connection failure' }
Assert ($rejected -and $calls.Count -eq 1) 'A transport failure must stop subsequent requests.'

$calls.Clear()
$scenario = 'no-code'
& $target -DeviceIp 192.0.2.1 -Hello | Out-Null
Assert ($calls.Count -eq 4) 'POST responses without a code field must be accepted.'

'PASS: TC002 HTTP plans, validation, read-only default, Hello, and error handling (offline).'
