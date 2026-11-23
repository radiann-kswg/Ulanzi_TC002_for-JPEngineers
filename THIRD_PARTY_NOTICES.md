# 同梱素材とビルド時の依存物

TC002 Studio のオリジナル部分の著作権は © 2026 TC002 Studio contributors に帰属します。ライセンスの適用範囲は [LICENSE](LICENSE) を参照してください。

## 同梱するビットマップフォント

患者長ひっく氏の3書体を時計用に変換しています。配布するフォントデータにはそれぞれの著作権表示と SIL Open Font License 1.1 の全文を添付してください。

| データ | 元の書体と作者の配布元 | 同梱のライセンス |
| --- | --- | --- |
| `firmware/assets/denki.bin` | [でんきチップ](https://github.com/hicchicc/x8y12pxDenkiChip) | [著作権表示・OFL](firmware/assets/licenses/x8y12pxDenkiChip/OFL.txt) |
| `firmware/assets/nega.bin` | [ネガクリップ](https://github.com/hicchicc/x5y8pxNegaClip) | [著作権表示・OFL](firmware/assets/licenses/x5y8pxNegaClip/OFL.txt) |
| `firmware/assets/maru.bin` | [マルミーニャ](https://github.com/hicchicc/x12y12pxMaruMinya) | [著作権表示・OFL](firmware/assets/licenses/x12y12pxMaruMinya/OFL.txt) |

## オリジナルの効果音

`firmware/assets/audio/` の MP3 10点は、本プロジェクトが数式から合成した秒針、ノブ、ボタン、決定、分・時・日付の時報、休憩、再開、アラームの効果音です。機器側ファームウェアと同じ GPL-3.0-or-later で配布します。ソースは [生成スクリプト](scripts/build-device.py) にあります。

効果音を作り直す開発者は、リポジトリのルートで次のコマンドを実行してください。配布版は `imageio-ffmpeg==0.6.0` 付属の FFmpeg 7.1 でエンコードしています。入力に実機の録音ファイルは必要ありません。

```powershell
$encoder = Read-Host "FFmpeg の実行ファイルのフルパス"
py -3.12 scripts/build-device.py --regenerate-audio $encoder
```

## ビルド時に取得するソフトウェア

- 機器側アプリは Ulanzi の公式 Z21 サンプルに本プロジェクトのコードを組み込んでビルドします。公式サンプル本体には GPL-3.0-or-later、BlueZ や TomThumb などには上流が記載した各ライセンスが適用されます。[公式サンプルのライセンス](https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002/blob/677a3aa89784bcb0b3e5ffa6db954efa0ce880de/LICENSE)・[上流の第三者告知](https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002/blob/677a3aa89784bcb0b3e5ffa6db954efa0ce880de/THIRD_PARTY_NOTICES.md)
- FlyThings IDE、Z21 ツールチェーンと SDK パッケージは開発者が配布元から取得します。生成したバイナリや更新イメージを配布するときは、組み込んだ SDK、ライブラリ、機器由来の音源の条件と、対応するソースコードの提供方法を確認してください。[FlyThings](https://developer.flythings.cn/zh-hans/download.html)
- PC 側で導入する Python パッケージや外部ツールにはそれぞれの配布条件が適用されます。ソース配布には SDK、個人の設定、実機から取り出した音源、生成した更新イメージを含めません。
