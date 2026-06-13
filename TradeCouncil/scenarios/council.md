# シナリオ: 意思決定会議(council)

利用者(オーナー)が**唯一の決裁権者**として参加する同期意思決定会議のプロトコル。
TradeCouncil の運用ポリシー(リスク上限・レバレッジ・ゲート基準など)を審議し、
利用者の決裁宣言によって `config/policies/` に決裁済みポリシーを生成する。

> 根拠文書: `docs/03_運営規程・第0回アジェンダ.md`(式次第・アジェンダ・決裁レコード必須項目)
> および `docs/02_基本設計書.md` §1.5(ガバナンス設計)。**開始前に必ず docs/03 を読むこと。**

---

## このシナリオが扱う会議

| 種別 | 兆候となる言葉 | アジェンダの出どころ |
|---|---|---|
| **第0回(キックオフ)** | 「第0回」「キックオフ」「初期ポリシー」 | docs/03 第5章(P-01〜P-12 のたたき台つき) |
| 月次戦略会議 | 「月次会議」「ポリシー見直し」 | review_after 到来ポリシー + 利用者の議題 |
| 臨時 | 「臨時会議」「この件を決裁したい」+議題 | 利用者の議題 / 決裁キュー(`tc approve` 待ちの提案) |

> 一般的な相談・賛否の議論は **合議(deliberation)** が適切。
> この会議は「**ポリシーとして決裁し、システムに反映する**」ことが目的の時に使う。

## 使用するペルソナ(MAGI 3人格ではなく以下の5名)

`.claude/agents/` の: `macro_analyst` / `momentum_trader` / `contrarian_value` /
`quant_validator` / `risk_manager`(veto = 審議差し戻しを持つ。決裁の代替ではない)

召喚作法・バックエンド振り分け(claude / openai / gemini)・メディア入力は
CLAUDE.md の共通作法に従う(MAGI 人格と同じ仕組みで動く)。

## 役割(docs/03 第2章)

- **利用者** = 決裁権者(議長)。承認 / 修正承認 / 却下 / 会議差し戻し / 期限付き保留を宣言できる
- **ファシリテーター(あなた)** = 進行・論点整理・決議案の起草・書記。**決定はしない**
- **ペルソナ5名** = 審議・意見・反論。決定はしない

---

## 進行(docs/03 第3章 式次第)

### Round 0: 会議パッケージの提示

1. `docs/03_運営規程・第0回アジェンダ.md` を読む(第0回なら第5章のアジェンダ表)
2. `python -m scripts.cli status` と `python -m scripts.cli policy list` を実行し、
   現在のポリシー状態・システム状態を会議パッケージに含める
3. 利用者に提示する: 議題一覧(★必須を明示)/ 各議題のたたき台 / 主な論点 /
   審議対象の提案(`proposals` キューにあれば)
4. 進め方を確認する(第0回の場合):「★4件(P-01〜P-04)だけ決裁すればペーパー稼働を
   開始できます。全12件をやるか、★4件に絞るか、どちらにしますか?」

### 議題ごとに以下を繰り返す

**Round 1: ペルソナ意見(並列・独立)**
- 5名を並列召喚。互いの意見は見せない(独立視点の確保)
- 召喚プロンプトに含める: 議題 / たたき台の値 / docs/03 の論点 / 現在のシステム状態 /
  ラウンド番号と出力形式(意見 + 推奨値 + 根拠 + リスク + 確信度)

**Round 2: 相互反論(1回)**
- 全員の意見を共有し、各自1回だけ反論・補強・修正
- risk_manager はここで veto を行使できる(理由と代替案つき)。veto された案は
  そのまま決裁にかけず、修正するか論点として利用者に提示する

**Round 3: 利用者質疑**
- 利用者は自由に深掘り・追加シナリオの検討を指示できる。指示があれば該当ペルソナを再召喚

**Round 4: 選択肢の確定**
- ファシリテーターが「案A / 案B / 保留」の形に整理し、各案の根拠とリスクを要約する
- ペルソナの意見の対立点は消さずに併記する(丸めない)

**Round 5: 決裁宣言**
- 利用者が宣言する: 承認 / 修正承認(値を指定)/ 却下 / 差し戻し / 期限付き保留

**Round 6: 決裁レコードの生成と適用(書記)**
1. 決裁レコード YAML を起草する(下の形式)。`decided_at` は現在時刻(JST)
2. **読み上げて利用者の最終確認を得る**
3. 確認後、一時ファイルに保存して実行する(これが**唯一の適用経路**):
   ```
   python -m scripts.cli policy record --file <一時ファイル.yaml>
   ```
4. `python -m scripts.cli policy sync` で実行用ビューを再生成する
5. 結果(policy_id / version / status)を利用者に報告する

### 閉会

1. 議事録を `workspace/council/<日付>-<会議名>.md` に保存する
   (全ラウンドの発言・決裁事項・保留事項。冒頭に各ペルソナの backend/model を明記)
   - 議事録(`council/*.md`)は監査テキストとして**開発機で git コミットする**
     (本番は push しない。開発機からの閲覧経路 — ADR-0005)。
     機微情報(APIキー・残高の生値等)は本文に書かない
2. `python -m scripts.cli council log --session-id <id> --kind <kickoff|monthly|adhoc> --minutes <議事録パス>`
   で council_sessions に開催記録を残す
3. **★P-01〜P-04 がすべて active になった場合**は明示的に報告する:
   「fail-closed が解除されました。`python -m scripts.cli paper --bot dummy_rw` でペーパー稼働を開始できます」
4. 未決裁の議題は次回(週次/月次)へ持ち越すことを確認する

---

## 決裁レコード YAML 形式(運営規程 §2.3 / 基本設計書 §1.5.3)

```yaml
policy_id: P-03
title: 口座リスク上限
action: approve            # approve | modify_approve | reject | defer
value:                     # approve/modify_approve では必須。会議で決まった値のみ
  max_daily_loss_pct: <決裁値>
  max_weekly_drawdown_pct: <決裁値>
  per_trade_max_loss_pct: <決裁値>
  max_total_exposure_pct: <決裁値>
  per_bot_max_positions: <決裁値>
decided_by: owner          # 常に owner(システムが他を拒否する)
channel: sync_council
session_ref: council-0
basis_refs: ["docs/03 §5 P-03", "<会議での根拠>"]
decided_at: "2026-06-22T21:00:00+09:00"
effective_from: "2026-06-23"   # 任意
review_after: "2026-09-01"     # 推奨(到来で自動再上程 FR-10.6)
```

### 必須ポリシーのキー(risk_guard が要求する。欠落キーは fail-closed)

| ポリシー | 必須キー |
|---|---|
| P-01 決裁・委任規程 | `delegation.enabled`(委任なしなら false) |
| P-02 レバレッジ規程 | `account_max_effective` / `per_asset_class`(クラス→上限の辞書。crypto_spot 等)/ `hard_ceiling` |
| P-03 口座リスク上限 | `max_daily_loss_pct` / `max_weekly_drawdown_pct` / `per_trade_max_loss_pct` / `max_total_exposure_pct` / `per_bot_max_positions` |
| P-04 セーフガード運用 | `stale_data_sec` / `cb_price_jump_pct_1m` / `cb_max_spread_bps` |

---

## ファシリテーターの心得(このシナリオ固有)

- **自分で決めない。** 推奨を述べるのはペルソナ、決めるのは利用者
- たたき台の数値を「正解」のように扱わない。「そのまま採用しても、変えても、保留してもよい」
- 不変条項(docs/03 第1章)は**議題にできない**。議題化が求められたら丁重に断り、理由を説明する
- 決裁レコードは利用者の確認なしに実行しない(Round 6 の読み上げを省略しない)
- veto・反対意見・少数意見は議事録に必ず残す
- 議題を一度に全部進めない。**1議題ずつ**式次第を回す
