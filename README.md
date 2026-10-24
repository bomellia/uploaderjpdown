# uploader.jp Backup Tool (Windows, preview)

uploader.jp の一般公開アップローダーを巡回し、パスワード不要のファイルを通常のダウンロード操作で**1件ずつ**保存する非公式のバックアップツールです。アップロードした本人である必要はありませんが、取得・利用に関する権限と利用規約の遵守が必要です。

> **開発中の試作版**: 実際のuploader.jpに対するエンドツーエンドテスト、およびWindows上のEXE動作確認は未完了です。重要なファイルは手動でも取得・照合してください。

## 対象と仕様

- `https://uu.getuploader.com/<name>/`、`https://ux.getuploader.com/<name>/`、`https://u1.getuploader.com/<name>/` などの `u数字.getuploader.com` サブドメインに対応。
- 一覧ページを自動巡回し、ファイルIDにより重複除去。
- Microsoft Edge をヘッドレス起動して通常のダウンロードボタンを操作。内部APIや認証回避手段は使用しません。
- 既定3秒以上のアクセス間隔、同時ダウンロード1件。
- 中断後も `manifest.json` に記録された完了ファイルをSHA-256とサイズで検証してスキップ。
- 同名ファイルは `ファイルID_ファイル名` で区別。既存ファイルを上書きしません。
- 403/429/503やCAPTCHAなどのアクセス制限を検出した際は停止します。

## 対応しないもの

ファイルダウンロードパスワード、閲覧パスワード、CAPTCHA解除、非公開コンテンツ、他ドメインのアップローダー。サイト仕様の違い・変更により取得できない場合があります。

## Windowsで開発版を起動

必要環境：Windows 10/11、Python 3.10以降、Microsoft Edge。

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

1. 公開アップローダーのURLと既存の保存先フォルダーを入力します。
2. 利用規約・権利関係を確認し、チェックを入れます。
3. 「一括ダウンロード開始」を押します。
4. 保存先の `<アップローダー名>` フォルダーにファイルと `manifest.json` が作成されます。
5. 停止・エラー後は同じURL/保存先で再実行してください。

## EXEのビルド

Windows上で `build_windows.bat` を実行すると `dist/uploaderjp-backup.exe` を作成します。Microsoft EdgeはEXEに同梱しません。PyInstallerによるプレビュー用ビルドで、署名・実機テストは未実施です。

GitHub上では **Actions → Build Windows preview (manual) → Run workflow** から、署名なしEXEをテスト用artifactとして生成できます。公開Releaseには自動配布しません。

## テストと開発

```powershell
python -m unittest discover -s tests -v
```

GitHub ActionsはWindows/Linux・Python 3.11/3.13で上記のネットワーク不要な単体テストを実行します。公開前の作業は [docs/ROADMAP.md](docs/ROADMAP.md) を参照してください。

## 負荷・権利・セキュリティについて

- uploader.jpは同時ダウンロードを避けるようFAQで案内しています（https://uploader.jp/faq/）。
- 公開されているファイルでも、著作権や再配布の許可とは別です。必要な権利を確認してください。
- サイトが制限したアクセスを回避・強制再試行しません。
- ダウンロードしたファイルには実行ファイルや未知のコンテンツが含まれる可能性があります。安易に開かず、必要に応じてスキャンしてください。
- アプリはuploader.jp公式のツールではありません。
- 開発用ソースのライセンスと公開範囲は正式リリース前に決定します。

## サービス終了

uploader.jpは2026年11月25日23:59に全データを削除する予定と告知しています（https://uu.getuploader.com/news/）。公開前の実機検証は早急に行う必要があります。
