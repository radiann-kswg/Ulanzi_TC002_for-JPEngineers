# TC002 に Wi-Fi で常設する

Windows PC と TC002 を同じ LAN に接続し、時計を USB 電源につなぎます。標準アプリ **1.1.4** で確認した方法です。時計が PC からアプリ用の `update.img` を取得して書き込み、自動再起動します。TF カードは不要です。

## 1. 時計とイメージを確認する

標準アプリが動いている間に「OS セットアップ」の「時計から標準効果音を取り込む」を実行してから Image Build します。以前の更新で音が変わった時計では、「バックアップから取り込む」で同じ時計の `ui/audio` フォルダーを選びます。画面には取り込んだ数と読み出し元に欠けているファイル名が出ます。以前取り込んだ音源は、読み出し元に同名のファイルがあるときだけ更新されます。

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

2026年11月25日に標準効果音を復元した個人用イメージは 1,450,556 バイト、SHA-256 は `96e356130ddf7586d581708198d4e178dfd700169770d1c2c71a38ecc21d0514` です。一時実行で秒針・ボタン・モード切替・ノブ回転の4音の再生完了を確認しました。常設更新と自動再起動の後、稼働中のライブラリをビルドと照合し、標準音源8点を同じ時計の更新前バックアップと照合しました。別のビルドには、そのビルド自身のハッシュを使います。

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

<a id="resident-ota"></a>

## 独自時計がすでに常設されている場合（開発者向け）

独自時計には標準アプリの `POST /update` がありません。実機での2回目以降の更新では、Wi-Fi ADB でイメージを RAM に転送し、一時実行用のアプリから FlyThings の `UpgradeMonitor` に渡しました。TF カードも工場復元も不要です。[FlyThings のネットワーク更新手順](https://developer.flythings.cn/zh-hans/remote_update.html)

1. 常設したいビルドの `update.img` と `Release/libzkgui.so` を PC に保管します。別の作業コピーで一時実行用アプリを準備します。`firmware/mainLogic.cc` に `#include "os/UpgradeMonitor.h"` を加え、既存の `onUI_Timer` を次に置き換えます。

   ```cpp
   static bool onUI_Timer(int) {
       const char* dir = "/mnt/extsd/tc002-stock-tick";
       if (rename("/mnt/extsd/tc002-stock-tick/armed",
                  "/mnt/extsd/tc002-stock-tick/received") == 0) {
           UpgradeMonitor::getInstance()->checkUpgradeFile(dir);
       }
       update();
       return true;
   }
   ```

2. この作業コピーで ARM ビルドを行い、「時計で一時実行」で起動します。下の PowerShell では `$adb` に SDK の `adb.exe`、`$serial` に対象の `IPv4:5555`、`$image` に最初に保管した常設用イメージの `Get-Item` 結果を指定します。転送先は起動ごとに消える専用ディレクトリです。

   ```powershell
   $dir = '/mnt/extsd/tc002-stock-tick'
   & $adb connect $serial
   $made = & $adb -s $serial shell "mkdir $dir && echo READY"
   if ("$made".Trim() -ne 'READY') { throw '新しい転送先を作れませんでした。既存の更新状態を確認してください。' }
   & $adb -s $serial push $image.FullName "$dir/update.img"
   if ($LASTEXITCODE -ne 0) { throw 'イメージの転送に失敗しました。' }
   $check = New-TemporaryFile
   try {
       & $adb -s $serial pull "$dir/update.img" $check.FullName
       if ($LASTEXITCODE -ne 0 -or (Get-FileHash $check.FullName).Hash -ne (Get-FileHash $image.FullName).Hash) {
           throw '転送したイメージを照合できませんでした。'
       }
   } finally {
       Remove-Item -LiteralPath $check.FullName
   }
   ```

3. 照合が済んだら給電を維持し、次の1行で更新を開始します。SDK が検査・書き込みを行って自動再起動します。前節の手順3で、最初に保管した**常設用**ライブラリと照合してください。

   ```powershell
   & $adb -s $serial shell "cd $dir && echo 3 > zkautoupgrade && touch armed"
   ```
