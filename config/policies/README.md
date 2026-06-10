# ポリシーレジストリ(config/policies/)

すべての運用ルール(リスク上限・レバレッジ・ゲート基準・委任範囲など)は
ここで `P-XX_<title>.yaml` として管理される。システムは **status=active** の
ポリシーだけを読む(基本設計書 §1.5.3)。

## 現在の状態

このディレクトリにポリシーファイルが無い間、システムは **fail-closed**
(No Policy, No Trade — 不変条項5)として動作し、一切発注しない。

**第0回意思決定会議**(docs/03_運営規程・第0回アジェンダ.md 第5章)で
必須ポリシー ★P-01〜P-04 を決裁すると、ここに決裁済みポリシーが生成され、
ペーパー取引が解禁される。会議の開催は「第0回会議を開催」と発話する
(scenarios/council.md)。

## 変更の唯一の経路

```
tc policy record --file <決裁レコード.yaml>
```

- **手編集は禁止**(hooks / pre-commit が検出する)
- 決裁レコードの必須項目は運営規程 §2.3(decided_by は owner のみ)
- ロールバック = 旧バージョンの値を再決裁(履歴は policy_decisions に不滅)
- `tc policy list / show <id> / sync` で確認・ビュー再生成
