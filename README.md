# ⌚ Apple Watch Health & Activity Dashboard

Apple Watch および iPhone ヘルスケアの生体データ・運動データ（8年分・600万件超）を安全かつ美しく可視化するモダンな PWA 対応 Web ダッシュボードです。

---

## 🌟 主な機能と特徴

- **🔒 クライアントサイド AES-256-GCM 暗号化**:
  - 個人生体データは強力な暗号化（PBKDF2 100,000回反復 + SHA-256 + AES-256-GCM）を施した状態で HTML 内に保持。
  - パスワード（初期値: `applehealth2026`）を入力した時のみブラウザ内（Web Crypto API）で復号されます。
  - GitHub Pages などのパブリックな場所で公開しても、パスワードを知らない第三者がデータを解読することは不可能です。
- **📊 豊富なヘルスケア指標 & インタラクティブ可視化**:
  - **概要 & 目標**: 生涯累計歩数、総距離（地球周回換算）、消費カロリー、1日歩数目標達成率ゲージ、睡眠目標ゲージ、年別推移表
  - **運動 & 歩数**: 月別1日平均歩数推移、活動カロリー＆運動回数、曜日別活動傾向（平日 vs 休日）、歩行安定性 / 非対称性（%）
  - **心拍 & バイタル**: 安静時心拍数 ＆ 心拍変動（HRV: SDNN）、血中酸素ウェルネス（SpO2 %）＆ VO2Max 推移
  - **睡眠 & ステージ**: 月別平均実睡眠時間（推奨基準ガイドライン付き）、睡眠ステージ内訳（深い睡眠 / コア / レム睡眠）
  - **ワークアウト**: 種目別内訳（ドーナツチャート）、全ワークアウト履歴（日付・種目検索＆フィルタ機能）
- **💾 データエクスポート機能**:
  - 復号された生データをワンクリックで JSON / CSV（月別サマリー・ワークアウト履歴）としてローカル保存可能。
- **📱 PWA & オフライン対応**:
  - ホーム画面に追加してネイティブアプリ感覚で利用可能。
  - Service Worker（`sw.js`）により、地下や電波の届かないオフライン環境でも瞬時に起動。

---

## 🔄 データ更新手順（Apple Health からの自動再生成）

iPhone のヘルスケアアプリからデータを書き出して、最新のダッシュボードを自動生成できます。

### 1. iPhone からデータを書き出す
1. iPhone の「**ヘルスケア**」アプリを開く
2. 右上の**プロフィールアイコン**をタップ
3. 画面最下部の「**すべてのヘルスケアデータを書き出す**」をタップ
4. 出力された `書き出し.zip`（または `export.zip`）を PC に転送する

### 2. スクリプトを実行する
リポジトリ直下の [`process_export.py`](file:///C:/Users/kentaro/.gemini/antigravity/scratch/apple-health-dashboard/process_export.py) を実行します（解凍不要で ZIP を直接指定できます）。

```bash
# 必要なライブラリのインストール
pip install cryptography

# ZIP ファイルから自動集計・暗号化して index.html を更新
python process_export.py -i export.zip -p "あなたのパスワード"
```

> [!TIP]
> パスワードを指定しない場合、初期パスワード（`applehealth2026`）が適用されます。

### 3. GitHub にプッシュする
```bash
git add index.html
git commit -m "update: Apple Health data synced"
git push origin main
```

---

## 🚀 GitHub Pages での公開手順（無料・1クリック）

1. このリポジトリをご自身の GitHub アカウントにプッシュします。
2. GitHub リポジトリの **Settings**（設定）タブを開きます。
3. 左メニューの **Pages** を選択します。
4. **Build and deployment** > **Source** で `Deploy from a branch` を選択します。
5. **Branch** で `main` / `/ (root)` を選択して **Save** をクリックします。
6. 数分後に発行される URL（`https://<username>.github.io/<repo-name>/`）にアクセスすれば、世界中どこからでも安全に閲覧できます！
