# TC002 に Wi-Fi で常設する

Windows PC と TC002 を同じ LAN に接続し、時計を USB 電源につなぎます。標準アプリ **1.1.4** で確認した方法です。時計が PC からアプリ用の `update.img` を取得して書き込み、自動再起動します。TF カードは不要です。

## 1. 時計とイメージを確認する

標準アプリから一時実行を始めた時計は、通常再起動で標準アプリに戻ります。すでに独自アプリを常設した時計では、通常再起動でも独自アプリが起動します。この手順が使えるのは、標準アプリの更新 API が動作しているときです。

PowerShell を開き、時計の「4 - Tools → IP Address」で確認した IPv4 アドレスを入力します。

```powershell
$clockIp = Read-Host '時計の IPv4'
$device = Invoke-RestMethod -Uri "http://$clockIp/getBase" -TimeoutSec 5
$device | Select-Object ip, appVer, mcuVer
```

表示された `ip` が対象の時計で、`appVer` が `1.1.4` であることを確認します。PC に空のフォルダーを用意し、同じビルドで一時実行を確認した TC002Dev の Image Build 出力 `update.img` だけを入れます。次のコマンドはこのフォルダーを一時的に LAN に公開します。PC の IPv4 は `ipconfig` で確認できます。

```powershell
$imageDir = Read-Host 'update.img だけを置いたフォルダーのパス'
$image = Get-Item -LiteralPath (Join-Path $imageDir 'update.img') -ErrorAction Stop
$pcIp = Read-Host '時計と同じ LAN に接続している PC の IPv4'
$port = 8765
$url = "http://${pcIp}:$port/update.img"
Get-FileHash -Algorithm SHA256 -LiteralPath $image.FullName
```

2026年11月25日に実機確認したイメージは 1,401,404 バイト、SHA-256 は `abd7b1f97311441db8cac91ff9b0db82db4b3cb4c3b7bb5b9c0ecf18e918d482` です。別のビルドには、そのビルド自身のハッシュを使います。

## 2. 更新を送信する

同じ PowerShell で次を実行します。別ウィンドウが開いてファイルの配信を開始します。更新後の確認が終わるまで開いておきます。

```powershell
Start-Process -FilePath py -WorkingDirectory $image.DirectoryName -ArgumentList "-3.12 -m http.server $port --bind $pcIp"
```

元の PowerShell で次を実行すると書き込みが始まります。時計の給電を維持してください。標準アプリ 1.1.4 は `downloadUrl`、`md5`、`size` を **`app` の中**に受け取ります。MCU の更新項目は送りません。

```powershell
$served = Invoke-WebRequest -UseBasicParsing -Method Head -Uri $url -TimeoutSec 5 -ErrorAction Stop
if ([long]($served.Headers['Content-Length'] -join '') -ne $image.Length) { throw '配信ファイルのサイズが一致しません。' }
$body = @{
    app = @{
        downloadUrl = $url
        md5 = (Get-FileHash -Algorithm MD5 -LiteralPath $image.FullName).Hash.ToLowerInvariant()
        size = $image.Length
    }
} | ConvertTo-Json -Depth 3
$reply = Invoke-RestMethod -Method Post -Uri "http://$clockIp/update" -ContentType 'application/json' -Body $body
if ($reply.code -ne 200) { throw "時計が更新を受理しませんでした。$($reply.message)" }
$reply.message
```

本文の `code: 200` と `OTA update started` が受付の合図です。配信ウィンドウに時計からの `GET /update.img` と `200` が出たら、自動再起動を待ちます。受付後に応答が途切れた場合も、再送する前に時計の画面と次の手順で起動状態を確認します。

## 3. 自動再起動後に常設を確認する

独自時計が起動し、Wi-Fi に再接続したら、同じ PowerShell で常設ライブラリを読み戻します。同じイメージを作成したビルドの `Release/libzkgui.so` を比較元に指定します。

```powershell
$adb = Read-Host 'FlyThings の adb.exe のフルパス'
$built = Read-Host 'このイメージに含めた Release/libzkgui.so のフルパス'
$serial = "${clockIp}:5555"
$copy = New-TemporaryFile
try {
    & $adb connect $serial
    & $adb -s $serial pull /res/lib/libzkgui.so $copy.FullName
    if ($LASTEXITCODE -ne 0) { throw '常設アプリを読み戻せませんでした。' }
    if ((Get-FileHash $copy.FullName).Hash -ne (Get-FileHash -LiteralPath $built).Hash) {
        throw '時計のアプリが指定したビルドと一致しません。'
    }
    $state = & $adb -s $serial shell 'getprop sys.zkapp.state'
    if ($LASTEXITCODE -ne 0 -or "$state".Trim() -ne 'running') { throw 'アプリの起動を確認できませんでした。' }
    '常設ライブラリの SHA-256 が一致し、時計アプリは running です。'
} finally {
    Remove-Item -LiteralPath $copy.FullName
}
```

`running` とハッシュの一致を確認したら、配信ウィンドウで **Ctrl+C** を押して閉じます。時計を通常再起動しても独自時計が起動し、「接続と表示」で起動した PC ブリッジから天気や開発情報を再び受信できます。

標準アプリに戻す場合、Ulanzi は USB-C 横の復旧ボタンを押したまま電源を入れる手順を案内しています。[TC002 の公式復旧案内](https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002/blob/677a3aa89784bcb0b3e5ffa6db954efa0ce880de/README_EN.md)・[標準アプリの OTA API](https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002/blob/677a3aa89784bcb0b3e5ffa6db954efa0ce880de/protocol/Ulanzi_TC002_protocol-http-mqtt_CN.md)
