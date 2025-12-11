import pygame
import random
import math

# --- Constants & Config ---
STRIPE_LENGTH = 300.0
ROAD_WORLD_WIDTH = 3388.0

# Curb Settings
CURB_WIDTH_RATIO = 0.06       # 道路幅に対する縁石幅の比率（6%、さらに10%増）
CURB_START_ZONE = 20000.0     # 200m = 20,000 world units（両端に縁石を表示する区間）
CURB_CURVE_THRESHOLD = 1.5    # この値以上のカーブで縁石を表示（大きなカーブのみ）
CURB_RED = (220, 50, 50)      # 縁石の赤色
CURB_WHITE = (255, 255, 255)  # 縁石の白色
CURB_BORDER_COLOR = (30, 30, 30)  # 境界線の色（濃いグレー）

# Road Edge Smoothing Settings (疑似アンチエイリアス)
EDGE_SMOOTHING_ENABLED = False  # [TEST] 一時的に無効化
EDGE_SMOOTHING_ALPHA = 100      # 半透明度（0-255、低いほど透明）

# Road Edge Roughness Settings (でこぼこ)
EDGE_ROUGHNESS_ENABLED = True   # でこぼこ有効/無効
EDGE_ROUGHNESS_AMOUNT = 22.0    # でこぼこの最大ピクセル数

PROJECTION_PLANE_DIST = 300.0
HORIZON_Y = 300
CAMERA_HEIGHT = 1500.0
DRAW_DISTANCE = 50000.0
GOAL_DISTANCE = 600000.0

STAGE_CONFIG = {
    1: { 
        'sky_color': (100, 149, 237), 'grass_color': (34, 139, 34),
        'road_light': (105, 105, 105), 'road_dark': (95, 95, 95),
        'bg_image': 'asset/bg1.png', 'ground_image': 'asset/bg1v.png', 'bg_offset_y': -140,
        'curve_freq': 0.05, 'curve_amp': 30.0,
        'curve_mult': 0.8,
        'sharp_prob': 0.1, 's_curve_prob': 0.1,
        'curb_enabled': True
    },
    2: { 
        'sky_color': (255, 140, 0), 'grass_color': (210, 180, 140),
        'road_light': (110, 110, 110), 'road_dark': (100, 100, 100),
        'bg_image': 'asset/bg2.png', 'ground_image': 'asset/bg2v.png', 'bg_offset_y': -135,
        'curve_freq': 0.08, 'curve_amp': 60.0,
        'curve_mult': 1.0,
        'sharp_prob': 0.2, 's_curve_prob': 0.2,
        'curb_enabled': True
    },
    3: { 
        'sky_color': (20, 40, 110), 'grass_color': (20, 20, 20),
        'road_light': (120, 120, 130), 'road_dark': (110, 110, 120),
        'bg_image': 'asset/bg3.png', 'ground_image': 'asset/bg3v.png', 'bg_offset_y': -169,
        'curve_freq': 0.1, 'curve_amp': 90.0,
        'curve_mult': 1.2,
        'sharp_prob': 0.3, 's_curve_prob': 0.4,
        'curb_enabled': True
    },
    4: { 
        'sky_color': (200, 240, 255), 'grass_color': (139, 69, 19),
        'road_light': (130, 130, 130), 'road_dark': (120, 120, 120),
        'bg_image': 'asset/bg4.png', 'ground_image': 'asset/bg4v.png', 'bg_offset_y': -175, 
        'fog_color': (190, 160, 130),  # 明るい砂漠色（背景に馴染む）
        'curve_freq': 0.04, 'curve_amp': 50.0,
        'curve_mult': 1.5,
        'sharp_prob': 0.5, 's_curve_prob': 0.3,
        'curb_enabled': False,  # ステージ4は縁石なし
        'sand_enabled': True,   # 砂粒子を有効化
        'sand_color': (230, 200, 100),  # 砂の色（明るい黄色）
        'fog_gradient': True,  # [TEST] 霧グラデーション有効化
        'fog_gradient_height': 80,  # 霧の高さ
        'fog_gradient_offset': 0  # 水平線からのオフセット
    },
    5: { 
        'sky_color': (100, 149, 237), 'grass_color': (34, 139, 34),
        'road_light': (105, 105, 105), 'road_dark': (95, 95, 95),
        'bg_image': 'asset/bg5.png', 'ground_image': 'asset/bg5v.png', 'bg_offset_y': -135,
        'curve_freq': 0.12, 'curve_amp': 80.0,
        'curve_mult': 1.8,
        'sharp_prob': 0.6, 's_curve_prob': 0.3,
        'curb_enabled': True,
        'fog_color': (175, 185, 195), # Keep for curbs/edges base
        'road_fog_color': (169, 171, 166), # User specified grey
        'fog_gradient': True,        # 霧グラデーションを有効化
        'fog_gradient_height': 80,   # 霧の高さ
        'fog_gradient_offset': 0     # 開始位置（下段グラデ開始から）
    },
}

class Track:
    def __init__(self):
        self.segments = []
        self.goal_distance = GOAL_DISTANCE
        self.goal_distance = GOAL_DISTANCE
        self.stripe_length = STRIPE_LENGTH
    
    def project(self, world_x, world_y, world_z, road_offset, screen_width, screen_height):
        if world_z <= 0: return None
        scale = PROJECTION_PLANE_DIST / world_z
        # New Projection Formula taking world_y into account
        # screen_y = HORIZON + (CAMERA_HEIGHT - (world_y - player_y)) * scale
        # But here we pass relative world coords? 
        # Actually proper 3D projection:
        # y_screen = (y_world - y_camera) * scale + y_center
        # In our case, HORIZON_Y is the vanishing point Y.
        # CAMERA_HEIGHT is the height of camera *above the road* (usually).
        # We need to act as if the camera is at (0, ry, 0) and the point is at (rx, ry_point, rz).
        # In current logic: screen_y = HORIZON_Y + (CAMERA_HEIGHT * scale)
        # This implies world_y was 0 (relative to camera's ground) and camera was at +CAMERA_HEIGHT.
        # So effective relative Y is (world_y - camera_abs_y).
        
        # Let's assume the argument world_y passed here is RELATIVE to the Camera Y (y_point - y_camera).
        # If camera is at height 1500, and road is at 0, relative Y is -1500.
        # ScreenY = Horizon - (relative_y * scale)
        # Check old formula: H + 1500*scale.
        # If relative Y is -1500, H - (-1500 * scale) = H + 1500*scale. Matches.
        
        # So we just use:
        screen_y = HORIZON_Y - (world_y * scale)
        
        screen_x = (screen_width / 2) + (world_x * scale) - (road_offset * scale * 2.5) 
        return screen_x, screen_y, scale

    def add_segment_sequence(self, num, curve, slope, color_light, color_dark):
        start_idx = len(self.segments)
        # Get height of last segment to continue continuity
        last_y = 0.0
        if start_idx > 0:
            last_y = self.segments[-1]['p2']['y']
            
        for i in range(num):
            idx = start_idx + i
            
            # Calculate Y based on slope
            # Slope = dy / dz (approx).
            # If slope is 0.05 (5%), per 300 units Z, Y changes 15 units.
            # Y increases = Uphill?
            # Visually, Up on screen is negative Y. In 3D world, usually Y is up.
            # Let's stick to Y is Up (Positive).
            
            p1_y = last_y + (slope * STRIPE_LENGTH * i) # Wait, this is linear within the batch? No it should be cumulative.
            # No, 'slope' is constant for this sequence.
            # So calculating incrementally is safer.
            
            # Let's track expected current y
            this_p1_y = last_y
            this_p2_y = last_y + (slope * STRIPE_LENGTH)
            
            p1 = {'z': idx * STRIPE_LENGTH, 'y': this_p1_y}
            p2 = {'z': (idx + 1) * STRIPE_LENGTH, 'y': this_p2_y}
            
            color = color_light if (idx % 2 == 0) else color_dark
            
            self.segments.append({
                'index': idx,
                'p1': p1, 'p2': p2,
                'color': color, 'curve': curve,
            })
            
            last_y = this_p2_y 


    def create_road(self, s_id):
        self.segments.clear()
        cfg = STAGE_CONFIG.get(s_id, STAGE_CONFIG[1])
        c_light = cfg["road_light"]
        c_dark = cfg["road_dark"]
        c_mult = cfg["curve_mult"]
        
        rnd = random.Random(s_id)
        
        # 1. Start Line (Flat)
        self.add_segment_sequence(50, 0.0, 0.0, c_light, c_dark)
        
        # 2. Procedural
        current_z = (len(self.segments)) * STRIPE_LENGTH
        remaining_dist = GOAL_DISTANCE - current_z
        
        while remaining_dist > 0:
            r = rnd.random()
            direction = 1 if rnd.random() > 0.5 else -1
            seg_count = rnd.randint(50, 150)
            
            prob_sharp = cfg.get("sharp_prob", 0.2)
            
            # Choose Slope
            # Limit 0-5% (0.0 to 0.05)
            # 30% chance of flat
            # 70% chance of slope
            slope = 0.0
            if rnd.random() < 0.7:
                slope = rnd.uniform(-0.05, 0.05)
                # Quantize slope slightly to be smoother? or raw random is fine.
            
            if r < 0.2: # Straight
                self.add_segment_sequence(seg_count, 0.0, slope, c_light, c_dark)
            elif r < 0.5: # Gentle
                c = rnd.uniform(0.5, 1.5) * direction * c_mult
                self.add_segment_sequence(30, c/2, slope, c_light, c_dark)
                self.add_segment_sequence(seg_count, c, slope, c_light, c_dark) 
                self.add_segment_sequence(30, c/2, slope, c_light, c_dark)
            elif r < (0.5 + prob_sharp): # Medium/Sharp
                c = rnd.uniform(2.0, 4.0) * direction * c_mult
                self.add_segment_sequence(40, c/2, slope, c_light, c_dark)
                self.add_segment_sequence(seg_count, c, slope, c_light, c_dark)
                self.add_segment_sequence(40, c/2, slope, c_light, c_dark)
            else: # S-Curve
                c = rnd.uniform(2.0, 4.0) * direction * c_mult
                self.add_segment_sequence(30, c/2, slope, c_light, c_dark)
                self.add_segment_sequence(40, c, slope, c_light, c_dark)
                self.add_segment_sequence(30, c/2, slope, c_light, c_dark)
                self.add_segment_sequence(30, -c/2, slope, c_light, c_dark)
                self.add_segment_sequence(40, -c, slope, c_light, c_dark)
                self.add_segment_sequence(30, -c/2, slope, c_light, c_dark)

            current_z = (len(self.segments)) * STRIPE_LENGTH
            remaining_dist = GOAL_DISTANCE - current_z
        
        # End Buffer
        self.add_segment_sequence(300, 0.0, 0.0, c_light, c_dark)


    def get_bg_image(self, stage_id):
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        return cfg.get("bg_image", None)

    def get_curve_at(self, z):
        idx = int(z / STRIPE_LENGTH)
        if 0 <= idx < len(self.segments):
            return self.segments[idx]['curve']
        return 0.0
        
    def get_height_at(self, z):
        idx = int(z / STRIPE_LENGTH)
        if 0 <= idx < len(self.segments):
            seg = self.segments[idx]
            # Interpolate height within segment
            # z_local = z % STRIPE_LENGTH
            # This logic assumes z is exact world z.
            p1_z = seg['p1']['z']
            p1_y = seg['p1']['y']
            p2_y = seg['p2']['y']
            
            t = (z - p1_z) / STRIPE_LENGTH
            t = max(0.0, min(1.0, t))
            
            return p1_y + (p2_y - p1_y) * t
            
        return 0.0

    def get_slope_at(self, z):
        """Returns the slope (dy/dz) at the given z position."""
        idx = int(z / STRIPE_LENGTH)
        if 0 <= idx < len(self.segments):
            seg = self.segments[idx]
            p1 = seg['p1']
            p2 = seg['p2']
            dy = p2['y'] - p1['y']
            dz = STRIPE_LENGTH # p2.z - p1.z
            return dy / dz
        return 0.0

    def get_curb_at(self, z, stage_id=1):
        """Returns (has_left_curb, has_right_curb) at the given z position."""
        # Config check
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        if not cfg.get('curb_enabled', False):
            return False, False
            
        # Logic matches draw()
        idx = int(z / STRIPE_LENGTH)
        if 0 <= idx < len(self.segments):
            seg = self.segments[idx]
            seg_z = seg['p1']['z']
            curve_val = seg['curve']
            
            has_left = False
            has_right = False
            
            if seg_z < CURB_START_ZONE:
                # Start zone: both sides
                has_left = True
                has_right = True
            else:
                # After start zone: curve inside only
                if curve_val > CURB_CURVE_THRESHOLD:  # Right curve -> right curb
                    has_right = True
                elif curve_val < -CURB_CURVE_THRESHOLD:  # Left curve -> left curb
                    has_left = True
                    
            return has_left, has_right
            
        return False, False



    @staticmethod
    def interpolate_color(c1, c2, t):
        t = max(0.0, min(1.0, t))
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return (r, g, b)

    def draw(self, screen, player_z, player_x, screen_width, screen_height, stage_id=1, fog_color=None, camera_y=None):
        # Config (fallback for fog)
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        if fog_color is None:
            fog_color = cfg['sky_color']
            
        # Curb enabled check
        curb_enabled = cfg.get('curb_enabled', False)
        
        # Find start segment
        start_idx = int(player_z / STRIPE_LENGTH)
        if start_idx >= len(self.segments): start_idx = len(self.segments) - 1
        
        num_visible = int(DRAW_DISTANCE / STRIPE_LENGTH)
        max_idx = min(len(self.segments) - 1, start_idx + num_visible)
        
        # Curve Accumulation
        render_points = []
        dx = 0.0
        x_turn = 0.0
        
        for i in range(start_idx, max_idx + 2):
            if i > start_idx:
                if i-1 < len(self.segments):
                    dx += self.segments[i-1]['curve']
                x_turn += dx
            
            # Store world y in render points
            world_y = 0.0
            
            render_points.append({
                'z_world': i * STRIPE_LENGTH,
                'x_rel': x_turn,
                'y_world': self.segments[min(i, len(self.segments)-1)]['p1']['y'] # Rough approx for iteration
                # Wait, we need precise Y for p_near and p_far logic later.
                # Actually, in the loop below, we access self.segments[i].
                # We can just get Y from segment p1/p2 there.
                # But 'render_points' structure is accumulating X curve.
                # Let's clean up render_points usage or add Y to it.
                # The loop below uses 'p_near' and 'p_far' from 'render_points'.
                # So we MUST store Y in render_points.
            })
            # Fix Y logic: i corresponds to a specific Z.
            # Z = i * STRIPE_LENGTH.
            # This corresponds to p1 of segment[i] (if i < len), or p2 of segment[i-1].
            actual_y = 0.0
            if i < len(self.segments):
                actual_y = self.segments[i]['p1']['y']
            elif i > 0:
                actual_y = self.segments[i-1]['p2']['y']
                
            render_points[-1]['y_world'] = actual_y

            
        # Draw Back-to-Front
        for i in range(max_idx, start_idx - 1, -1):
             if i >= len(self.segments): continue
             k = i - start_idx
             if k + 1 >= len(render_points): continue
             
             p_near = render_points[k]
             p_far = render_points[k+1]
             seg = self.segments[i]
             
             # Rel coords
             z_near = p_near['z_world'] - player_z
             z_far = p_far['z_world'] - player_z
             rel_x_near = p_near['x_rel'] - player_x
             rel_x_far = p_far['x_rel'] - player_x
             
             # Y Coords (Absolute)
             y_world_near = p_near['y_world']
             y_world_far = p_far['y_world']
             
             # Clip
             if z_near < PROJECTION_PLANE_DIST:
                 if z_far < PROJECTION_PLANE_DIST: continue
                 ratio = (PROJECTION_PLANE_DIST - z_near) / (z_far - z_near)
                 z_near = PROJECTION_PLANE_DIST
                 rel_x_near = rel_x_near + (rel_x_far - rel_x_near) * ratio
                 # Interpolate Y at clip point
                 y_world_near = y_world_near + (y_world_far - y_world_near) * ratio
             
             # Project (Pass camera_y)
             # カメラ高さ（外部から渡されない場合はフォールバック）
             if camera_y is None:
                 player_y = self.get_height_at(player_z)
             else:
                 player_y = camera_y
             
             # Relative Y for projection
             # The camera is at (player_y + CAMERA_HEIGHT).
             # The point is at y_world_near/far.
             # Relative Y = PointY - CameraY
             rel_y_near = y_world_near - (player_y + CAMERA_HEIGHT)
             rel_y_far = y_world_far - (player_y + CAMERA_HEIGHT)
             
             p1_proj = self.project(rel_x_near, rel_y_near, z_near, 0, screen_width, screen_height)
             p2_proj = self.project(rel_x_far, rel_y_far, z_far, 0, screen_width, screen_height)

             
             if not p1_proj or not p2_proj: continue
             
             x1, y1, s1 = p1_proj
             x2, y2, s2 = p2_proj
             
             # 水平線付近のY座標を制限（投影ジャンプ防止）
             y1 = max(y1, HORIZON_Y + 10)
             y2 = max(y2, HORIZON_Y + 10)
             
             # Culling: If segment is completely below next segment (occlusion)?
             # Hill handling: we draw Painter's algo (back to front), so it should cover correctly 
             # provided screen_y handles Up correctly.
             # Wait, if p_near Y < p_far Y (uphill), y1 < y2 on screen?
             # Y increases downwards on screen.
             # Uphill: world_y increases.
             # y1 = H - (yy1 - cam) * s1.
             # y2 = H - (yy2 - cam) * s2.
             # if yy2 > yy1 (uphill), y2 might be higher (smaller) than y1.
             # Painter's algo works fine for solid polygons.
             
             # Height check for optimization? (Skip if y2 > y1 and below horizon? No, hills can block horizon).
             # Stick to Painter's.
             
             # Fog Calculation
             # Linear fog: (constant * z / max_dist)
             # Let's make it start fading at 1/2 draw distance
             fog_pct = z_near / DRAW_DISTANCE
             # Increase density coverage (1.5x from previous 1.5 => 2.25)
             fog_pct = fog_pct * fog_pct * 2.25
             
             # [TEST] 水平線近くの道路を背景に馴染ませる（非線形グラデーション）
             # Y座標に基づく追加フェード（最遠方で強くブレンド）
             # Hills can make horizon varied. 
             # Fixed horizon logic (y2 < HORIZON_Y + 120) might need adj. 
             # But screen Y is what matters for visual blending.
             
             if y2 < HORIZON_Y + 120:  # 水平線から120px以内で処理
                 # 非線形グラデーション（三乗カーブでさらに急激にフェード）
                 horizon_dist = (y2 - HORIZON_Y) / 120.0  # 0（水平線）～1（120px下）
                 horizon_dist = max(0.0, min(1.0, horizon_dist))
                 horizon_fade = 1.0 - (horizon_dist * horizon_dist * horizon_dist)  # 三乗で非線形
                 
                 # [TEST] 道路色自体をフォグ色に強くブレンド
                 # horizon_fade: 0（遠方）→ 1（水平線上）
                 extra_fog = horizon_fade * 1.0  # 最大100%フォグ（完全に背景色）
                 fog_pct = min(1.0, fog_pct + extra_fog)
                 
             # Use specific road fog color if defined, else global fog color
             target_fog = cfg.get('road_fog_color', fog_color)
             poly_color = Track.interpolate_color(seg['color'], target_fog, fog_pct)

             # Draw Poly
             w1 = ROAD_WORLD_WIDTH * s1
             w2 = ROAD_WORLD_WIDTH * s2
             
             # ===== Road Edge Roughness (でこぼこ) =====
             # Segment index seeded pseudo-random for natural randomness (no flicker)
             if EDGE_ROUGHNESS_ENABLED:
                 seg_idx = seg['index']
                 # Create seeded random generator for this segment
                 rnd1 = random.Random(seg_idx * 12345)  # Near edge seed
                 rnd2 = random.Random((seg_idx + 1) * 12345)  # Far edge seed
                 
                 # Generate random jitter (-1 to 1) * amount * scale
                 jitter_left_1 = (rnd1.random() - 0.5) * 2 * EDGE_ROUGHNESS_AMOUNT * s1
                 jitter_right_1 = (rnd1.random() - 0.5) * 2 * EDGE_ROUGHNESS_AMOUNT * s1
                 jitter_left_2 = (rnd2.random() - 0.5) * 2 * EDGE_ROUGHNESS_AMOUNT * s2
                 jitter_right_2 = (rnd2.random() - 0.5) * 2 * EDGE_ROUGHNESS_AMOUNT * s2
             else:
                 jitter_left_1 = jitter_right_1 = jitter_left_2 = jitter_right_2 = 0
             
             poly = [
                 (x2 - w2/2 + jitter_left_2, y2), 
                 (x2 + w2/2 + jitter_right_2, y2), 
                 (x1 + w1/2 + jitter_right_1, y1), 
                 (x1 - w1/2 + jitter_left_1, y1)
             ]
             pygame.draw.polygon(screen, poly_color, poly)
             
             # ===== Stage 4 Sand Particles (砂粒子) =====
             # [TEST] この処理ブロック全体がステージ4砂粒子機能
             if cfg.get('sand_enabled', False) and y1 > y2:
                 sand_color = cfg.get('sand_color', (230, 200, 100))
                 # Use segment index for stable random placement
                 sand_rnd = random.Random(seg['index'] * 7777)
                 
                 # [TEST] クラスター配置ロジック（複数クラスター重複方式）
                 # 75%のセグメントにクラスター配置（増加）
                 if sand_rnd.random() < 0.75:
                     # 1-4個のクラスターを重ねて配置
                     num_clusters = sand_rnd.randint(1, 4)
                     
                     for _ in range(num_clusters):
                         # 各クラスター内の粒子数（5-15個）- 増加
                         num_particles = sand_rnd.randint(5, 15)
                         
                         # クラスター中心位置を毎回ランダムに決定
                         cluster_t = sand_rnd.random()
                         cluster_side = sand_rnd.choice(['left', 'right'])
                         # X軸の中心をランダムに（道路外にもはみ出す）
                         if cluster_side == 'left':
                             cluster_px_center = sand_rnd.uniform(-0.1, 0.2)
                         else:
                             cluster_px_center = sand_rnd.uniform(0.8, 1.1)
                         
                         for _ in range(num_particles):
                             # クラスター中心からの散らばり（広め）
                             t = cluster_t + sand_rnd.gauss(0, 0.5)
                             t = max(0.0, min(1.0, t))
                             
                             # X軸の散らばり（中心から広がる）
                             px = cluster_px_center + sand_rnd.gauss(0, 0.15)
                             
                             # Interpolate position
                             sand_x = x2 + (x1 - x2) * t
                             sand_w = w2 + (w1 - w2) * t
                             sand_x += (px - 0.5) * sand_w
                             sand_y = y2 + (y1 - y2) * t
                             
                             # [TEST] 水平線近くの透明化グラデーション
                             # 粒子のY位置から距離係数を計算
                             sand_distance = 1.0 - (sand_y - HORIZON_Y) / (screen_height - HORIZON_Y)
                             sand_distance = max(0.0, min(1.0, sand_distance))
                             
                             # [TEST] 中間〜水平線（distance > 0.35）で道路範囲外の砂はスキップ
                             if sand_distance > 0.35 and (px < 0.0 or px > 1.0):
                                 continue
                             
                             # 遠方（distance > 0.85）は描画スキップ
                             if sand_distance > 0.85:
                                 continue
                             
                             # 中距離（0.6-0.85）は霧色により強くブレンド
                             if sand_distance > 0.6:
                                 fade_strength = (sand_distance - 0.6) / 0.25  # 0 to 1
                                 extra_fog = fog_pct + fade_strength * 0.5  # 追加のフォグ
                                 extra_fog = min(1.0, extra_fog)
                                 fogged_sand = Track.interpolate_color(sand_color, fog_color, extra_fog)
                             else:
                                 fogged_sand = Track.interpolate_color(sand_color, fog_color, fog_pct)
                             
                             # [TEST] 疑似AA処理
                             ix, iy = int(sand_x), int(sand_y)
                             
                             # 90% = 1 pixel, 10% = 2px circle（頻度を減らした）
                             if sand_rnd.random() < 0.9:
                                 screen.set_at((ix, iy), fogged_sand)
                                 # 疑似AA: 30%の確率で隣接ピクセル
                                 if sand_rnd.random() < 0.3:
                                     aa_color = Track.interpolate_color(poly_color, fogged_sand, 0.5)
                                     dx, dy = sand_rnd.choice([(1,0), (-1,0), (0,1), (0,-1)])
                                     screen.set_at((ix + dx, iy + dy), aa_color)
                             else:
                                 pygame.draw.circle(screen, fogged_sand, (ix, iy), 2)  # [TEST] 2px
             # ===== Road Edge Smoothing (遠方のみ弱い色補正) =====
             # GPT-5助言: Y座標が地平線に近いほど背景色にブレンド
             # ===== Road Edge Smoothing (遠方のみ弱い色補正) =====
             # GPT-5助言: Y座標が地平線に近いほど背景色にブレンド
             if EDGE_SMOOTHING_ENABLED and y1 > y2:
                 # Calculate distance factor (0 = near, 1 = far/horizon)
                 # HORIZON_Y = 300, typical screen bottom ~600
                 distance_factor = 1.0 - (y2 - HORIZON_Y) / (screen_height - HORIZON_Y)
                 distance_factor = max(0.0, min(1.0, distance_factor))
                 
                 # Only apply smoothing to distant segments (upper 40% of road)
                 if distance_factor > 0.6:
                     # Blend strength: 0.2〜0.4 based on distance (weak blend)
                     blend_strength = 0.2 + (distance_factor - 0.6) * 0.5  # 0.2 to 0.4
                     
                     # Edge color blends road color toward fog/background color
                     edge_color = Track.interpolate_color(poly_color, target_fog, blend_strength)
                     
                     # Edge coordinates
                     left_x1, left_y1 = x1 - w1/2, y1
                     left_x2, left_y2 = x2 - w2/2, y2
                     right_x1, right_y1 = x1 + w1/2, y1
                     right_x2, right_y2 = x2 + w2/2, y2
                     
                     # Draw anti-aliased edge lines
                     pygame.draw.aaline(screen, edge_color, 
                                       (left_x1, left_y1), (left_x2, left_y2))
                     pygame.draw.aaline(screen, edge_color, 
                                       (right_x1, right_y1), (right_x2, right_y2))
             # ===== Curb Drawing =====
             if curb_enabled:
                 curb_w1 = ROAD_WORLD_WIDTH * CURB_WIDTH_RATIO * s1
                 curb_w2 = ROAD_WORLD_WIDTH * CURB_WIDTH_RATIO * s2
                 
                 # Curb colors based on segment index (sync with road stripes)
                 base_curb_color = CURB_RED if (seg['index'] % 2 == 0) else CURB_WHITE
                 # Apply fog to curb color
                 curb_color = Track.interpolate_color(base_curb_color, target_fog, fog_pct)
                 # Border color with fog
                 border_color = Track.interpolate_color(CURB_BORDER_COLOR, target_fog, fog_pct)
                 
                 # Determine which sides to draw curbs
                 seg_z = seg['p1']['z']
                 curve_val = seg['curve']
                 
                 draw_left = False
                 draw_right = False
                 
                 if seg_z < CURB_START_ZONE:
                     # Start zone: both sides
                     draw_left = True
                     draw_right = True
                 else:
                     # After start zone: curve inside only (large curves only)
                     if curve_val > CURB_CURVE_THRESHOLD:  # Right curve -> right curb (inside)
                         draw_right = True
                     elif curve_val < -CURB_CURVE_THRESHOLD:  # Left curve -> left curb (inside)
                         draw_left = True
                     # Straight or gentle curve: no curbs
                 
                 # Draw LEFT curb
                 if draw_left and curb_w1 > 0.5 and curb_w2 >= 0:
                     left_curb = [
                         (x2 - w2/2 - curb_w2, y2),
                         (x2 - w2/2, y2),
                         (x1 - w1/2, y1),
                         (x1 - w1/2 - curb_w1, y1)
                     ]
                     pygame.draw.polygon(screen, curb_color, left_curb)
                     # Border (road side)
                     pygame.draw.line(screen, border_color, 
                                     (x1 - w1/2, y1), (x2 - w2/2, y2), 2)
                 
                 # Draw RIGHT curb
                 if draw_right and curb_w1 > 0.5 and curb_w2 >= 0:
                     right_curb = [
                         (x2 + w2/2, y2),
                         (x2 + w2/2 + curb_w2, y2),
                         (x1 + w1/2 + curb_w1, y1),
                         (x1 + w1/2, y1)
                     ]
                     pygame.draw.polygon(screen, curb_color, right_curb)
                     # Border (road side)
                     pygame.draw.line(screen, border_color,
                                     (x1 + w1/2, y1), (x2 + w2/2, y2), 2)
             
             # Goal Line
             if seg['p1']['z'] <= GOAL_DISTANCE < seg['p2']['z']:
                 offset_z = GOAL_DISTANCE - seg['p1']['z']
                 g_rel_z = z_near + offset_z
                 ratio_g = offset_z / STRIPE_LENGTH
                 g_rel_x = rel_x_near + (rel_x_far - rel_x_near) * ratio_g
                 # Goal Y Interp
                 g_world_y = y_world_near + (y_world_far - y_world_near) * ratio_g
                 g_rel_y = g_world_y - (player_y + CAMERA_HEIGHT)
                 
                 pg = self.project(g_rel_x, g_rel_y, g_rel_z, 0, screen_width, screen_height)
                 if pg:
                     gx, gy, gs = pg
                     gw = ROAD_WORLD_WIDTH * gs
                     gh = (STRIPE_LENGTH * 0.3) * gs
                     pygame.draw.rect(screen, (255, 255, 255), (gx - gw/2, gy - gh, gw, gh))
        
        # カーブ累積値を返す（背景の消失点オフセットに使用）
        return dx

    def get_bg_colors(self, stage_id):
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        # Check if sky/ground keys exist, otherwise map from schema
        # v3 schema had straight sky_color/grass_color
        # But this method used "sky" and "ground" in the weird duplicate at bottom.
        # Let's use the standard keys.
        return cfg.get('sky_color', (0,0,0)), cfg.get('grass_color', (0,0,0))
