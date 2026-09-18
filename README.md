# わんカフェわんランマップ

全国のドッグラン・ドッグカフェを地図で探し、目印をタップするとわんちゃんの写真・動画が見られるアプリです。

## 中身

| ファイル | 役割 |
|---|---|
| `index.html` | アプリの画面 |
| `data.js` | 施設データ（下の手順で自動作成） |
| `tools/fetch_osm.py` | OpenStreetMap から全国のドッグラン・ドッグカフェを取得 |
| `tools/featured.json` | 調査済みスポット（大阪・兵庫・京都・奈良）と、埋め込む動画・投稿の一覧 |
| `tools/build_data.py` | 上の2つを合わせて `data.js` を作成（位置・住所の補完、動画が見られるかの確認） |

## データの更新

```
cd tools
..\..\.venv\Scripts\python.exe fetch_osm.py
..\..\.venv\Scripts\python.exe build_data.py
```

調査済みスポットを増やすときは `featured.json` に追記してから `build_data.py` を実行します。

## 費用

すべて無料のサービスのみ使用（国土地理院の地図・住所検索、OpenStreetMap、YouTube/Instagram の公式埋め込み、GitHub Pages）。

## 注意

- YouTube の埋め込みは、ファイルをダブルクリックで開いた状態では再生されません（YouTube側の仕様）。公開先のページか、手元の簡易サーバーで開いてください。
- 施設データは OpenStreetMap の登録情報のため、登録漏れ・閉店の反映漏れがあります。
