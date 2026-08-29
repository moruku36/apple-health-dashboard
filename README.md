# ⌚ Apple Watch Health & Activity Dashboard

Apple Watch およびヘルスケアの生体データ・運動データ（約8年分・600万件超）を可視化するセキュアなWebダッシュボードです。

## 🔒 セキュリティとプライバシー保護
このダッシュボードは、個人生体データ保護のために **クライアントサイド AES-256-GCM 暗号化** を採用しています。
- データは強力な暗号で暗号化された状態でHTML内に保持されています。
- 正しいパスワードを入力した時のみ、ブラウザ（Web Crypto API）内で安全に復号されます。
- GitHub 上でソースコードが公開されても、パスワードを知らない第三者がデータを解読することは不可能です。

### 初期パスワード
- **`applehealth2026`**

---

## 🚀 GitHub Pages での公開手順（1クリック）

1. このリポジトリを GitHub にプッシュします。
2. GitHub リポジトリの **Settings**（設定）タブを開きます。
3. 左メニューの **Pages** を選択します。
4. **Build and deployment** > **Source** で `Deploy from a branch` を選択します。
5. **Branch** で `main`（または `master`）/ `/ (root)` を選択して **Save** をクリックします。
6. 数分後に発行される URL（`https://<username>.github.io/<repo-name>/`）にアクセスすれば、世界中どこからでもスマートフォンやPCで安全にダッシュボードを閲覧できます！
