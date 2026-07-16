# コードレビュー: v24_stable 全体

対象: `v24_stable/main.py` + `v24_stable/src/*.py`（全モジュール通読 + 疑わしい箇所は実ファイル・実データで裏取り済み）。
前提資料: [repo_map.md](repo_map.md), [architecture_v24.md](architecture_v24.md)

---

## A. バグ（重要度: 高）

### A-1. エンジン音が一切鳴っていない（v23以降の全バージョン）
[sound.py:21-27](../src/sound.py:21)

```python
base_path = os.path.dirname(os.path.abspath(__file__))   # → v24_stable/src/
wav_path = os.path.join(base_path, "asset", "engine.wav") # → v24_stable/src/asset/engine.wav
```

`sound.py` は自分のいる `src/` フォルダの下に `asset/` を探すが、実体は **1つ上の** `v24_stable/asset/engine.wav`。`src/asset/` は存在しないことを確認済み。結果、起動時に警告を出して `self.enabled = False` となり、**エンジン音全体（低/中/高速ループ、ミュート機能含む）が無効化されたまま動いている**。BGMは `main.py` がCWD相対で別途ロードするため正常に鳴り、気づきにくい。

- フォルダ構成を `src/` + `asset/` に分けた **v23のリファクタリング時に発生した回帰**。GitHub公開版の `v23_stable` と開発中の `test/v23_test` にも同じバグを確認済み。
- 修正案: `os.path.join(base_path, "..", "asset", "engine.wav")`、または他アセットと同じCWD相対 `"asset/engine.wav"` に統一。

### A-2. CONTINUE（周回リスタート）で `replay_data` がクリアされない
[main.py:395-405](../main.py:395)

CONTINUE時に `stage_times = {}` 等はリセットされるが `replay_data` はリセットされない。このため:
1. **2周目クリア後のリプレイに1周目の走行データが先頭から混入**する（リプレイ開始時に `replay_data[0]` のステージへ巻き戻す実装なので、必ず1周目の冒頭から再生される）。
2. 周回するたびにメモリが無制限に増える（1周あたり数万フレーム分の辞書）。

修正案: CONTINUE処理内に `replay_data = []` を1行追加。

### A-3. ranking.json の読み込み失敗時、既存ランキングを黙って消して上書き
[main.py:39-57](../main.py:39)

読み込みが `except Exception` で握りつぶされ `scores = []` のまま処理が続くため、**読めなかった場合は過去のランキング全件が新スコア1件だけのファイルで上書きされる**。実際、現在の `v24_stable/ranking.json` は UTF-16 LE（BOM `FF FE`）で保存されており（PowerShellのリダイレクトで作った形跡）、`json.load(encoding="utf-8")` では読めない状態＝次回クリア時に全消しされる実例がリポジトリ内に存在する。

修正案: 読み込み失敗時は既存ファイルを `ranking.json.bak` に退避してから書き込む、または `encoding="utf-8-sig"` + 破損時は上書きせずエラー表示。

### A-4. リプレイをAボタンで終了すると、そのままCONTINUEが誤発動する
[main.py:477](../main.py:477) → [main.py:392](../main.py:392)

リプレイ終了条件にジョイスティックの**ボタン0（A）**が含まれ、終了先の `STATE_GAME_CLEAR` では**同じボタン0がCONTINUE**に割り当てられている。ボタンは人間の操作では複数フレーム押され続けるため、リプレイをAで抜けた直後のフレームでCONTINUE判定が成立し、**意図せずゲームが最初から再スタートする**。

修正案: リプレイ終了はB（ブレーキ）系のみにする（キーボード側はK_DOWN/K_bで整合が取れており、UIの案内文「Press the brake key to exit」ともAボタンは矛盾している）。または「ボタンが一度離されるまで次の入力を受け付けない」エッジ検出を入れる。

---

## B. バグ（重要度: 中〜低）

### B-1. 左右キー同時押しで「車は曲がるが見た目とリプレイは直進」
[car.py:107-113](../src/car.py:107)

`steering_input` を確定して `self.x` を動かした**後に**両押しチェックで `steering_input = 0.0` に戻している。順序が逆のため、両押し時は右へ移動しつつ、車体の傾き（sway）とリプレイ記録は「入力なし」になる。ゼロ化を位置更新の前に移動すれば解決。

### B-2. 最高速到達時に加速フラグが毎フレーム点滅する
[car.py:239-297](../src/car.py:239)

`speed` が上限を僅かに超えると、アクセル押下中でも加速分岐（`speed < limit` が条件）に入らず `accel_pressed = False` のまま減速分岐＋コースト減速が同時適用され、翌フレーム再加速…を繰り返す。実害は速度の微振動（メーターはスムージングで隠れる）と、**アクセル全開なのにエンジン音の音量が非加速時の0.6に落ちる**こと。上限到達時は `speed = limit` にクランプして `accel_pressed = True` を維持するのが素直。

### B-3. デバッグキーF2でランキングに重複スコアが登録される
[main.py:150-151](../main.py:150), [main.py:167-174](../main.py:167)

`F2`（強制ステージスキップ）は状態を問わず効くため、GAME_CLEAR画面で押すと `stage_id` が6以上のままGAME_CLEAR処理を再実行し、`save_ranking(同じ合計タイム)` が再度呼ばれて**同一スコアがランキングに複数登録される**。F1〜F3・U/Jキーがstable版に残っていること自体、ROADMAPのデバッグコード規約（削除可能なマーカーで囲む）から外れている。

### B-4. リプレイ中に背景・ピッチの更新が止まる
[main.py:436-478](../main.py:436)

`bg_manager.update()`（パララックススクロール・地面の縦スクロール）と `smoothed_slope`（背景ピッチ）は `STATE_PLAYING` でしか更新されないため、リプレイ中は背景横スクロールが凍結し、地面テクスチャも車が走っているのに流れない。また勾配ピッチはゴール直前の値で固定される。カメラ高さフォールバックの `stage_id in [2,3,5]`（[main.py:466](../main.py:466)）も、コース生成が全ステージで勾配を持つ実装（[track.py:191](../src/track.py:191)）と不整合。

### B-5. GOAL/STAGE_CLEAR中にパーティクルが空中で静止する
`effects.update_particles()` がPLAYING時のみ呼ばれるため、ゴール瞬間に出ていた砂煙・火花が2.5秒間フリーズして表示され続ける。更新だけは全状態で回すのが簡単な修正。

---

## C. 堅牢性・設計

- **C-1. クラッシュ時にクリーンアップが走らない**: 例外を [main.py:597-602](../main.py:597) で捕捉→`raise` するため、`sound_manager.cleanup()` / `pygame.quit()` に到達しない。`finally` 化を推奨。`crash_log.txt` も毎回 `"w"` 上書きで履歴が1件しか残らない。
- **C-2. ログの無制限追記**: [logger.py](../src/logger.py) はローテーションなしの追記のみ。個人開発規模では許容範囲だが、`inspect` によるフレーム遡りは毎回のログでコストがかかる。
- **C-3. 例外の握りつぶし**: `background.py` の `get_fog_color` / `_sample_*` に裸の `except: pass` が3箇所。色サンプリング失敗が黙ってフォールバックするため、アセット差し替え時の異常に気づけない。
- **C-4. ステージ固有物理のハードコード**（[architecture_v24.md](architecture_v24.md) 既出）: `if stage_id == 4/5` 分岐が `car.py` に散在。`STAGE_CONFIG` へ `grip`, `brake_mult` 等として統合するのが今後の拡張に最も効く。
- **C-5. パスの二重基準**: アセットはCWD相対（`run.bat` の `cd /d %~dp0` 前提）、ログは `__file__` 相対、そして `sound.py` はその混在が原因でA-1を起こした。**基準ディレクトリを1箇所で定義して全モジュールが参照する**形に統一すべき。
- **C-6. バージョン表記の更新漏れ**: [src/\_\_init\_\_.py:1](../src/__init__.py:1) が「v23_stable src package」のまま。ROADMAPの昇格チェックリスト（ver名コメント更新）の対象漏れ。

---

## D. パフォーマンス（現状60FPSが出ているなら優先度低）

- **D-1. 背景の完全な二重描画**: [main.py:496](../main.py:496) で `bg_manager.draw()` を呼んだ直後、[main.py:503-504](../main.py:503) の `pygame.draw.rect` 2枚が**画面全体を塗りつぶして完全に隠し**、[main.py:507](../main.py:507) でもう一度 `bg_manager.draw()`。1回目の描画（グラデ帯生成含む）は毎フレーム丸ごと無駄。
- **D-2. 毎フレームのSurface生成**: フォグオーバーレイ（[main.py:518-528](../main.py:518)、800×80 Surface + 80本のline）、グラデ帯3種（`background.py`、色が変わらないのに毎フレーム再構築）、7セグ描画のsmoothscale×桁数（`ui.py`）、`draw_hud` の**毎フレーム `pygame.font.Font` 生成**（[ui.py:215](../src/ui.py:215)）。いずれも初回生成してキャッシュ可能。
- **D-3. ループ内import**: `import random`（[main.py:239](../main.py:239)）、`from src.car import NORMAL_MAX_SPEED`（[main.py:533](../main.py:533)）が毎フレーム実行される。キャッシュされるので実害は小さいがファイル先頭へ移動を。

---

## E. コード衛生（動作には影響しない）

- 重複行: `smoothed_camera_y` 二重初期化（[main.py:99-100](../main.py:99)）、`curve_val` 二重計算（[main.py:210-213](../main.py:210)）、`goal_distance` 二重代入（[track.py:93-94](../src/track.py:93)）、`ui.py` スピード色分岐内の到達不能な `> 280` チェック（[ui.py:45](../src/ui.py:45)）。
- 未使用: [main.py:490](../main.py:490) の `current_slope`（計算するだけで使わない）、`Track.project()` の `road_offset` 引数（常に0）、`calculate_sway` の `speed`/`normal_max_speed` 引数。
- 思考過程コメントの残置: 「Wait, this is linear? No it should be…」のような自問自答コメントが `track.py`/`car.py` に多数。動作には無関係だが、確定した仕様だけを残すと可読性が上がる。

---

## 良い点（維持すべき設計）

- **オブジェクトプール**（`effects.py`）: パーティクル/スパークの固定長プール＋リングバッファ再利用は正しいリアルタイムゲームのパターン。
- **シード付き乱数による描画の安定化**: 道路エッジのでこぼこや砂粒子を `random.Random(seg_index * 定数)` で生成しており、毎フレーム同じ位置に出る＝**ちらつき防止**として上手い（[track.py:466](../src/track.py:466), [track.py:490](../src/track.py:490)）。
- **エンジン音のクロスフェード設計**: 1本のWAVからDSPで3ループを合成し速度でブレンドする構成は、アセット追加なしで良い結果を出す合理的な設計（A-1でパスが直れば、の話）。
- **リプレイのスナップショット方式**: 物理を再実行しない状態再生は、決定論を保証できない実装での安全な選択。

---

## 推奨対応順

| 順位 | 項目 | 理由 |
|---|---|---|
| 1 | A-1 エンジン音パス | 1行修正で消えていた機能が丸ごと復活。GitHub公開版にも波及 |
| 2 | A-2 replay_dataクリア | 1行修正。周回プレイで確実に発生 |
| 3 | A-4 リプレイ終了→CONTINUE誤爆 | パッド利用者が確実に踏む操作系バグ |
| 4 | A-3 ランキング保護 | データ消失系。現物のUTF-16ファイルが引き金として実在 |
| 5 | B-3含むデバッグキー整理 | stable昇格ルール（ROADMAP規約）との整合 |

C・D・Eは次フェーズのリファクタリング（ステージ物理の`STAGE_CONFIG`統合、描画キャッシュ化）とまとめて対応するのが効率的。
