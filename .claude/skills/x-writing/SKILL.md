---
name: x-writing
description: >
  X（Twitter）投稿文章を作成するスキル。
  生成AI・AIエージェント関連のテーマについて、投稿文を生成する。
  「X投稿を書いて」「ツイート文を作って」「Xの文章案」「投稿文作成」
  「ツイート案」「X投稿の下書き」「SNS投稿文」などのリクエストで発動。
---

# X投稿文作成

x-writerサブエージェントに委譲して投稿文を作成する。
メインエージェントはreferenceファイルを読む必要はない。

## 詳細定義の場所（サブエージェントが参照）

- 文章要件・NGパターン: `x-manager/reference/x-writing-guidelines.md`
- 成果がでた投稿例: `x-manager/reference/x-writing-examples.md`
- サブエージェント定義: `x-manager/agents/x-writer.md`

## 実行フロー

1. テーマ確定（ユーザー指定 or 確認）
2. `config.local.md` からXアカウント情報を取得
3. Taskツールでx-writerサブエージェント（sonnet）を起動し、テーマとアカウント情報を渡す
4. サブエージェントがreference内のガイドライン・成功例を自分で読み、投稿文を作成
5. 結果をユーザーに提示、修正があればサブエージェントに再委譲
