# リポジトリマップ

Python + Pygame 製の疑似3Dレースゲーム。プレイヤー固定・道路スクロール方式。
開発ルールは [ROADMAP.md](ROADMAP.md) に集約されている（コミット前の動作確認、コミット時の4点更新、デバッグコード規約、報告言語など）。

## 1. 全体構成（gitベース）

このリポジトリはフォルダ単位のバージョン管理ではなく、**gitのコミット履歴でバージョン管理**している
（2026-07-17 に移行済み。旧 `v24_stable/` 等のフォルダ運用は廃止）。

- ブランチ運用: 作業は feature ブランチで進め、動作確認後にユーザーの指示で `main` へマージする。
  `main` の履歴はマージコミットを作らない直線履歴（fast-forward）で運用している。
- リリース区切りには `git tag v1.1` のように注釈付きタグを付ける（`v25_stable` のようなフォルダ名の
  代わり）。
- ソース（`main.py` / `src/`）とドキュメント（`docs/`）はリポジトリのルート直下に一本化されている。
  バージョンごとのフォルダ分割はない。

| 場所 | 役割 |
|---|---|
| ルート直下 | `main.py`、ドキュメント類、`run.bat` |
| `src/` | ゲーム本体のモジュール一式 |
| `asset/` | 画像・音声（**git管理対象外**。ディスク上にのみ存在。例外: [3節](#3-アセット) 参照） |
| `docs/` | 開発ドキュメント（本ファイルを含む） |
| `logs/`, `ranking.json`, `settings.json` | 実行時生成物（git管理対象外） |

## 2. ドキュメント（`docs/`）

- [ROADMAP.md](ROADMAP.md) — 開発ルール（コミット前の動作確認、コミット時の4点更新、デバッグコード規約、報告言語など）とフェーズ履歴
- [changelog.md](changelog.md) — 実装時の詳細な変更ログ・決定事項と落とし穴
- [stage.md](stage.md) — Stage1〜6 の環境色・コース特性・物理挙動・関連ファイル対応表
- [tunnel_requirements.md](tunnel_requirements.md) — Stage6 トンネルギミックの実装ログ（要件・決定事項・実装メモを章立てで記録）
- [architecture_v24.md](architecture_v24.md) / [review_v24.md](review_v24.md) — v24時点のアーキテクチャ資料・レビュー記録（フォルダ運用時代の名残。内容は当時のスナップショット）
- ルート直下: [BGMについて.txt](../BGMについて.txt)（BGMクレジット）、[操作マニュアル.txt](../操作マニュアル.txt)
- `__ignore_human_notes.txt`（ルート直下、git管理対象外） — 開発者個人用メモ。ファイル冒頭に「AI: ignore this file」と明記されているため、AIはこのファイルの内容を参照・使用しない

## 3. ソースコード構成

```
main.py            (768行) ゲームループ、状態遷移、ランキング保存、演出トリガーの発行
src/
├── car.py         (599行) Car クラス — 物理演算（加減速・ステアリング・路面グリップ・トンネル壁の制限）
├── track.py      (1211行) Track クラス — STAGE_CONFIG、コース生成、パース投影、トンネル/山の描画
├── background.py  (622行) BackgroundLayer / GroundLayer / BackgroundManager — 空・地面・ヘイズ描画
├── effects.py     (469行) Effects クラス — 火花・砂煙・afterfire等のパーティクル演出
├── ui.py          (350行) UI クラス — HUD、スピードメーター、メニュー
├── sound.py       (338行) SoundManager クラス — BGM/SE再生
├── logger.py       (59行) log_debug/info/warn/error, log_phase — ログ出力ユーティリティ
└── __init__.py      (9行)
```
（行数は目安。正確な値は都度 `wc -l` 等で確認すること）

依存関係の要点（[stage.md](stage.md) より）:
- `track.py` … ステージ別コース特性・環境色・トンネル定数の定義元
- `car.py` … `track.py` の `STRIPE_LENGTH` / `ROAD_WORLD_WIDTH` / `TUNNEL_WALL_LIMIT` 等を利用し物理挙動を計算
- `main.py` … `effects.add_sand_dust` / `effects.add_spark` 等のトリガーを発行、全体オーケストレーション
- `background.py` … `track.py` の `STAGE_CONFIG` / `HORIZON_Y` を参照

## 4. アセット

- 背景画像: `bg1〜bg6.png` / `bg1v〜bg5v.png`（横・縦スクロール用）、`forest.png`（Stage6山肌テクスチャ）
- 車両・エフェクト: `car.png`, `spark.png`, `afterfire.png`, `vfx_dirt_kickup.png`, `vfx_smoke_beige_sand.png`
- 音声: `engine.wav`, `Experimental_Model_long.mp3`
- `asset/` はディレクトリごと `.gitignore` で除外（ディスク上にのみ存在、追加・変更してもコミットには含まれない）。
  **例外**: README が参照するスクリーンショットは `docs/screenshot.png` として git管理下に置いている
  （`.gitignore` は `docs/` 配下の画像を対象外にする設計になっている）。
- 実行時生成物（git管理対象外）: `ranking.json`（スコア）, `logs/`, `crash_log.txt`, `settings.json`

## 5. 開発ワークフロー上の注意点（ROADMAP.mdより抜粋）

1. 新規実装は `main.py` / `src/` を直接編集して進めてよい（`test/` フォルダ運用は廃止済み）。
2. **動作確認が取れるまではコミットしない**。ユーザーが確認し、問題なければ明示的な指示があった場合のみコミットする。
3. ROADMAPのタスクは1つずつ進め、各ステップでユーザー確認を取る。
4. コミット操作・GitHubへのpushは AI から自動で行わない。必ずユーザー判断を待つ。
5. コミット時（バージョンを更新する時）は次の4点を確認・更新する:
   `main.py` 冒頭のver名・日付コメント／ゲーム内タイトル表示／ROADMAPへの1行追記／README のVersionバッジとFeatures記述。
   タグ付けは任意（大きな区切りで `git tag v1.1` 等）。
6. 新規コードが500行を超える場合は事前に分割を提案する。
7. デバッグコードは `debug_*` 変数名 / `DBG:` ログ / `# DEBUG YYYY-MM-DD` コメントで囲む。
