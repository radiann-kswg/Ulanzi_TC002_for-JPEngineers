# 同梱素材とビルド時の依存物

本プロジェクトのオリジナル部分の著作権は © 2026 TC002 Studio contributors に帰属します。ライセンスの適用範囲は [LICENSE](LICENSE) を参照してください。

## Windows 設定アプリの画像

`studio/assets/tc002.png` の時計イラストと `studio/assets/icon.png` のアプリアイコンは、本プロジェクトで描いたオリジナル素材です。Windows アプリと同じ MIT ライセンスで配布します。利用ガイドに掲載する設定画面は、例示用の接続先と設定値を使って撮影しています。

## 地図と住所検索

天気の地点選択画面は、国土地理院から標準地図（ズームレベル2～8）と淡色地図（9～18）を表示時に取得します。日本とその周辺を描く標準地図（5～8）の等深線と海岸線については、「広域図の出典」に配信元指定の表記を掲載しています。[地理院タイル一覧](https://maps.gsi.go.jp/development/ichiran.html)・[広域図の出典](studio/assets/map-credits.txt)・[国土地理院コンテンツ利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)

日本の住所検索には、国土地理院のサービスを通じて東京大学空間情報科学研究センターのジオコーディングを使用しています。[CSISシンプルジオコーディング実験を利用](https://geocode.csis.u-tokyo.ac.jp/)・[実験参加規約](https://geocode.csis.u-tokyo.ac.jp/home/simple-geocoding/simple-geocoding-tems-of-use/)

## 同梱するビットマップフォント

患者長ひっく氏の3書体を時計用に変換しています。配布するフォントデータにはそれぞれの著作権表示と SIL Open Font License 1.1 の全文を添付してください。

| データ | 元の書体と作者の配布元 | 同梱のライセンス |
| --- | --- | --- |
| `firmware/assets/denki.bin` | [でんきチップ](https://github.com/hicchicc/x8y12pxDenkiChip) | [著作権表示・OFL](firmware/assets/licenses/x8y12pxDenkiChip/OFL.txt) |
| `firmware/assets/nega.bin` | [ネガクリップ](https://github.com/hicchicc/x5y8pxNegaClip) | [著作権表示・OFL](firmware/assets/licenses/x5y8pxNegaClip/OFL.txt) |
| `firmware/assets/maru.bin` | [マルミーニャ](https://github.com/hicchicc/x12y12pxMaruMinya) | [著作権表示・OFL](firmware/assets/licenses/x12y12pxMaruMinya/OFL.txt) |

## オリジナルの効果音

`firmware/assets/audio/` の MP3 28点は、本プロジェクトが数式から合成した秒針・操作音、分の機械音、1〜11時を2進数で表す正時のメロディー17種（1〜11時の11曲と18〜23時の6曲。13〜17時は1〜5時と共通）、正午・午前0時のオリジナルメロディー、スクロール通知音、休憩・再開・アラーム音です。機器側ファームウェアと同じ GPL-3.0-or-later で配布します。ソースは [生成スクリプト](scripts/build-device.py) にあります。

設定アプリで `build/TC002Dev/resources/audio/` に取り込む標準効果音は利用者の TC002 に付属する音源です。実機または同じ時計のバックアップから読み出し、その時計の一時実行と個人用イメージで使用します。

効果音を作り直す開発者は、リポジトリのルートで次のコマンドを実行してください。配布版は `imageio-ffmpeg==0.6.0` 付属の FFmpeg 7.1 でエンコードしています。午前・午後の時報17曲は 24 kHz・モノラル・16 kbps の MP3 で同梱し、再生成時だけ中間 WAV を作ります。入力に実機の録音ファイルは必要ありません。

```powershell
$encoder = Read-Host "FFmpeg の実行ファイルのフルパス"
py -3.12 scripts/build-device.py --regenerate-audio $encoder
```

## 祝日データ

PC ブリッジは、時計のカレンダーと曜日配色に使う祝日を次の2か所から実行時に取得します。祝日データはこのリポジトリに同梱しません。時計には日付・UTC 時差・地域コード・祝日名だけを送ります。

| 対象 | 取得元 | 利用条件 |
| --- | --- | --- |
| 日本の祝日 | 内閣府「国民の祝日について」の CSV（`syukujitsu.csv`）。翌年分は例年2月に掲載されます。 | 内閣府ホームページの利用規約（公共データ利用規約 第1.0版）。出典：内閣府ホームページ「[国民の祝日について](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html)」・[利用規約](https://www.cao.go.jp/notice/rule.html) |
| 世界時計の代表地域の国民の祝日 | [Nager.Date](https://github.com/nager/Nager.Date)（ソフトウェアは MIT License、© 2016 nager.at）の公開 API（Nager.Holidays API v4）。種別が Public の全国祝日だけを使います。 | Nager.Holidays の利用規約では、Web API は私的・非営利の利用に限られ、商用利用にはスポンサー登録が必要です。可用性と正確性は保証されません。[利用規約](https://nagerholidays.com/legal/termsofservice)・[API](https://nagerholidays.com/api) |

## ビルド時に取得するソフトウェア

- 機器側アプリは Ulanzi の公式 Z21 サンプルに本プロジェクトのコードを組み込んでビルドします。公式サンプル本体には GPL-3.0-or-later、BlueZ や TomThumb などには上流が記載した各ライセンスが適用されます。[公式サンプルのライセンス](https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002/blob/677a3aa89784bcb0b3e5ffa6db954efa0ce880de/LICENSE)・[上流の第三者告知](https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002/blob/677a3aa89784bcb0b3e5ffa6db954efa0ce880de/THIRD_PARTY_NOTICES.md)
- FlyThings IDE、Z21 ツールチェーンと SDK パッケージは開発者が配布元から取得します。生成したバイナリや更新イメージを配布するときは、組み込んだ SDK、ライブラリ、機器由来の音源の条件と、対応するソースコードの提供方法を確認してください。[FlyThings](https://developer.flythings.cn/zh-hans/download.html)
- PC 側で導入する Python パッケージや外部ツールにはそれぞれの配布条件が適用されます。ソース配布には SDK、個人の設定、実機から取り出した音源、生成した更新イメージを含めません。
