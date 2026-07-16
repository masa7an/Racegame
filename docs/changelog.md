## v19 - Debug Section (2025/12/09)

### デバッグコード削除について
- デバッグ用コードは以下のマーカーで囲まれています：
  ```
  # ========== [DEBUG SECTION START] ==========
  （デバッグコード）
  # ========== [DEBUG SECTION END] ==========
  ```
- **stable版への昇格時**: この範囲を削除してください

---

    - **Tuning**: Tested -100, -20, 0, and currently set to **20**.
    - **Effect**: Controls where the ground texture begins drawing relative to HORIZON_Y.
    - **Reverted**: "Near-Field Speed Boost" was removed due to scrolling artifacts (jerkiness).
    - **Note**: Z-Projection (v6) attempt was discarded due to texture quality loss.

### Ground Texture Rework & Seam Fix (Vertical Parallax)

## Stage 4 Horizon Blending Issues
- stage4の道路馴染ませで苦戦
- 水平線近くの道路描画は完全NG

## 2025/12/09
### フォルダ構成の混乱により意図しないバグが発生

**想定している正しい構成**
- / (ルート)
  - /test
  - /stable
  - /backup

**現状の構成**
- / (ルート)
  - old_main.py（※旧ファイルが残留）
  - /test
    - /stable
    - /backup

**問題点**
- ルートフォルダに古い main.py が存在するため、最新版ではないファイルを誤って参照・編集しやすい。

**対策**
- ルートフォルダに main.py を置かない方針に変更する。

### リネーム
- sanddust → dust
- 理由：紛らわしいので取り違えミスを防ぐため

## rename(2025/12/09)
-"dust.png"→"vfx_dirt_kickup.png"
 "sandslip.png"→"vfx_smoke_beige_sand.png"
- 理由：紛らわしいので取り違えミスを防ぐため
「dust」は「ほこり」なので、
「泥」が適切だった。
