import math

import pygame
from .track import (STAGE_CONFIG, HORIZON_Y, DRAW_DISTANCE,
                    PROJECTION_PLANE_DIST, CAMERA_HEIGHT)

# --- Ground Layer Config ---
#
# 地面テクスチャの帯を地平線の何px下から描き始めるか。＝帯のカバー範囲。
#
# 17 なのは見た目の要求から: これより下げると、地平線〜帯の上端の隙間に背景画像が覗き、
# そこを通る道路の遠方が地面から浮いて見える（かつスクロールテクスチャと背景画像の色が
# 馴染まず、切れ目が露見する）。地平線ぎりぎりまで地面で埋めることでこの継ぎ目を隠している。
#
# 帯の行を dy（帯の上端からの距離）とすると、その行が映すワールド奥行きは
#     z(dy) = CAMERA_HEIGHT * PROJECTION_PLANE_DIST / (OFFSET + dy)
# で決まる。OFFSET=17 は上端が z=26471、最下段が z=1500 で、22000単位ぶんの奥行きを
# たった83px(y=317〜400)に詰め込む。この圧縮は物理的に避けられず、素直にサンプリング
# すれば必ず折り返す。GroundLayer は縦ミップマップでこれを面積平均して吸収している
# （上端はテクスチャの平均色に収束し、地平線の霞へ自然に溶ける）。
GROUND_RENDER_OFFSET_Y = 17

# 地面テクスチャの幅が、ワールド上で何単位ぶんに相当するか。＝模様の細かさのツマミ。
#
# GROUND_RENDER_OFFSET_Y とは独立に選べる。横倍率を scale(dy) = a * (OFFSET + dy) と
# 置くと、テクスチャがワールド上で占める幅は texture_width * a * CAMERA_HEIGHT となり、
# dy にも OFFSET にも依存しない定数になる。一方、流線が収束するのは scale(dy)=0 すなわち
# dy=-OFFSET（＝ちょうど地平線）で、これは a に依存しない。つまり:
#     OFFSET … 帯のカバー範囲と、消失点が地平線に乗ること
#     この値 … 模様の細かさ（＝手前でどれだけ拡大＝ボケるか）
# の2つが完全に分離している。小さくすると模様が細かくなりボケにくくなるが、上端の
# 折り返し量が増える（ミップマップが吸収するので破綻はせず、単に早くボケ始める）。
#
# 24000 は等方（テクスチャの縦横がワールド上で同じ縮尺＝画像が歪まない）の値。
# 旧実装の実効値は約41800相当で、模様が奥へ1.74倍引き伸ばされていた。
GROUND_TEXTURE_WORLD_WIDTH = 24000.0

# --- Gradient Smoothing Config ---
GRADIENT_HEIGHT = 20  # グラデーション帯の高さ（上段、50%縮小）
GRADIENT_HEIGHT_2 = 40  # 2段目の緩いグラデーションの高さ

# --- Tunnel Haze Fade Config ---
# トンネル区間では地平線付近の霧・グラデーション帯がアーチ/山のシルエットと
# 噛み合わず不自然に見えるため、入口/出口の手前からフェードアウトする。
# アーチが画面を覆い始める前に消え終わるよう、境界からHIDE_MARGINだけ
# 離れた位置でフェードが完了する（境界±HIDE_MARGINの範囲は完全非表示）。
TUNNEL_HAZE_FADE_DISTANCE = 3000.0
TUNNEL_HAZE_HIDE_MARGIN = 1500.0

class BackgroundLayer:
    def __init__(self, image_path, scroll_factor_x, scroll_factor_y, screen_width, screen_height, base_y_offset=0):
        self.image = pygame.image.load(image_path).convert()
        # Scale to 2.0x width to allow for non-looping scroll
        self.image = pygame.transform.scale(self.image, (int(screen_width * 2.0), screen_height + 250))
        
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Center the image initially relative to screen
        # Image is wider than screen. We want center of image to be at center of screen.
        # scroll_x represents the X coordinate where the image is drawn.
        # Initial X: (screen_width - image_width) / 2
        
        self.initial_x = (screen_width - self.width) / 2.0
        self.current_x = self.initial_x
        
        self.scroll_factor_x = scroll_factor_x
        self.scroll_factor_y = scroll_factor_y
        self.base_y_offset = base_y_offset
        self.smoothed_curve = 0.0 # Smoothing state
        
    def update(self, dt, curve_value, player_speed):
        # Smoothing (Low-pass filter)
        # Factor 2.0 * dt -> fast but smooth response
        smooth_factor = 5.0 * dt
        self.smoothed_curve += (curve_value - self.smoothed_curve) * smooth_factor
        
        # User Request: Stop on straight lines, move only on curves
        # Apply threshold on SMOOTHED value for stability
        use_curve = self.smoothed_curve
        if abs(use_curve) < 0.005: # Slight deadzone
             use_curve = 0.0
             
        move_speed = -use_curve * player_speed * self.scroll_factor_x
            
        self.current_x += move_speed * dt
        
        # Clamp Logic (Stop at edges)
        # Max X (Left Limit): 0 (Left edge of image at left edge of screen)
        # Min X (Right Limit): screen_width - image_width (Right edge of image at right edge of screen)
        
        min_x = self.screen_width - self.width
        max_x = 0
        
        if self.current_x < min_x:
            self.current_x = min_x
        elif self.current_x > max_x:
            self.current_x = max_x

    def draw(self, screen, pitch_offset_y=0):
        draw_y = self.base_y_offset + (pitch_offset_y * self.scroll_factor_y)
        
        # Split Rendering
        # Top: Fixed (Center of image)
        # Bottom: Scrolled (current_x)
        
        # Split point: HORIZON_Y
        
        # 1. Draw Top (Sky) - Fixed -> CHANGED to Scrolled
        # Clip to top rect
        screen.set_clip(0, 0, self.screen_width, HORIZON_Y)
        # Using current_x instead of initial_x to allow sky to move
        screen.blit(self.image, (self.current_x, draw_y))
        
        # 2. Draw Bottom (Ground) - Scrolled
        # Clip to bottom rect
        screen.set_clip(0, HORIZON_Y, self.screen_width, self.screen_height - HORIZON_Y)
        screen.blit(self.image, (self.current_x, draw_y))
        
        # Reset Clip
        screen.set_clip(None)

class GroundLayer:
    # スクロールの状態を一切持たない。横は draw() の road_x_offset（＝道路が帯の最上段を
    # 貫く画面位置）、縦は player_z だけで決まる純粋な関数になっている。BackgroundLayer の
    # ような時間積分ではないため、直線では必ず中央へ戻り、フレームレートにも依存しない。
    def __init__(self, image_path, screen_width, screen_height):
        # Load source and crop bottom section
        src_img = pygame.image.load(image_path).convert()
        
        # Scale width 2.0x like main BG
        # Increase height significantly to ensure we have enough "ground" pixels
        target_total_height = 1200
        scaled_img = pygame.transform.scale(src_img, (int(screen_width * 2.0), target_total_height))
        
        # Crop Height: Use the bottom section of the image, starting 200px below the horizon
        # Reference Start Position -> y+200 (relative to horizon line on image)
        base_horizon_on_image = target_total_height // 2
        crop_start_y = base_horizon_on_image + 200 
        
        self.texture_height = target_total_height - crop_start_y
        
        crop_rect = pygame.Rect(0, crop_start_y, scaled_img.get_width(), self.texture_height)
        self.image = scaled_img.subsurface(crop_rect).copy()
        
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 縦ミップマップ。帯の上端は1ストリップ(2px)でテクスチャを200テクセル以上飛ばすため、
        # 素直に点サンプルすると激しく折り返す。縦を半分ずつ面積平均した列を作っておき、
        # 描画時に飛ばす量に見合うレベルから読むことで、正しいフィルタ結果が1回のblitで得られる。
        # 横は縮まないので模様の左右の形は保たれる。生成は読み込み時の一度きり。
        # level n のテクセル1行 ≒ 元テクスチャの 2^n 行分。
        self.mips = [self.image]
        h = self.height
        while h > 1:
            h = max(1, h // 2)
            self.mips.append(pygame.transform.smoothscale(self.mips[-1], (self.width, h)))

        # Use centralized constant for Y drawing start position
        self.start_y = HORIZON_Y + GROUND_RENDER_OFFSET_Y

    def set_start_y(self, y):
        self.start_y = y

    def draw(self, screen, pitch_offset_y=0, road_x_offset=0.0, player_z=0.0):
        # Raster Effect Loop for Perspective (Pseudo-3D)

        # Apply pitch to start_y
        # pitch_offset_y is passed from BackgroundManager
        # Positive pitch -> Horizon moves down -> start_y moves down
        current_start_y = self.start_y + int(pitch_offset_y)

        # 帯の上端が「地面の地平線」から何px下か。ピッチは地平線ごと帯を動かす見立て
        # なので、ピッチ抜きの start_y から求める（結果としてFOEは地平線+ピッチに乗る）。
        offset = self.start_y - HORIZON_Y
        if offset <= 0: return

        strip_height = 2 # Performance vs Quality tradeoff. 2px is decent.

        # Loop from top of ground (current_start_y) to bottom of screen
        target_height = self.screen_height - current_start_y
        if target_height <= 0: return

        # To optimize, we can lock surfaces, but Pygame handles this mostly.
        # We need to center the scaled strip.

        center_x = self.screen_width // 2

        # 流れの消失点(FOE)を道路に係留する。
        # 横倍率を scale(dy) = a*(offset+dy) と置くと、全流線は scale(dy)=0 となる
        # dy=-offset（＝ちょうど地平線）で一点に収束する。その画面xは
        #     FOE_x = center_x + vp * (1 + offset/H)        … H = target_height
        # なので、これを「道路が帯の最上段を貫く位置」center_x + road_x_offset に一致させる:
        #     vp = road_x_offset * H / (H + offset)
        # こうするとFOEが道路の上に乗るので、道路の左の地面は左下へ、右の地面は真下〜右下へと
        # 道路から離れる向きに扇状に流れる。道路へ横から滑り込む帯ができない。
        # a に依存しない（模様の細かさを変えても係留は保たれる）。
        # H はピッチで変わるため、ここ（描画時）で計算する必要がある。
        vp = road_x_offset * target_height / (target_height + offset)

        # 横倍率の係数 a。テクスチャ幅がワールド上で GROUND_TEXTURE_WORLD_WIDTH 単位を
        # 占めるように決める（導出は定数の説明を参照）。
        a = GROUND_TEXTURE_WORLD_WIDTH / (self.width * CAMERA_HEIGHT)

        # テクスチャの縦サンプリング。行dyが映すワールド奥行きは
        #     z(dy) = CAMERA_HEIGHT * PROJECTION_PLANE_DIST / (offset + dy)
        # なので、テクスチャ座標はその絶対ワールド位置に比例させればよい。閉じた式なので
        # 累積和が要らず、誤差の蓄積もフレームレート依存もない（旧実装は dt で積分した
        # scroll_y を使っていたため、fpsが落ちると道路の進みに対し地面だけが速く流れた）。
        # 符号を反転しているのは、テクスチャのv軸を手前向き（画面下へ進むほどvが増える）に
        # 保つため。画像の上下の向きが従来と変わらない。
        depth_numerator = CAMERA_HEIGHT * PROJECTION_PLANE_DIST
        texels_per_world = self.width / GROUND_TEXTURE_WORLD_WIDTH

        for dy in range(0, target_height, strip_height):
            # 1. 消失点シフト計算（カーブ対応）
            # 上（dy=0）ほど強く、下（dy=target_height）ほど弱い
            shift = vp * (1.0 - dy / target_height)

            # 2. Calculate Scale
            # Scale increases as we go down (dy increases)
            # 帯の上端はテクスチャが画面幅に届かない。水平線の行(z=26471)は画面幅で
            # ワールド70588単位を映すのに対しテクスチャ1枚は24000単位ぶんしかなく、
            # 原理的に約3枚分足りない。さらに消失点シフトで横へずれるため、ずれた先でも
            # 左右端を覆う必要がある（覆えないと隙間から背景画像が覗き、地平線の霧が
            # 途中で切れて見える。大きなカーブでは左端に最大260px以上の隙間が出た）。
            # strip は center_x+shift を中心に width*scale で描かれるので、
            #   左端<=0 かつ 右端>=screen_width には
            #   width*scale >= 2*max(center_x+shift, screen_width-center_x-shift)
            # が要る。+2 は dest_x 側の整数丸めで1px欠けるのを防ぐ余裕。
            # 引き伸ばす分だけ横方向の遠近は嘘になるが、該当するのは上端のごく一部で、
            # そこはミップマップがほぼ平均色まで潰しているため模様が無く見た目に出ない。
            min_width = 2.0 * max(center_x + shift,
                                  self.screen_width - center_x - shift) + 2.0
            scale = max(a * (offset + dy), min_width / self.width)

            # 3. Source Strip Y - この行が映すワールド奥行きから直接求める
            world_z = player_z + depth_numerator / (offset + dy)
            v = -world_z * texels_per_world

            # 4. ミップレベル選択。このストリップが跨ぐテクセル数 |dv| を strip_height 行で
            # 読むので、1行あたり |dv|/strip_height テクセル分を平均したレベルが要る。
            # level n の1行が元テクスチャの 2^n 行分にあたるので n = log2(|dv|/strip_height)。
            dv = strip_height * texels_per_world * depth_numerator / ((offset + dy) ** 2)
            level = 0
            if dv > strip_height:
                level = min(len(self.mips) - 1, int(math.log2(dv / strip_height) + 0.5))
            mip = self.mips[level]
            mip_h = mip.get_height()
            src_y = int(v * mip_h / self.height) % mip_h

            # 5. Handle Wrap-Around for Strip Height
            current_strip_h = int(min(strip_height, target_height - dy))

            # Source Rect
            # We need to handle if src_y + strip_h > mip_h

            if src_y + current_strip_h > mip_h:
                # Part A (End of image)
                h_a = int(mip_h - src_y)
                self._draw_strip(screen, mip, dy, h_a, src_y, scale, center_x, pitch_offset_y, shift)

                # Part B (Start of image)
                h_b = int(current_strip_h - h_a)
                self._draw_strip(screen, mip, dy + h_a, h_b, 0, scale, center_x, pitch_offset_y, shift)
            else:

                # Single part
                self._draw_strip(screen, mip, dy, current_strip_h, src_y, scale, center_x, pitch_offset_y, shift)

    def _draw_strip(self, screen, mip, dy, h, src_y, scale, center_x, pitch_offset_y, shift=0.0):
        if h <= 0: return

        # Extract Strip
        # Full width of the source image (mip は縦だけ縮んでいるので幅は self.width のまま)
        src_rect = pygame.Rect(0, src_y, self.width, h)
        try:
            strip_surf = mip.subsurface(src_rect)
        except ValueError:
            return

        # Scale Strip
        # New width = self.width * scale
        new_width = int(self.width * scale)
        if new_width <= 0: return
        
        scaled_strip = pygame.transform.scale(strip_surf, (new_width, h))
        
        # Draw Centered with Curve Shift（消失点シフト適用）
        dest_x = center_x - (new_width // 2) + int(shift)
        dest_y = self.start_y + int(pitch_offset_y) + dy

        
        # Clip X to screen (optional, blit handles it but optimization?)
        screen.blit(scaled_strip, (dest_x, dest_y))

class BackgroundManager:
    def __init__(self, screen_width, screen_height):
        self.layers = []
        self.ground_layer = None # Experimental
        self.current_stage_id = -1
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ground_offset = GROUND_RENDER_OFFSET_Y
        self.road_x_offset = 0.0  # 帯の最上段を道路が貫く画面x（中央からのオフセット）
        self.camera_y_offset = 0.0  # 道路カメラ高さに連動するオフセット（消失点同期用）
    
    def get_ground_top_depth(self):
        """地面テクスチャの帯の最上段が対応する奥行き z を返す（係留用）。

        帯の最上段は画面 y = HORIZON_Y + ground_offset。道路の投影式
            screen_y = HORIZON_Y + CAMERA_HEIGHT * (PROJECTION_PLANE_DIST / z)
        を z について解いた値。ground_offset はデバッグキーで実行中に変わるため、
        定数ではなくメソッドで都度求める。
        """
        if self.ground_offset <= 0:
            return DRAW_DISTANCE
        return PROJECTION_PLANE_DIST * CAMERA_HEIGHT / self.ground_offset

    def set_road_anchor(self, road_screen_offset):
        """地面テクスチャの流れの消失点を係留する道路の画面位置を設定する。

        road_screen_offset は「帯の最上段(get_ground_top_depth()の奥行き)における
        道路中心が、画面中央から何px横にずれているか」。実際の消失点シフト量への
        変換は GroundLayer.draw が行う（ピッチで帯の高さが変わるため）。
        """
        self.road_x_offset = road_screen_offset


    def set_camera_y_offset(self, camera_y):
        """道路のカメラ高さからオフセットを計算（消失点同期用）
        
        道路の投影式: screen_y = HORIZON_Y - (rel_y * scale)
        rel_y = world_y - (player_y + CAMERA_HEIGHT)
        
        camera_yが変化すると、遠方のセグメント（scale小）でも消失点がずれる。
        この変化を背景にも適用することで同期を取る。
        
        camera_y が増加（上り坂）→ 消失点が上へ → 背景も上へ
        camera_y が減少（下り坂）→ 消失点が下へ → 背景も下へ
        """
        # 係数はトラックのスケール計算と整合させる
        # 遠方（z=DRAW_DISTANCE）でのscale ≈ 300/50000 = 0.006
        # camera_y変化の影響: Δy_screen ≈ camera_y * 0.006 * 調整係数
        # 調整係数を経験的に設定（道路描画と視覚的に一致するよう調整）
        raw_offset = camera_y * 0.02  # 調整係数
        # クランプ: 極端な高低差での描画位置ずれを防止（±15pxに制限）
        self.camera_y_offset = max(-15.0, min(15.0, raw_offset))
    
    def adjust_ground_offset(self, delta):
        self.ground_offset += delta
        print(f"Ground Offset: {self.ground_offset}")
        if self.ground_layer:
            self.ground_layer.set_start_y(HORIZON_Y + self.ground_offset)

        
    def set_stage(self, stage_id):
        if self.current_stage_id == stage_id:
            return
            
        self.current_stage_id = stage_id
        self.layers.clear()
        self.ground_layer = None # Reset ground layer
        
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        bg_file = cfg.get("bg_image")
        ground_file = cfg.get("ground_image", bg_file) # Use ground_image if exists, else fallback to bg
        bg_offset = cfg.get("bg_offset_y", 0)
        
        if bg_file:
            # For now, creating just ONE layer as requested ("Start considering... layer count not too high")
            # But we make it a "Far" layer with low movement?
            # User said "Far layer small shake".
            # Let's add the main background as a "Mid/Far" layer.
            # Factor X: 0.06 (Reduced from 0.17 to 1/3 again)
            # Factor Y: 0.1 (Slight vertical shift)
            # 下のBackgroundLayer(bg_file, 0.06←ここは背景のy軸
            # BackgroundLayer(bg_file, 0.06 ...) -> Changed to 0.02 -> 0.01 (Half speed)
            layer = BackgroundLayer(bg_file, 0.01, 0.1, self.screen_width, self.screen_height, base_y_offset=bg_offset)
            self.layers.append(layer)
            
            # Experimental Ground Layer initialization
            # Use dedicated ground file if available
            self.ground_layer = GroundLayer(ground_file, self.screen_width, self.screen_height)
            # Sync with current dynamic offset
            self.ground_layer.set_start_y(HORIZON_Y + self.ground_offset)

            
    def get_fog_color(self, stage_id):
        # Allow checking config override first
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        if 'fog_color' in cfg:
            return cfg['fog_color']

        # Otherwise sample from the first layer (Main BG)
        if self.layers:
            layer = self.layers[0]
            # Calculate sample Y relative to image
            # layer.image is scaled to SCREEN_HEIGHT + 120
            # We want screen Y = HORIZON_Y - 5
            # Screen Y = Image Y + base_offset + (pitch * factor)
            # Ignoring pitch for sampling base color is safer/simpler
            # Image Y = Screen Y - base_offset
            
            sample_y = max(0, min(layer.height - 1, HORIZON_Y - 5 - layer.base_y_offset))
            try:
                # Sample center X
                # Center of the image relative to the image surface itself is width // 2
                # Since top half is centered on screen, sampling image center is correct for horizon color.
                return layer.image.get_at((layer.width // 2, sample_y))[:3]
            except Exception as e:
                from .logger import log_warn
                log_warn(f"get_fog_color sample failed: {e}")

        return None
    
    def update(self, dt, curve_value, player_speed):
        for layer in self.layers:
            layer.update(dt, curve_value, player_speed)
        # GroundLayer は状態を持たない（縦は player_z、横は road_x_offset から描画時に決まる）
    
    def _interpolate_color(self, c1, c2, t):
        """線形補間で2色を混合"""
        t = max(0.0, min(1.0, t))
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return (r, g, b)
    
    def _sample_bg_color_at_y(self, screen_y):
        """BackgroundLayerから指定Y座標の色をサンプリング"""
        if not self.layers:
            return (100, 100, 100)
        layer = self.layers[0]
        # Image Y = Screen Y - base_offset
        img_y = int(max(0, min(layer.height - 1, screen_y - layer.base_y_offset)))
        try:
            return layer.image.get_at((layer.width // 2, img_y))[:3]
        except Exception as e:
            from .logger import log_warn
            log_warn(f"_sample_bg_color_at_y failed: {e}")
            return (100, 100, 100)
    
    def _sample_ground_color(self):
        """GroundLayerの平均的な色を返す（スクロールに連動しない固定色）

        最も粗いミップ（高さ1px＝テクスチャを縦に全平均したもの）の中央列を読む。
        帯の上端は遠方ほど強いミップが効いてこの色そのものへ収束するので、グラデーション帯を
        同じ色で作れば継ぎ目が出ない。以前は3点を拾う近似で、真の平均と数階調ずれていた。
        """
        if not self.ground_layer:
            return (80, 60, 40)
        try:
            coarsest = self.ground_layer.mips[-1]
            return coarsest.get_at((self.ground_layer.width // 2, 0))[:3]
        except Exception as e:
            from .logger import log_warn
            log_warn(f"_sample_ground_color failed: {e}")
            return (80, 60, 40)
    
    def _compute_tunnel_haze_mult(self, player_z):
        """トンネル入口手前〜区間内〜出口後にかけて、地平線ヘイズの不透明度倍率(0〜1)を計算

        ステージに複数のトンネル区間がありうるため、各区間ごとの倍率のうち最小値
        （＝最も強く隠すべき区間の値）を採用する。区間から離れていれば全て1.0になる。
        """
        if player_z is None:
            return 1.0
        cfg = STAGE_CONFIG.get(self.current_stage_id, {})
        tunnels = cfg.get('tunnels', [])
        if not tunnels:
            return 1.0
        fade = TUNNEL_HAZE_FADE_DISTANCE
        mult = 1.0
        for t in tunnels:
            tunnel_start = t['start_z']
            tunnel_end = tunnel_start + t['length']
            # 完全非表示になる境界（入口手前/出口先のマージン込み）
            hide_start = tunnel_start - TUNNEL_HAZE_HIDE_MARGIN
            hide_end = tunnel_end + TUNNEL_HAZE_HIDE_MARGIN
            if player_z < hide_start - fade:
                m = 1.0
            elif player_z < hide_start:
                m = (hide_start - player_z) / fade
            elif player_z < hide_end:
                m = 0.0
            elif player_z < hide_end + fade:
                m = (player_z - hide_end) / fade
            else:
                m = 1.0
            mult = min(mult, m)
        return mult

    def _compute_overlay_haze_mult(self, player_z):
        """main.py側の霧オーバーレイ用倍率。坑口の山は各トンネルの入口が描画距離
        （DRAW_DISTANCE）に入った時点から画面に写るため、区間ごとにその手前から
        即座に非表示にする（フェード区間は設けない）。出口側は通常どおり山が
        見えなくなった後にフェードで復帰する。複数区間ある場合は最小値を採用する。"""
        if player_z is None:
            return 1.0
        cfg = STAGE_CONFIG.get(self.current_stage_id, {})
        tunnels = cfg.get('tunnels', [])
        if not tunnels:
            return 1.0
        fade = TUNNEL_HAZE_FADE_DISTANCE
        mult = 1.0
        for t in tunnels:
            tunnel_start = t['start_z']
            tunnel_end = tunnel_start + t['length']
            hide_start = tunnel_start - DRAW_DISTANCE
            hide_end = tunnel_end + TUNNEL_HAZE_HIDE_MARGIN
            if player_z < hide_start:
                m = 1.0
            elif player_z < hide_end:
                m = 0.0
            elif player_z < hide_end + fade:
                m = (player_z - hide_end) / fade
            else:
                m = 1.0
            mult = min(mult, m)
        return mult

    def _draw_gradient_band(self, screen, pitch_offset):
        """GroundLayer開始位置の手前に2段階グラデーション帯を描画（透明度付き）"""
        if not self.layers or not self.ground_layer:
            return
        
        # ステージ固有の設定を取得
        cfg = STAGE_CONFIG.get(self.current_stage_id, STAGE_CONFIG[1])
        stage_gradient_height = cfg.get('gradient_height', GRADIENT_HEIGHT)
        stage_gradient_height_2 = cfg.get('gradient_height_2', GRADIENT_HEIGHT_2)
        
        # グラデーション帯の終端がGroundLayer開始位置と一致するように配置
        # グラデーション帯の終端がGroundLayer開始位置と一致するように配置
        # Shift with Pitch
        # Use Dynamic Ground Offset
        ground_start_y = HORIZON_Y + self.ground_offset + int(pitch_offset)
        gradient_start_y = ground_start_y - stage_gradient_height


        
        # 色のサンプリング（固定色）
        top_color = self._sample_bg_color_at_y(gradient_start_y)
        ground_color = self._sample_ground_color()
        
        # 下グラデと同じ「平均色」を上グラデの終端色にして境目を滑らかに
        bg_horizon_color = self._sample_bg_color_at_y(HORIZON_Y - 5)  # 上背景（地平線付近）
        blended_bottom_color = self._interpolate_color(bg_horizon_color, ground_color, 0.5)  # 50%平均
        
        # === 上段グラデーション（メイン） ===
        gradient_surface = pygame.Surface((self.screen_width, stage_gradient_height), pygame.SRCALPHA)
        for i in range(stage_gradient_height):
            t = i / float(stage_gradient_height)  # 0.0 ~ 1.0
            # 上端はtop_color、下端は平均色（blended_bottom_color）
            color = self._interpolate_color(top_color, blended_bottom_color, t)
            # 上端は透明、下端は半透明（非線形：上側が薄く、下側が濃い）
            fade = t ** 2  # 2乗で上側が薄く、下側が濃い
            alpha = int(fade * 180 * self._tunnel_haze_mult)  # 下グラデと同じ180に統一
            pygame.draw.line(gradient_surface, (*color, alpha), (0, i), (self.screen_width, i))
        screen.blit(gradient_surface, (0, gradient_start_y))
        
        # 上段グラデの高さを保存（デバッグ用）
        self._last_gradient_height = stage_gradient_height
        
        # === 下段グラデーション：設定を保存（描画は別メソッドでGroundLayerの後に行う） ===
        # 「上背景」と「縦スクロールテクスチャ」の平均色を使用
        bg_color = self._sample_bg_color_at_y(HORIZON_Y - 5)  # 上背景（地平線付近）
        ground_color = self._sample_ground_color()             # 縦スクロールテクスチャ
        blended_base = self._interpolate_color(bg_color, ground_color, 0.5)  # 50%平均
        
        # さらに霧色をブレンドする場合
        fog_blend_ratio = cfg.get('fog_blend_ratio', 0.0)
        if fog_blend_ratio > 0:
            fog_color = (255, 255, 255)  # 白
            self._lower_gradient_color = self._interpolate_color(blended_base, fog_color, fog_blend_ratio)
        else:
            self._lower_gradient_color = blended_base
        
        
        # Store BASE start_y (without pitch)
        self._lower_gradient_base_start_y = HORIZON_Y + self.ground_offset
        self._lower_gradient_height = stage_gradient_height_2


        
        # 下段グラデの高さを保存（デバッグ用）
        self._last_gradient2_height = stage_gradient_height_2
        
        # === 霧グラデーション（白、ステージ固有）は別メソッドで描画 ===
        # 霧の設定を保存
        if cfg.get('fog_gradient', False):
            self._fog_enabled = True
            self._fog_height = cfg.get('fog_gradient_height', 60)
            self._fog_offset = cfg.get('fog_gradient_offset', 30)
            # Store BASE start_y (without pitch)
            self._fog_base_start_y = HORIZON_Y + self.ground_offset + self._fog_offset
        else:

            self._fog_enabled = False
            self._fog_base_start_y = None
            self._fog_height = None
    
    def _draw_lower_gradient(self, screen, pitch_offset):
        """下段グラデーションを描画（GroundLayerの後に呼び出す）"""
        
        blended_color = getattr(self, '_lower_gradient_color', (80, 60, 40))
        # Use BASE + pitch
        start_y = getattr(self, '_lower_gradient_base_start_y', 340) + int(pitch_offset)
        height = getattr(self, '_lower_gradient_height', 40)


        
        gradient_surface = pygame.Surface((self.screen_width, height), pygame.SRCALPHA)
        for i in range(height):
            t = i / float(height)  # 0.0 ~ 1.0
            # 下段は非線形フェードアウト（2乗減衰：上側が濃く、下側が長く薄い）
            fade = (1.0 - t) ** 2
            alpha = int(fade * 180 * self._tunnel_haze_mult)  # 最大180で強めに
            pygame.draw.line(gradient_surface, (*blended_color, alpha), (0, i), (self.screen_width, i))
        screen.blit(gradient_surface, (0, start_y))
    
    def _draw_fog_gradient(self, screen, pitch_offset):
        """霧グラデーションを描画（GroundLayerの後に呼び出す）"""
        if not getattr(self, '_fog_enabled', False):
            return
        
        fog_height = self._fog_height
        # Use BASE + pitch
        fog_start_y = getattr(self, '_fog_base_start_y', 370) + int(pitch_offset)

        
        fog_surface = pygame.Surface((self.screen_width, fog_height), pygame.SRCALPHA)
        # 霧の色を地平線付近の背景色からサンプリング（白ではなく自然な色に）
        fog_color = self._sample_bg_color_at_y(HORIZON_Y - 5)
        for i in range(fog_height):
            t = i / float(fog_height)  # 0.0 ~ 1.0
            # 不透明から透明へ非線形フェードアウト（2乗減衰で下部が長く薄い）
            fade = (1.0 - t) ** 2  # 2乗で上部は濃く、下部は長く薄く
            alpha = int(fade * 100 * self._tunnel_haze_mult)  # 最大100で強めに
            pygame.draw.line(fog_surface, (*fog_color, alpha), (0, i), (self.screen_width, i))
        screen.blit(fog_surface, (0, fog_start_y))
            
    def draw(self, screen, pitch_offset=0, player_z=None):
        # 道路カメラ高さと勾配ピッチのオフセットを合成
        # camera_y_offset: 道路の消失点変化（高さ由来）
        # pitch_offset: 勾配による背景の上下移動
        raw_combined = pitch_offset + self.camera_y_offset
        # クランプ: 合計オフセットを ±15px に制限（極端な高低差での描画位置ずれを防止）
        combined_offset = max(-15.0, min(15.0, raw_combined))
        # デバッグ用に生の値も保持
        self._debug_raw_combined = raw_combined

        # トンネル区間では地平線ヘイズ（上段/下段グラデ・霧グラデ）を手前からフェードアウト
        self._tunnel_haze_mult = self._compute_tunnel_haze_mult(player_z)
        # main.py側の霧オーバーレイ用（坑口の山が見える間は即座に非表示）
        self._overlay_haze_mult = self._compute_overlay_haze_mult(player_z)
        
        for layer in self.layers:
            layer.draw(screen, pitch_offset)  # 背景レイヤーは従来通り
        
        # 上段グラデーション帯を描画（GroundLayerの前）
        self._draw_gradient_band(screen, combined_offset)
        
        if self.ground_layer:
            self.ground_layer.draw(screen, combined_offset, self.road_x_offset,
                                   player_z if player_z is not None else 0.0)

        
        # 下段グラデーションを描画（GroundLayerの後）
        self._draw_lower_gradient(screen, combined_offset)

        
        # 霧グラデーションを描画（最上位）
        self._draw_fog_gradient(screen, combined_offset)

