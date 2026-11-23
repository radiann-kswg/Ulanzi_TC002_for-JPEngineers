<#
.SYNOPSIS
Checks a TC002 over HTTP; -Hello creates and displays a fixed test app.
.EXAMPLE
.\scripts\tc002-http.ps1 -DeviceIp 192.0.2.42
.EXAMPLE
.\scripts\tc002-http.ps1 -DeviceIp 192.0.2.42 -Hello -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ipaddress] $DeviceIp,
    [switch] $Hello,
    [switch] $DryRun
)

if ($DeviceIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $DeviceIp.GetAddressBytes()[0] -ge 224 -or $DeviceIp.ToString() -eq '0.0.0.0') {
    throw 'DeviceIp must be a unicast IPv4 address.'
}

$base = 'http://' + $DeviceIp.ToString()
$requests = @(
    @{ Method = 'Get'; Uri = "$base/getBase" }
    @{ Method = 'Get'; Uri = "$base/api/customList" }
)
if ($Hello) {
    $requests += @(
        @{
            Method = 'Post'; Uri = "$base/api/custom?name=tc002_dev_hello"
            ContentType = 'application/json'
            Body = '{"text":[{"content":"HELLO","fontHeight":10,"align":"center","valign":"middle","color":"#FFFFFF"}]}'
        }
        @{ Method = 'Post'; Uri = "$base/api/switchDiyApp?name=tc002_dev_hello" }
    )
}
if ($DryRun) {
    return $requests
}

foreach ($request in $requests) {
    $response = Invoke-RestMethod @request -TimeoutSec 10 -ErrorAction Stop
    if ($request.Method -eq 'Post' -and $null -ne $response -and
        $null -ne $response.PSObject.Properties['code'] -and [string]$response.code -ne '200') {
        throw "TC002 rejected $($request.Uri) (code=$($response.code))."
    }
    $response
}
