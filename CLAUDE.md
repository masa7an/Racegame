# プロジェクトルール

## Bashツールでのコミットメッセージ・複数行文字列の書き方

- **PowerShellのhere-string構文（`@'...'@` / `@"..."@`）をBashツールで使わないこと。** Bashツール（Git Bash / POSIX sh）とPowerShellツールは別のシェルであり、構文が異なる。`@'` で始めると `unexpected token` の構文エラーになる。
- Bashツールで複数行のコミットメッセージを渡す場合は、POSIXのheredocを使う：
  ```bash
  git commit -F - <<'EOF'
  タイトル行

  本文...
  EOF
  ```
  （`git commit -m "$(cat <<'EOF' ... EOF)"` の形式でもよい）
- PowerShellツールで複数行文字列を渡す場合のみ、`@'...'@` を使う（Bashツールでは使わない）。
- コミット前に `git add` で対象ファイルを明示的に指定し、ステージングされていることを確認してから `git commit` を実行する（`add` と `commit` を分けて確認する）。
