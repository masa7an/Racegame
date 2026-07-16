# アーキテクチャ分析（v24_stable）

対象: `v24_stable/main.py` + `v24_stable/src/*.py`（合計約3,559行）。
[repo_map.md](repo_map.md) の続編として、最新Stable版の内部設計を詳しく分析する。

## 1. 全体構造 — 「main.py God Object」パターン

```
main.py (611行)
  ├─ Car          (src/car.py)     … 物理演算・自車描画
  ├─ Track        (src/track.py)   … コース生成・道路投影描画
  ├─ BackgroundManager (src/background.py) … 空・地面パララックス
  ├─ Effects      (src/effects.py) … パーティクル演出
  ├─ UI           (src/ui.py)      … HUD/メニュー描画
  ├─ SoundManager (src/sound.py)   … エンジン音合成・BGM
  └─ logger       (src/logger.py)  … ログユーティリティ（唯一のグローバル関数群）
```

各クラスは互いを知らず、**すべての配線と調停は `main()` 関数1つが担っている**（Mediator的だが専用クラス化されておらず、`main()` 自体がその役割を兼ねる巨大関数）。フレームごとの処理はモジュール横断のインライン処理として `main()` に直接書かれている（例: 砂煙・火花のスポーン条件分岐、L358〜358行あたりの数十行）。これは意図的というより、機能追加を重ねた結果の集約と見られる（[ROADMAP.md](ROADMAP.md) にも「Phase 22」等の追記コメントが随所に残る）。

## 2. ゲームループとステートマシン

`main()` 内の `while running:` ループが以下を毎フレーム実行：

1. `pygame.event.get()` でQUIT/デバッグキー処理
2. `current_state` に応じた **Update分岐**（`if/elif`チェーンのみ、State classやテーブル駆動ではない）
3. 固定順序の **Rendering**（背景→道路→フォグ→車→エフェクト→HUD）

ステートは整数定数（`STATE_PLAYING=0 … STATE_REPLAY=5`）で管理：

```
PLAYING ──(ゴール到達)──▶ GOAL ──(1.5s)──▶ STAGE_CLEAR ──(1.0s)──▶ NEXT_STAGE_INIT
                                                                        │
                              ┌─────────────────────────────────────────┘
                              ▼
                    stage_id > 5 ? ──yes──▶ GAME_CLEAR ──[R]──▶ REPLAY ──(終了)──▶ GAME_CLEAR
                              │no                                │
                              ▼                          [Enter]/[Esc]
                          PLAYING (次ステージ)              リスタート／終了
```

- 遷移条件・タイマーはすべて `main()` 内のローカル変数（`state_timer`, `stage_times` 等）で管理。ステートごとのロジックがクラス化されていないため、状態が増えるたびに `main()` の分岐が線形に増える構造（拡張性より単純さを優先した設計）。
- リプレイは **入力の再生ではなく状態のスナップショット再生**：`replay_data` に毎フレーム `{x, z, speed, steering_input, offroad_l/r, braking, camera_y, stage_id}` を辞書として追記し、リプレイ時は `car` の属性へ直接代入するだけ（物理再計算なし）。実行中のみ有効でディスク保存はされない。

## 3. 座標系・描画パイプライン（Track / Background）

擬似3Dレース（アウトラン式）の古典的手法をベースに実装：

- **セグメント方式**: `STRIPE_LENGTH=300`単位でコースを短冊状の `segments` 配列に分割し、各セグメントが `p1/p2` の `{z, y}` とカーブ値・色を保持（[track.py:124](../src/track.py:124) `add_segment_sequence`）。
- **投影**: `screen_y = HORIZON_Y - world_y * scale`, `scale = PROJECTION_PLANE_DIST / world_z` という単純な透視除算（[track.py:97](../src/track.py:97) `project`）。
- **描画順序**: 遠方から手前へのペインターズアルゴリズム（`draw()` 内 `for i in range(max_idx, start_idx-1, -1)`）。カーブは `dx`（曲率の累積値）としてXオフセットに畳み込まれ、道路だけでなく `bg_manager.set_curve_offset()` 経由で背景の消失点にも伝播する（モジュール間の**唯一の双方向っぽい連携ポイント**）。
- **背景**: `BackgroundLayer`（空、緩やかな視差スクロール）+ `GroundLayer`（地面、ストライプ単位でスケールを変えるラスタ効果によって疑似アフィン変換を実現）の2層構成。両者の継ぎ目を隠すために `_draw_gradient_band` / `_draw_lower_gradient` / `_draw_fog_gradient` という**手動チューニングされたグラデーション帯**を3つ重ねている。定数（オフセット量、フェード指数、閾値等）はほぼ全てハードコードされたマジックナンバーで、コメントに試行錯誤の履歴（「Tested -100, -20, 0…」等）が残っている＝**設定より実験的調整で仕上げられたレンダリング**。

カメラ高さ（登坂・降坂時の消失点変化）は `smoothed_camera_y` としてローパスフィルタ処理された上で、道路描画・背景描画の両方に個別の経験式（`* 0.02` 等）で伝達されており、本来1つの「カメラ」オブジェクトが持つべき責務が `main()` と `Track` と `BackgroundManager` の3箇所に分散している。

## 4. 物理演算（Car）— データ駆動と決め打ちが混在

- ステージ非依存の基本パラメータ（`NORMAL_MAX_SPEED`, `ACCEL_RATE`, `STEER_SENSITIVITY_*` 等）は `car.py` 冒頭の定数。
- ステージ固有の外観設定（色・カーブ頻度等）は `STAGE_CONFIG`（`track.py`）で**データ駆動**。
- 一方で **ステージ固有の物理挙動**（Stage4の砂スリップ・オフロード時ブレーキ半減、Stage5のウェット操舵低下・ドリフト増加）は `car.py` の `update()` 内に `if stage_id == 4` / `if stage_id == 5` という**ハードコード分岐**として実装されている（[car.py:78](../src/car.py:78), [car.py:233](../src/car.py:233), [car.py:254](../src/car.py:254) 等）。`STAGE_CONFIG` を拡張してそこにグリップ係数等を持たせる余地はあるが未使用 — **設計の一貫性がやや崩れている箇所**。
- `car.update()` は「操舵→遠心力→オフロード判定→坂道physics→加減速→座標更新」を1メソッドに直列実装（約230行）。副作用（`self.x`, `self.speed`, `self.offroad_l/r` 等7個以上のインスタンス変数を書き換え）が多く、単体テストは書きにくい構造。

## 5. エフェクト・サウンドの設計パターン（良い点）

- **オブジェクトプール**: `Effects` はパーティクル/スパークを固定長配列（`max_particles=30`, `max_sparks=50`）で確保し、リングバッファ的に再利用（`pool_index = (pool_index+1) % max_particles`）。GC負荷を避ける典型的なリアルタイムゲームパターンが正しく使われている。
- **手続き的サウンド合成**: `SoundManager` は起動時に `engine.wav` 1本から、ローパスフィルタ→エコー→ピッチシフト（サンプル間引き）を自前DSP（`wave`/`struct`使用、純Python実装）で適用し、低速/中速/高速の3ループを生成、速度に応じてチャンネル音量をクロスフェードする設計。追加音声アセット無しでエンジン音の速度感を表現する工夫だが、**起動時に純Pythonでサンプル単位ループ処理**（[sound.py:174](../src/sound.py:174)以降）を行うため、WAV尺が伸びると起動が遅くなるリスクがある。

## 6. 横断的な設計傾向・懸念点

| 傾向 | 具体例 | 影響 |
|---|---|---|
| **God Object化した main()** | 砂煙/火花のスポーン判定が`main()`に直書き（本来`Effects`か`Car`の責務） | 新規演出追加のたびに`main()`が肥大化 |
| **描画とロジックの未分離** | Update/Renderが同一`while`ループ内で逐次実行、分離レイヤーなし | シンプルだが自動テスト・ヘッドレス実行が困難 |
| **マジックナンバー多数** | `background.py`の`k=0.01`, `GROUND_RENDER_OFFSET_Y=17`等、コメントに調整履歴が残る | 値の意味が実装者の試行錯誤に依存し、再調整が難しい |
| **ステートマシンが非構造化** | 6ステートを`if/elif`で分岐、専用クラスなし | ステート追加ごとに`main()`の分岐が線形増加 |
| **相対パス依存** | `ranking.json`はCWD相対、`sound.py`は`__file__`基準 | 実行ディレクトリによって保存先が変わりうる |
| **デバッグコードが本番パスに混在** | F1〜F3キー、`K_u`/`K_j`地面オフセット調整が`main()`に直書き | ROADMAPのデバッグ規約（`debug_*`命名等）はcar.py内の一部のみ順守 |
| **例外処理は最小限** | ループ全体を`try/except`で囲み`crash_log.txt`に書いて再送出のみ | クラッシュ時の状態復旧・自動リカバリはなし |

## 7. 総評

「非エンジニアがAntigravity/Gemini/Claudeと対話しながら機能を継ぎ足していった」という開発経緯（README.md記載）と整合する構造で、**個々のモジュール（Effects のプール管理、Sound の手続き的合成、Track の教科書的疑似3D投影）は妥当な設計判断が随所にある**一方、**モジュール間の調停役が専用化されておらず`main()`に集中**しているため、フェーズを重ねるごとに`main()`と`car.py`にステージ固有の分岐が蓄積している。今後さらにステージや演出を追加するなら、①ステージ固有の物理係数を`STAGE_CONFIG`に統合してハードコード分岐を削減、②`main()`のエフェクトスポーン処理を`Effects`側のメソッドに委譲、の2点が最も効果対効率の良いリファクタリング候補になる。
