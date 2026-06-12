# アイデア置き場(ideas/)

TradeCouncil 本体のスコープに収まらない構想も含めて、アイデアを複数文書で
ブラシュアップして育てるための置き場。

## 1. 位置づけ — 何であって、何でないか

- ここにあるのは**構想(アイデア)**であり、仕様でもポリシーでもない
- 本体(TradeCouncil)の仕様・設定・挙動を一切変更しない。ポリシーレジストリ
  (`config/policies/`)や decision_gate とも無関係(非規範)
- アイデア内に登場する数値・ルール案・編成案はすべて「たたき台」であり、
  決裁されたものは存在しない

## 2. 既存の置き場との棲み分け

| 置き場 | 役割 |
|---|---|
| `docs/` | 本体の一次仕様(規範) |
| `docs/adr/` | 本体に関する大きな判断の記録 |
| `docs/proposals/` | 本体への採否決裁を求める提案書 |
| `BACKLOG.md` の Icebox | 本体スコープ内の一行メモ |
| **`ideas/`** | **スコープを問わない構想の分冊置き場**(本フォルダ) |

動線は双方向: Icebox の一行メモが分冊化したくなったら ideas/ へ。ideas/ の構想が
本体採用へ向かうなら docs/proposals/ や BACKLOG のストーリーへ、外部で実現するなら
別リポジトリへ昇格する。

## 3. 運用ルール

1. **1アイデア = 1フォルダ**(kebab-case)。入口は各フォルダの `README.md`(アイデアカード)
2. **索引(§5)が真実源**: フォルダを作ったら必ず1行追加する
3. status の真実源は各アイデアカードのみ。分冊へ転記しない(転記は必ず陳腐化する)
4. **秘密情報・実在顧客の個人情報を書かない**: ideas/ は git 追跡される
   (`.gitignore` が除外するのは `local/`・`sharepoint/`・`var/` 等のみ)。例示は必ず架空名で行う
5. **retired でも消さない**: 取り下げ理由と学びを追記して残す(更新履歴は append-only)
6. ブラシュアップに本リポジトリのシナリオ(deliberation / document-review / brainstorm)を
   使ってよい。シナリオ成果物の原本は `<root>/` 配下に出力されるので、確定した内容を
   ideas/ 側へ反映する(構想の真実源は ideas/)
7. コミットは Conventional Commits(例: `docs(ideas): ...`)

## 4. アイデアの状態(status)とライフサイクル

```
idea → shaping → proposed → promoted
          ↘ parked / retired(どの段階からでも)
```

| status | 意味 |
|---|---|
| `idea` | 着想・骨子のみ(カード1枚) |
| `shaping` | 分冊化してブラシュアップ中 |
| `proposed` | 決裁権者へ上程中(本体採用なら docs/proposals/ 起票、外部実現なら具体化判断) |
| `promoted` | 昇格済み。以後の真実源は昇格先(別リポジトリ等)。カードに行き先を記す |
| `parked` | 休眠。再開条件をカードに書く |
| `retired` | 取り下げ。理由と学びを残す(削除しない) |

## 5. アイデア索引

| アイデア | status | 一言 | 入口 |
|---|---|---|---|
| governance-core | shaping | 「AIが提案し、人間が決裁する」運用コアの汎用解説(流用構想の共通参照資料) | [governance-core/README.md](governance-core/README.md) |
| sales-council | shaping | TradeCouncil のガバナンス枠組みを営業支援へ流用(No Policy, No Send) | [sales-council/README.md](sales-council/README.md) |
