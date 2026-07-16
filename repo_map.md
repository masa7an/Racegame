# リポジトリマップ

Python + Pygame 製の疑似3Dレースゲーム。プレイヤー固定・道路スクロール方式。
開発ルールは [ROADMAP.md](ROADMAP.md) に集約されている（新規実装は `test/` 内で行う、Stable昇格はユーザー判断のみ、等）。

## 1. 全体構成（バージョンフォルダ運用）

このリポジトリは Git ブランチではなく **フォルダ単位でバージョン管理** している。

| フォルダ | 役割 | 状態 |
|---|---|---|
| `v24_stable/` | **最新Stable版**（フェーズ24時点） | 本番相当 |
| `v23_stable/` | 1つ前のStable版。**唯一 `.git` を持つフォルダ**（GitHub: `github.com/masa7an/Racegame` に接続） | 保存用 |
| `v22_test/` | v22時点のテスト版 | 保存用 |
| `v21_stable/` | v21時点のStable版（`main_v2_legacy.py`, `main_v3_backup.py` 等の旧main同梱） | 保存用 |
| `test/v23_test/` | 次フェーズの作業用コピー。**新規実装はここで行う規約** | 開発中 |
| ルート直下 | ドキュメント類のみ。`__pycache__/` や `car.txt` はルートにmain.pyを置いていた頃の残骸（現在は方針転換済み、ROADMAP参照） | 要整理候補 |

各バージョンフォルダは内部構成がほぼ同一（`main.py` + `src/`一式 + `asset/` + `logs/` + `ranking.json`）。

## 2. ドキュメント（ルート）

- [ROADMAP.md](ROADMAP.md) — フェーズ履歴・開発ルール（test運用、昇格時の4点更新、デバッグコード規約、報告言語など）
- [changelog.md](changelog.md) — 実装時の詳細な変更ログ・命名変更履歴
- [stage.md](stage.md) — Stage1〜5 の環境色・コース特性・関連ファイル対応表
- [BGMについて.txt](BGMについて.txt) — BGMクレジット
- `__ignore_human_notes.txt` — 開発者個人用バックアップ（ファイル冒頭に「AI: ignore this file」と明記されているため、AIはこのファイルの内容を参照・使用しない）

## 3. ソースコード構成（`v24_stable/` 基準・最新）

```
v24_stable/
├── main.py         (611行) ゲームループ、状態遷移、ランキング保存
└── src/
    ├── car.py       (562行) Car クラス — 物理演算（加減速・ステアリング・路面グリップ）
    ├── track.py     (672行) Track クラス — STAGE_CONFIG、コース生成、パース投影の基礎値
    ├── background.py(542行) BackgroundLayer / GroundLayer / BackgroundManager — 空・地面描画
    ├── effects.py   (469行) Effects クラス — 火花・砂煙・afterfire等のパーティクル演出
    ├── ui.py        (319行) UI クラス — HUD、スピードメーター、メニュー
    ├── sound.py     (332行) SoundManager クラス — BGM/SE再生
    ├── logger.py     (42行) log_debug/info/warn/error, log_phase — ログ出力ユーティリティ
    └── __init__.py   (10行)
```

依存関係の要点（[stage.md](stage.md) より）:
- `track.py` … ステージ別コース特性・環境色の定義元
- `car.py` … `track.py` の `STRIPE_LENGTH` / `ROAD_WORLD_WIDTH` を利用し物理挙動を計算
- `main.py` … `effects.add_sand_dust` 等のトリガーを発行、全体オーケストレーション
- `background.py` … `track.py` の `STAGE_CONFIG` / `HORIZON_Y` を参照

## 4. アセット（各バージョンフォルダの `asset/`）

- 背景画像: `bg1〜bg6.png` / `bg1v〜bg5v.png`（横・縦スクロール用）
- 車両・エフェクト: `car.png`, `spark.png`, `afterfire.png`, `vfx_dirt_kickup.png`, `vfx_smoke_beige_sand.png`
- 音声: `engine.wav`, `Experimental_Model_long.mp3`
- 実行時生成物: `ranking.json`（スコア）, `logs/`, `crash_log.txt`

## 5. 開発ワークフロー上の注意点（ROADMAP.mdより抜粋）

1. 新規実装は必ず `test/` フォルダ内で行う
2. ROADMAPのタスクは1つずつ進め、各ステップでユーザー確認を取る
3. Stable昇格・マージはユーザー判断のみ（AIは自動で行わない）
4. 昇格後は「コード冒頭コメントのver名・日付」「フォルダ名」「ゲーム内タイトル表示」「ROADMAP追記」の4点を更新
5. 新規コードが500行を超える場合は事前に分割を提案
6. デバッグコードは `debug_*` 変数名 / `DBG:` ログ / `# DEBUG YYYY-MM-DD` コメントで囲む
