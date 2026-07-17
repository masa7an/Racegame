# ステージ仕様 (Stage Specifications)

## Stage 01 – Forest (Day)
【環境】
- 空色: Clear Blue (100, 149, 237)
- 地面: Green Forest (34, 139, 34)
- 道路: Standard Asphalt (Light: 105, 105, 105 / Dark: 95, 95, 95)
- 背景: `bg1.png` (山岳), `bg1v.png`
- 縁石: あり

【コース特性】
- カーブ頻度: 0.05 (低)
- カーブ振幅: 30.0 (緩やか)
- カーブ倍率: 0.8x
- 急カーブ率: 10%
- S字率: 10%

【関連ファイル】
- `track.py` (Stage Config 1)
- `main.py`

---

## Stage 02 – Sunset / Savanna
【環境】
- 空色: Orange Sunset (255, 140, 0)
- 地面: Savanna Brown (210, 180, 140)
- 道路: Standard Asphalt
- 背景: `bg2.png` (夕日/荒野), `bg2v.png`
- 縁石: あり

【コース特性】
- カーブ頻度: 0.08
- カーブ振幅: 60.0
- カーブ倍率: 1.0x
- 急カーブ率: 20%
- S字率: 20%

【関連ファイル】
- `track.py` (Stage Config 2)

---

## Stage 03 – Night Highway
【環境】
- 空色: Deep Navy (20, 40, 110)
- 地面: Dark Ground (20, 20, 20)
- 道路: Bright Asphalt (視認性確保)
- 背景: `bg3.png` (夜景/都市?), `bg3v.png`
- 縁石: あり

【コース特性】
- カーブ頻度: 0.1 (中)
- カーブ振幅: 90.0 (強)
- カーブ倍率: 1.2x
- 急カーブ率: 30%
- S字率: 40%

【関連ファイル】
- `track.py` (Stage Config 3)

---

## Stage 04 – Sand Desert (White Sands)
【環境】
- 空色: Pale Blue (200, 240, 255)
- 地面: Desert Brown (139, 69, 19) ※遠景用
- 道路: Sand Asphalt (Light: 130, 130, 130 / Dark: 120, 120, 120)
- 背景: `bg4.png` (砂漠), `bg4v.png`
- 霧色: Bright Desert (190, 160, 130)
- 縁石: **なし**

【特殊エフェクト】
- **砂粒子 (Sand Particles)**: あり
  - 発生ロジック: `track.py` (描画ループ内)
  - 色: Bright Yellow (230, 200, 100)
- **スリップ砂煙**: あり
  - 発生条件: 加速時(スリップ中), ブレーキ時
  - 関連: `main.py` -> `effects.add_sand_dust`

【物理挙動 (Physics Adjustment)】
- **ブレーキ効き**: 50% (オフロード時は100%に回復)
- **加速スリップ**:
  - 適用範囲: 220km/h以下 (< 107.0 units)
  - 挙動: 断続的に加速係数が低下 (0.4x ~ 1.0x)
  - 上り坂補正: 勾配 > 0.02 の時はスリップ緩和 (0.7x ~ 1.0x)
- **自然減速 (Coasting)**:
  - オフロード時: 1.2倍 (通常より強く減速)

【コース特性】
- カーブ頻度: 0.04 (低)
- カーブ振幅: 50.0
- カーブ倍率: 1.5x (緩やかだが長い)
- 急カーブ率: 50%
- S字率: 30%

【関連ファイル】
- `track.py` (Stage Config 4)
- `car.py` (Physics Logic)
- `main.py` (Effect Triggers)
- `effects.py` (Rendering)

---

## Stage 05 – Cloudy / High Difficulty
【環境】
- 空色: Clear Blue (100, 149, 237)
- 地面: Green (34, 139, 34)
- 背景: `bg5.png`, `bg5v.png`
- 縁石: あり

【コース特性】
- カーブ頻度: 0.12 (高)
- カーブ振幅: 80.0
- カーブ倍率: 1.8x (激しい)
- 急カーブ率: 60%
- S字率: 30%

【関連ファイル】
- `track.py` (Stage Config 5)

---

## Stage 06 – Tunnel (Mountain Pass)
【環境】
- Stage1の環境・コース特性を複製（コースレイアウトはStage1とは別物）
- 空色: Clear Blue (100, 149, 237)
- 地面: Green Forest (34, 139, 34)
- 背景: `bg1.png` (山岳), `bg1v.png`
- 縁石: **なし**

【特殊エフェクト】
- **トンネル区間**: あり（固定位置・固定長、コース中に3回登場）
  - 区間1: z = 20,000 〜 83,000（長さ63,000）
  - 区間2: z = 200,000 〜 263,000（長さ63,000）
  - 区間3: z = 400,000 〜 463,000（長さ63,000）
  - 詳細: `docs/tunnel_requirements.md`

【コース特性】
- カーブ頻度: 0.05 (低)
- カーブ振幅: 30.0 (緩やか)
- カーブ倍率: 0.8x
- 急カーブ率: 10%
- S字率: 10%

【関連ファイル】
- `track.py` (Stage Config 6)
