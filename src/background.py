import pygame
from .track import STAGE_CONFIG, HORIZON_Y

# --- Ground Layer Config ---
GROUND_RENDER_OFFSET_Y = 17 # Adjusts the Y start position of the ground layer relative to HORIZON_Y

# --- Gradient Smoothing Config ---
GRADIENT_HEIGHT = 20  # グラデーション帯の高さ（上段、50%縮小）
GRADIENT_HEIGHT_2 = 40  # 2段目の緩いグラデーションの高さ

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
    def __init__(self, image_path, scroll_factor_x, factor_y_speed, screen_width, screen_height):
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
        
        # Use centralized constant for Y drawing start position
        self.start_y = HORIZON_Y + GROUND_RENDER_OFFSET_Y
        
        self.scroll_x = (screen_width - self.width) / 2.0 # Center
        self.scroll_y = 0.0
        
        self.scroll_factor_x = scroll_factor_x
        self.factor_y_speed = factor_y_speed # Speed multiplier for Y scroll

    def set_start_y(self, y):
        self.start_y = y
        
    def update(self, dt, curve_value, player_speed):
        # X: Curve Link (Same as BG)
        move_speed = -curve_value * player_speed * self.scroll_factor_x
        self.scroll_x += move_speed * dt
        
        # Clamp X logic (Same as BG)
        min_x = self.screen_width - self.width
        max_x = 0
        if self.scroll_x < min_x: self.scroll_x = min_x
        elif self.scroll_x > max_x: self.scroll_x = max_x
        
        # Y: Speed Link (Forward Motion -> Texture moves Down)
        # To make texture move DOWN (approach player), we need the source sampling window to move UP.
        # Moving window UP means decreasing src_y.
        # So scroll_y should decrease.
        self.scroll_y -= player_speed * self.factor_y_speed * dt

    def draw(self, screen, pitch_offset_y=0, vp_x_offset=0.0):
        # Raster Effect Loop for Perspective (Pseudo-3D)
        
        # Apply pitch to start_y
        # pitch_offset_y is passed from BackgroundManager
        # Positive pitch -> Horizon moves down -> start_y moves down
        current_start_y = self.start_y + int(pitch_offset_y)

        
        # Perspective Factor (k)
        # User requested "10x" stronger feel. 
        # k = 0.001 -> Adds 100% width over 1000px.
        # k = 0.01 -> Adds 100% width over 100px.
        # Screen height part to cover is approx 350px.
        # With k=0.01, at bottom (dy=350), scale = 1.0 + 3.5 = 4.5x. This is strong.
        k = 0.01 
        
        strip_height = 2 # Performance vs Quality tradeoff. 2px is decent.
        
        # Loop from top of ground (current_start_y) to bottom of screen
        target_height = self.screen_height - current_start_y
        if target_height <= 0: return

        # 定数（track.pyと整合）
        PROJECTION_PLANE_DIST = 300.0
        CAMERA_HEIGHT = 1500.0

        # To optimize, we can lock surfaces, but Pygame handles this mostly.
        # We need to center the scaled strip.
        
        center_x = self.screen_width // 2
        
        # 累積的アプローチ：スクロール開始位置から累積的にサンプリング
        # scroll_y をモジュロで正規化した位置から開始
        base_src_y = self.scroll_y % self.height  # 開始位置（負対応）
        cumulative_src_y = base_src_y
        
        for dy in range(0, target_height, strip_height):
            # 1. Calculate Scale
            # Scale increases as we go down (dy increases)
            scale = 1.0 + (dy * k)
            
            # 2. 消失点シフト計算（カーブ対応）
            # 上（dy=0）ほど強く、下（dy=target_height）ほど弱い
            shift = vp_x_offset * (1.0 - dy / target_height)
            
            # 3. Source Strip Y - 累積的アプローチ（ジャンプ防止）
            # 奥行きに応じたサンプリング増分を計算
            # dyが小さい（遠方）→ zが大きい → 増分小（テクスチャ密に読む）
            # dyが大きい（手前）→ zが小さい → 増分大（テクスチャまばらに読む）
            z = PROJECTION_PLANE_DIST * CAMERA_HEIGHT / max(1, dy + 1)
            # 増分係数：手前ほど大きく増分（テクスチャをスキップ）
            # 基準はdy=target_height/2のラインで1.0
            increment_factor = (target_height / 2) / max(1, dy + 1)
            
            # 現在の累積位置をモジュロで正規化
            src_y = int(cumulative_src_y % self.height)
            
            # 次のラインへの増分を加算
            # strip_height * increment_factor でテクスチャ上の移動量を計算
            cumulative_src_y += strip_height * increment_factor
            
            # 4. Handle Wrap-Around for Strip Height
            current_strip_h = int(min(strip_height, target_height - dy))
            
            # Source Rect
            # We need to handle if src_y + strip_h > self.height
            
            if src_y + current_strip_h > self.height:
                # Part A (End of image)
                h_a = int(self.height - src_y)
                self._draw_strip(screen, dy, h_a, src_y, scale, center_x, pitch_offset_y, shift)

                
                # Part B (Start of image)
                h_b = int(current_strip_h - h_a)
                self._draw_strip(screen, dy + h_a, h_b, 0, scale, center_x, pitch_offset_y, shift)
            else:

                # Single part
                self._draw_strip(screen, dy, current_strip_h, src_y, scale, center_x, pitch_offset_y, shift)

    def _draw_strip(self, screen, dy, h, src_y, scale, center_x, pitch_offset_y, shift=0.0):
        if h <= 0: return

        
        # Extract Strip
        # Full width of the source image
        src_rect = pygame.Rect(0, src_y, self.width, h)
        try:
            strip_surf = self.image.subsurface(src_rect)
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
        self.curve_offset = 0.0  # カーブに連動する消失点オフセット
        self.camera_y_offset = 0.0  # 道路カメラ高さに連動するオフセット（消失点同期用）
    
    def set_curve_offset(self, curve_accumulated):
        """カーブ累積値から地面の消失点オフセットを設定"""
        # 道路より控えめに動かす（0.3は調整可能）
        self.curve_offset = curve_accumulated * 0.3
    
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
            self.ground_layer = GroundLayer(ground_file, 0.1, 2.3, self.screen_width, self.screen_height)  # 2.3x speed
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
            except:
                pass
                
        return None
    
    def update(self, dt, curve_value, player_speed):
        for layer in self.layers:
            layer.update(dt, curve_value, player_speed)
        
        if self.ground_layer:
            self.ground_layer.update(dt, curve_value, player_speed)
    
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
        except:
            return (100, 100, 100)
    
    def _sample_ground_color(self):
        """GroundLayerの平均的な色をサンプリング（スクロールに連動しない固定色）"""
        if not self.ground_layer:
            return (80, 60, 40)
        try:
            # テクスチャの複数ポイントからサンプリングして平均色を取得（ちらつき防止）
            samples = []
            for sample_y in [0, self.ground_layer.height // 4, self.ground_layer.height // 2]:
                color = self.ground_layer.image.get_at((self.ground_layer.width // 2, sample_y))[:3]
                samples.append(color)
            # 平均色を計算
            avg_r = sum(c[0] for c in samples) // len(samples)
            avg_g = sum(c[1] for c in samples) // len(samples)
            avg_b = sum(c[2] for c in samples) // len(samples)
            return (avg_r, avg_g, avg_b)
        except:
            return (80, 60, 40)
    
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
            alpha = int(fade * 180)  # 下グラデと同じ180に統一
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
            alpha = int(fade * 180)  # 最大180で強めに
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
            alpha = int(fade * 100)  # 最大100で強めに
            pygame.draw.line(fog_surface, (*fog_color, alpha), (0, i), (self.screen_width, i))
        screen.blit(fog_surface, (0, fog_start_y))
            
    def draw(self, screen, pitch_offset=0):
        # 道路カメラ高さと勾配ピッチのオフセットを合成
        # camera_y_offset: 道路の消失点変化（高さ由来）
        # pitch_offset: 勾配による背景の上下移動
        raw_combined = pitch_offset + self.camera_y_offset
        # クランプ: 合計オフセットを ±15px に制限（極端な高低差での描画位置ずれを防止）
        combined_offset = max(-15.0, min(15.0, raw_combined))
        # デバッグ用に生の値も保持
        self._debug_raw_combined = raw_combined
        
        for layer in self.layers:
            layer.draw(screen, pitch_offset)  # 背景レイヤーは従来通り
        
        # 上段グラデーション帯を描画（GroundLayerの前）
        self._draw_gradient_band(screen, combined_offset)
        
        if self.ground_layer:
            self.ground_layer.draw(screen, combined_offset, self.curve_offset)

        
        # 下段グラデーションを描画（GroundLayerの後）
        self._draw_lower_gradient(screen, combined_offset)

        
        # 霧グラデーションを描画（最上位）
        self._draw_fog_gradient(screen, combined_offset)

