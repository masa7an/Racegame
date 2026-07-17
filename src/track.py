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

# Tunnel Settings (Stage6 単発ギミック — docs/tunnel_requirements.md 参照)
# 断面は半楕円（円柱を横に半分に割った形）。TUNNEL_HEIGHTとTUNNEL_HALF_WIDTHが
# 弧の縦横それぞれの半径にあたる（両者が等しければ真円の半分になる）。
TUNNEL_HEIGHT = 2400.0                             # 路面からアーチ頂点までの高さ（world units）
TUNNEL_HALF_WIDTH = ROAD_WORLD_WIDTH / 2 * 1.4     # 中心からアーチ両端（路面との接点）までの距離
TUNNEL_WALL_LIMIT = 1200.0                         # トンネル内で車が中心から離れられる上限（world units）。
                                                   # アーチの根元(TUNNEL_HALF_WIDTH=2371.6)ではなくここで止めるのは、
                                                   # カメラのxが車のxそのものなうえ、画面の視野がアーチ幅より広いため。
                                                   # 車体が根元に届くはるか手前からカメラが坑外を映してしまう。
                                                   # 中心からの距離と画面に占める空の割合の実測値(800x600):
                                                   #   800=0% / 1000=0% / 1200=0.1% / 1400=5.5% / 1600=20.8% / 1966=57.5%
                                                   # この値は解像度・アスペクト比に依存する(1280x720だと1200で4%)。
                                                   # 16:9へ変更するならdocs/tunnel_requirements.md 22-2の表を測り直すこと。
                                                   # 1000も空はほぼ0%だがオフロード判定の境界(約1025)より内側になり、
                                                   # トンネル内だけ路肩のスピードダウンが起きなくなるため採らない
TUNNEL_WALL_PUSHBACK = 20.0                        # 壁にめり込んだ車を1フレームあたり押し戻す最小量（world units）。
                                                   # 最大ステア量(STEER_SENSITIVITY_LOW=12)＋ドリフトを上回るので
                                                   # 壁に押し付けても外へは進めず、事実上の固い壁になる
TUNNEL_WALL_PUSHBACK_RATIO = 0.2                   # めり込み量に対する追加の押し戻し率。坑口の外は横に無制限なので、
                                                   # 大きく外へ逃げてから入口へ突っ込むと壁のはるか外側で坑内に入る。
                                                   # 固定量だけで戻すと壁に埋まったまま何十秒も走れてしまうため、
                                                   # 深いめり込みほど速く戻す。壁際では上のPUSHBACKが下限として効く
# 弧の分割数は固定せず、投影後の半径から必要な数を毎回求める（LOD）。詳細は _arc_segments_for()。
TUNNEL_ARC_TOLERANCE_PX = 0.8                      # 弦が真円から凹んでよい最大量（px）。小さいほど滑らかで重い
TUNNEL_ARC_SEGMENTS_MIN = 4                        # 最遠方でも最低これだけは分割する
TUNNEL_ARC_SEGMENTS_MAX = 24                       # 至近距離での分割数の上限（コスト頭打ち用）
                                                   # 接近時に必要なのは約21なので画質には効かず、
                                                   # 弧が画面外まで広がる至近距離のコストだけを抑える
TUNNEL_ARCH_COLOR = (60, 55, 57)                   # アーチ全体の色（単色、陰影なし）。ニュートラルグレー(55,53,57)
                                                   # からR/Gだけ加算してオレンジ寄りに（ライトの環境光の反射・
                                                   # 疑似グローを想定）。Bを削る方向（減算）だと赤黒く暗く
                                                   # 見えるため避け、明るさを保ったまま暖色を足す方向にした
TUNNEL_FLOOR_COLOR = (77, 72, 74)                  # 路肩の床色（コンクリート想定。道路端〜アーチ根元を埋める）。同上
TUNNEL_FOG_COLOR = (14, 14, 17)                    # トンネル奥の到達色（通常フォグの代わりに暗闇へフェード）
TUNNEL_SHADOW_SOFTEN = 7.5                         # 内部の明暗境界(手前=入口付近の明るさ/奥=暗闇)をぼかす倍率。
                                                   # fog_pct ** (1/この値) のべき乗カーブで、手前から緩やかに
                                                   # 暗くなり始めつつ奥は完全な暗闇(1.0)へ到達させる。
                                                   # 1.0=補正なし、大きいほど影が手前へ広がり境目が緩やかになる

# Tunnel Daylight Spill (坑口から差し込む外光)
# 坑口（入口・出口とも）に近いセグメントを明るくする。SHADOW_SOFTEN（カメラからの距離で
# 決まる）とは独立に、セグメントの「坑口からの奥行き」だけで決まるため、走って近づいても
# 明るさは動かない。奥行きに応じて線形に通常のトンネル暗化色へ戻る。
# 面ごとに当て方が違う:
#   床・路面 … 「トンネル外と同じフォグ計算をした色」とブレンドする。坑口（奥行き0）では
#              外の色に完全一致し、外の路面とシームレスに繋がる。
#   アーチ(屋根・横壁) … 外に対応物がないのでブレンド先がない。暗化を緩めてアーチ本来の色
#              (TUNNEL_ARCH_COLOR)へ近づけるだけ。床だけ明るいと不自然なため弱めに追従させる。
#   天井ライト … 光源であって外光を受ける面ではないので適用しない。
TUNNEL_DAYLIGHT_REACH = 4500.0                     # 坑口から外光が届く奥行き（world units。セグメント15本ぶん）
TUNNEL_DAYLIGHT_ARCH_RELIEF = 0.45                 # 坑口直近でのアーチの暗化緩和率。0=効果なし（床だけ明るい）、
                                                   # 1=坑口では全く暗くならずTUNNEL_ARCH_COLORそのもの

# Tunnel Entrance Portal (入口の厚み — 薄い板に見えないよう小口面を描く)
# 入口面に外枠アーチ（半径+厚み）と内枠アーチ（＝坑内の弧）の二重ポリゴンを取り、間を埋める。
TUNNEL_PORTAL_THICKNESS = 170.0                    # 小口の厚み（world units。ROAD_WORLD_WIDTH=約10m換算で約50cm）
TUNNEL_PORTAL_COLOR = (120, 118, 122)              # 小口面の色（外光に照らされたコンクリート想定）

# Tunnel Mountain (坑口の周りの山 — docs/tunnel_requirements.md 14節)
# 入口面に貼る平面シルエット1枚。アーチの根元は路面（＝山の裾と同じ平面）に接しているので、
# 開口部は「穴」ではなく下辺の切り欠きになり、外周の稜線→アーチ輪郭を逆順、と一筆でたどれる
# 単純多角形で描ける（pygameは穴あきポリゴンを描けないので、この性質に頼っている）。
MOUNTAIN_HALF_WIDTH = 40000.0     # 中心から裾までの距離（world units）。接近時に裾を画面へ入れない幅
MOUNTAIN_HEIGHT = 16000.0         # 稜線の最大高さ（路面から。接近時に画面上部を覆う）
MOUNTAIN_COLOR = (40, 92, 46)     # 山肌の色（背景の地面と馴染む暗めの緑、単色）
MOUNTAIN_SEED = 6                 # 稜線の形を固定する乱数シード（毎フレーム同じ形）
MOUNTAIN_DETAIL_LEVELS = 5        # 稜線の分割段数（midpoint displacement。2^N+1 点になる）
MOUNTAIN_ROUGHNESS = 0.35         # 稜線が包絡線から凹んでよい最大割合（0=なめらかな釣鐘、1=激しくギザギザ）
MOUNTAIN_AA_SUPERSAMPLE = 4       # 稜線のAA: 帯を縦何倍で描いて縮小するか（＝カバレッジの階調数。詳細は _blit_mountain_aa）
MOUNTAIN_RIDGE_FEATHER_PX = 1.75  # 稜線を縦方向へにじませる幅（px）。1でほぼAAのみ、大きいほど空へ溶ける
MOUNTAIN_FOREST_IMAGE = 'asset/forest.png'  # 山肌に貼る森テクスチャ（航空写真風、格子状に敷き詰める）
MOUNTAIN_FOREST_TILE_WORLD_W = 4500.0  # タイル1枚分の世界幅（world units）。s1倍してスクリーン上のタイル寸法にする
MOUNTAIN_FOREST_ALPHA_MAX = 170        # 至近距離でのテクスチャ最大不透明度（0-255）。低めにして地肌とブレンドさせる
MOUNTAIN_FOREST_ALPHA_GAMMA = 0.7      # (1-fog_pct)に掛ける指数。1未満だと遠距離の減衰が緩やかになり、より遠くまでうっすら見え続ける

# Tunnel Ceiling Lights (天井ライト — 装飾のみ、路面への影響なし)
# 左右2灯に分離。弧のファセット分割とは独立した角度で自由に配置・サイズ調整する。
TUNNEL_LIGHT_COLOR = (255, 130, 30)                # ライトの色（オレンジ寄りの暖色系）
TUNNEL_LIGHT_CENTER_OFFSET = math.radians(27.0)    # アーチ頂点(theta=90°)から左右ライト中心までの角度
TUNNEL_LIGHT_HALF_ANGLE = math.radians(2.8)        # 各ライトの半幅角度（小さめサイズ）
TUNNEL_LIGHT_SPACING = 4                           # ライトの周期（セグメント数）
TUNNEL_LIGHT_ON_LENGTH = 2                          # 周期のうち点灯させるセグメント数（密な配置）
# グロー（にじみ）: ライト本体だけを発光用Surfaceに描き、縮小→拡大で作った疑似ブラーを
# 加算合成で重ねる。(縮小率, 強さ) を縮小率の小さい順に並べる。縮小率が大きいレイヤーほど
# 広く弱いにじみになる。強さ1.0のレイヤーが重なる中心は白飛びし、光源の芯として見える。
TUNNEL_LIGHT_GLOW_LEVELS = (
    (4, 1.0),                                      # 芯に近いハロー
    (12, 0.7),                                     # 広く薄いにじみ
)
TUNNEL_LIGHT_GLOW_INTENSITY = 1.0                  # グロー全体の強さ倍率
TUNNEL_LIGHT_SHADOW_RELIEF = 0.25                  # ライト(本体・にじみ)だけ暗化を緩める割合。TUNNEL_SHADOW_SOFTEN後の
                                                   # 値をこのぶん減らして使う。0=壁と同じ暗さ、0.25なら25%明るく残る
TUNNEL_LIGHT_GLOW_SURF_DOWNSCALE = 2               # 発光用Surfaceの解像度分周率。にじみはどのみち縮小→拡大の
                                                   # ブラーを通すため低解像度で描いても見た目はほぼ変わらず、
                                                   # ライト・遮蔽(黒消し)の塗りコストが1/分周率^2になる。
                                                   # ブラー初段の縮小率(GLOW_LEVELSの先頭)より小さくすること

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
    6: {
        # Stage1の環境・コース特性を複製（トンネルギミック用ステージ）
        # stage_idが乱数シードのため、実際のコースレイアウトはStage1とは別物になる
        'sky_color': (100, 149, 237), 'grass_color': (34, 139, 34),
        'road_light': (105, 105, 105), 'road_dark': (95, 95, 95),
        'bg_image': 'asset/bg1.png', 'ground_image': 'asset/bg1v.png', 'bg_offset_y': -140,
        'curve_freq': 0.05, 'curve_amp': 30.0,
        'curve_mult': 0.8,
        'sharp_prob': 0.1, 's_curve_prob': 0.1,
        'curb_enabled': False,  # ステージ6は縁石なし（トンネルギミック優先）
        # トンネル区間（固定位置・固定長、複数区間）: docs/tunnel_requirements.md 3-1参照
        'tunnels': [
            {'start_z': 20000.0, 'length': 63000.0},
            {'start_z': 200000.0, 'length': 63000.0},
            {'start_z': 400000.0, 'length': 63000.0},
        ],
    },
}

class Track:
    def __init__(self):
        self.segments = []
        self.goal_distance = GOAL_DISTANCE
        self.goal_distance = GOAL_DISTANCE
        self.stripe_length = STRIPE_LENGTH
        self._tunnel_glow_surf = None   # 天井ライトの発光用Surface（ライト本体のみを描き、ブラーの入力にする）
        self._tunnel_glow_size = (0, 0)
        self._glow_scratch = {}         # ブラーの縮小/拡大に使うSurfaceのキャッシュ
        self._mountain_ridge = Track._build_mountain_ridge()  # 坑口の山の稜線（世界座標、形は毎フレーム同じ）
        self._mountain_forest_tex = pygame.image.load(MOUNTAIN_FOREST_IMAGE).convert_alpha()  # 山肌に敷き詰める森テクスチャ
        self._alpha_scratch = {}        # 山肌テクスチャのマスク・タイル描画に使うSurfaceのキャッシュ

    @staticmethod
    def _build_mountain_ridge():
        """坑口の山の稜線を世界座標の (x, y) 列で返す（左の裾 → 右の裾）。

        釣鐘状の包絡線に midpoint displacement のノイズを掛けて凹ませる。掛け算にしているので、
        裾（包絡線=0）は必ず地面へ戻り、高さも包絡線を超えない＝画面を覆う量を包絡線側だけで見積もれる。
        """
        rnd = random.Random(MOUNTAIN_SEED)
        noise = [rnd.random(), rnd.random()]
        amp = 1.0
        for _ in range(MOUNTAIN_DETAIL_LEVELS):
            refined = [noise[0]]
            for i in range(len(noise) - 1):
                mid = (noise[i] + noise[i + 1]) / 2 + rnd.uniform(-amp, amp)
                refined.append(max(0.0, min(1.0, mid)))
                refined.append(noise[i + 1])
            noise = refined
            amp *= 0.5   # 段を追うごとに揺れを半分にする（細部ほど小さい凹凸になる）

        ridge = []
        last = len(noise) - 1
        for i, v in enumerate(noise):
            t = i / last
            x = -MOUNTAIN_HALF_WIDTH + 2 * MOUNTAIN_HALF_WIDTH * t
            envelope = MOUNTAIN_HEIGHT * 0.5 * (1 - math.cos(2 * math.pi * t))
            ridge.append((x, envelope * (1.0 - MOUNTAIN_ROUGHNESS * v)))
        return ridge

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

    def get_accumulated_curve(self, player_z):
        """描画距離内に見えているセグメントの曲率の総和を返す（背景の消失点オフセット用）。

        draw() の描画ループが積む dx と同じ値。背景は道路より先に描くため、描画とは
        独立に求められるようにしてある（draw() の戻り値を使うと背景が1フレーム遅れる）。
        """
        if not self.segments:
            return 0.0
        start_idx = int(player_z / STRIPE_LENGTH)
        if start_idx >= len(self.segments):
            start_idx = len(self.segments) - 1
        num_visible = int(DRAW_DISTANCE / STRIPE_LENGTH)
        max_idx = min(len(self.segments) - 1, start_idx + num_visible)
        return sum(self.segments[i]['curve'] for i in range(start_idx, max_idx + 1))

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

    def get_tunnel_at(self, z, stage_id=1):
        """Returns True if the given z position is within any of the stage's tunnel sections."""
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        for t in cfg.get('tunnels', []):
            if t['start_z'] <= z < t['start_z'] + t['length']:
                return True
        return False

    @staticmethod
    def interpolate_color(c1, c2, t):
        t = max(0.0, min(1.0, t))
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return (r, g, b)

    @staticmethod
    def _arc_segments_for(radius_px):
        """投影後の半径に対し、弧を何分割すれば多角形に見えないかを返す。

        N分割の内接多角形は、弦の中央で真円より sagitta = R*(1-cos(pi/2N)) だけ内側に凹む。
        これが多角形に見える正体なので、凹みが TUNNEL_ARC_TOLERANCE_PX 以下になる最小のNを
        小角近似 sagitta ≈ R*(pi/2N)^2/2 から逆算する。

        注意: この値はフレームごとに1つだけ求めて全トンネルセグメントで共有すること。
        セグメントごとに分割数を変えてはいけない。手前のセグメントの弧（奥側の端）と
        奥のセグメントの弧（手前側の端）は同一平面・同一半径で接しているが、分割数が違うと
        内接多角形どうしが互いを包含せず（頂点数が違う内接多角形は入れ子にならない）、
        細かい側が粗い側の外へ僅かに張り出す。その隙間はどちらのポリゴンにも覆われず、
        継ぎ目に背景（空）が線状に覗く。
        """
        n = (math.pi / 2) * math.sqrt(max(radius_px, 0.0) / (2 * TUNNEL_ARC_TOLERANCE_PX))
        return max(TUNNEL_ARC_SEGMENTS_MIN, min(TUNNEL_ARC_SEGMENTS_MAX, math.ceil(n)))

    def _blit_mountain_aa(self, screen, mountain_poly, ridge_pts, color, screen_width, screen_height):
        """稜線が画面に写っている帯だけを縦MOUNTAIN_AA_SUPERSAMPLE倍で描いてから縮小し、
        空との境の階段を消す（真のカバレッジAA）。あわせて縦方向にだけにじませる。
        適用したらTrueを返す。

        pygame.draw.aaline は使えない。あれは「線」であってエッジのカバレッジAAではないため、
        (1)塗りつぶしが1pxの帯を食って中間色が一切残らず、(2)線を1px下げても得られるのは
        ほぼ塗り色そのままの1px線で、ほぼ水平な稜線（1px上がるまでの横の走りが長い＝階段が
        最も目立つ所）には効かない。縮小によるカバレッジ計算なら列ごとに連続的な中間色が出る。

        帯は画面のx範囲に掛かる稜線からだけ求める。接近時は稜線が画面の外（上）へ抜けて帯が
        空になり、AAは自動的にスキップされる。＝山が画面を覆う一番重いフレームではコストゼロで、
        稜線が見えている軽いフレームでだけ払う。
        """
        top = bot = None
        for (ax, ay), (bx, by) in zip(ridge_pts, ridge_pts[1:]):
            if max(ax, bx) < 0 or min(ax, bx) > screen_width or ax == bx:
                continue
            # 画面内に入る部分の端点でのyを取る（線分が画面をまたぐ場合は交点のy）
            for cx in (max(min(ax, bx), 0.0), min(max(ax, bx), float(screen_width))):
                cy = ay + (by - ay) * (cx - ax) / (bx - ax)
                top = cy if top is None else min(top, cy)
                bot = cy if bot is None else max(bot, cy)
        if top is None:
            return False

        # にじみ幅は小数も許す（1.5や1.75など、1pxより細かい調整用）。帯の余白（整数pxで確保する
        # 必要がある）は切り上げで、実際のぼかしの強さはfeatherの小数値そのままで効かせる。
        feather = max(1.0, float(MOUNTAIN_RIDGE_FEATHER_PX))
        margin = math.ceil(feather) + 1
        y0 = max(0, int(top) - margin)
        y1 = min(screen_height, int(bot) + margin + 1)
        if y1 <= y0:
            return False

        f = MOUNTAIN_AA_SUPERSAMPLE
        h = y1 - y0
        band = pygame.Surface((screen_width, h * f), pygame.SRCALPHA)
        # 透明部分もRGBは山の色で埋めておく。SRCALPHAの初期値(0,0,0,0)のまま縮小すると、
        # RGBとAが別々に平均されて縁のRGBが黒へ引っ張られ、にじみが黒く濁る。
        # RGBを一様にしておけばAだけが平均され、空との正しい線形補間になる。
        band.fill((*color, 0))
        pygame.draw.polygon(band, color, [(px, (py - y0) * f) for px, py in mountain_poly])

        # 縦だけにじませる: 縦をfeather分の1へ潰してから戻す（11節のグローと同じ縮小→拡大ブラー）。
        # 幅はWのまま触らないので、横方向は滲まず稜線の形は保たれる。
        # 潰す段が同時にカバレッジ平均も兼ねるため、AA用の縮小はこれ1回で済む。
        # round()で最終pxへ丸めることで、feather=1.5/1.75のような小数差もsmoothscaleの出力に反映される。
        squished_h = max(1, round(h / feather))
        blurred = pygame.transform.smoothscale(band, (screen_width, squished_h))
        screen.blit(pygame.transform.smoothscale(blurred, (screen_width, h)), (0, y0))
        return True

    def _get_alpha_scratch(self, key, size):
        # 山肌テクスチャのマスク・タイルに使う中間Surface（per-pixel alpha）を使い回す
        surf = self._alpha_scratch.get(key)
        if surf is None or surf.get_size() != size:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            self._alpha_scratch[key] = surf
        return surf

    def _blit_mountain_forest(self, screen, mountain_poly, fog_pct, screen_width, screen_height,
                               anchor_x, anchor_y, scale):
        """山肌に森テクスチャ（forest.png）を貼って質感を出す。mountain_polyと同じ輪郭で
        マスクするので、稜線やアーチの切り欠きをはみ出さない。

        タイルは坑口中心の投影点(anchor_x, anchor_y)を基準に敷き詰める。マスクの左上
        （＝bbox角）を基準にすると、接近でbboxが広がるたびに基準点自体が動き、模様が
        対角線状に流れて見えてしまう。坑口中心はスクリーン上でほぼ動かないので、
        ここを基準にすれば模様は中心から均等に育つだけになる。

        濃さはfog_pctで絞るが、1次関数だと近距離で不透明になりすぎ遠距離ではすぐ消えるため、
        ALPHA_MAXで頭打ちにしつつALPHA_GAMMA(<1)で遠距離の減衰を緩めている。
        """
        xs = [p[0] for p in mountain_poly]
        ys = [p[1] for p in mountain_poly]
        x0 = max(0, int(min(xs)))
        y0 = max(0, int(min(ys)))
        x1 = min(screen_width, int(max(xs)) + 1)
        y1 = min(screen_height, int(max(ys)) + 1)
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0:
            return

        fog_pct_clamped = max(0.0, min(1.0, fog_pct))
        overlay_alpha = int(MOUNTAIN_FOREST_ALPHA_MAX * (1.0 - fog_pct_clamped) ** MOUNTAIN_FOREST_ALPHA_GAMMA)
        if overlay_alpha <= 2:
            return

        local_poly = [(px - x0, py - y0) for px, py in mountain_poly]
        mask = self._get_alpha_scratch('mountain_forest', (w, h))
        mask.fill((0, 0, 0, 0))
        pygame.draw.polygon(mask, (255, 255, 255, 255), local_poly)

        tex = self._mountain_forest_tex
        # タイルの上限は画面幅まで（それより大きくしても、はみ出す分は敷き詰めループが
        # 別タイルでまかなうので見た目は変わらない。坑口に接近するとscaleが急激に増えるため、
        # 上限を設けないとsmoothscaleの対象が数千px四方まで膨らみ、そこだけ極端に重くなる）。
        tile_w = max(1, min(round(MOUNTAIN_FOREST_TILE_WORLD_W * scale), screen_width))
        tile_h = max(1, round(tile_w * tex.get_height() / tex.get_width()))
        tile = self._get_alpha_scratch('mountain_forest_tile', (tile_w, tile_h))
        pygame.transform.smoothscale(tex, (tile_w, tile_h), tile)

        # タイルの「中心」がanchor(=坑口中心の投影点)に来る格子を、マスクの左上手前から敷き詰める。
        # 剰余でanchorと同位相のままbbox内へ引き戻すので、-tile幅ぶん手前が最初の1枚になる。
        start_x = (anchor_x - x0 - tile_w / 2.0) % tile_w - tile_w
        start_y = (anchor_y - y0 - tile_h / 2.0) % tile_h - tile_h
        for ty in range(round(start_y), h, tile_h):
            for tx in range(round(start_x), w, tile_w):
                mask.blit(tile, (tx, ty), special_flags=pygame.BLEND_RGBA_MULT)

        mask.set_alpha(overlay_alpha)
        screen.blit(mask, (x0, y0))

    def _get_glow_scratch(self, key, size):
        # 縮小/拡大の中間Surfaceを使い回す（毎フレームの確保を避ける）
        surf = self._glow_scratch.get(key)
        if surf is None or surf.get_size() != size:
            surf = pygame.Surface(size)
            self._glow_scratch[key] = surf
        return surf

    def _blit_tunnel_glow(self, screen, glow_surf):
        # 発光用Surface（ライト本体のみ）を縮小→拡大した疑似ブラーとして加算合成する。
        # 縮小するとライトの色が周囲の黒と混ざり、拡大時の補間で連続的な減衰になる＝にじみ。
        # 各レイヤーは前段の縮小結果からさらに縮小するので、一気に縮小するより滑らかで安い。
        screen_size = screen.get_size()
        src = glow_surf
        for level_idx, (divisor, weight) in enumerate(TUNNEL_LIGHT_GLOW_LEVELS):
            small_size = (max(1, screen_size[0] // divisor), max(1, screen_size[1] // divisor))
            small = self._get_glow_scratch(('down', level_idx), small_size)
            pygame.transform.smoothscale(src, small_size, small)
            src = small

            layer = small
            w = max(0, min(255, int(255 * weight * TUNNEL_LIGHT_GLOW_INTENSITY)))
            if w < 255:
                # 強さの調整は乗算で行う（加算合成ではアルファ値が無視されるため）
                layer = self._get_glow_scratch(('fade', level_idx), small_size)
                layer.blit(small, (0, 0))
                layer.fill((w, w, w), special_flags=pygame.BLEND_MULT)

            up = self._get_glow_scratch('up', screen_size)
            pygame.transform.smoothscale(layer, screen_size, up)
            screen.blit(up, (0, 0), special_flags=pygame.BLEND_ADD)

    def draw(self, screen, player_z, player_x, screen_width, screen_height, stage_id=1, fog_color=None, camera_y=None):
        # Config (fallback for fog)
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        if fog_color is None:
            fog_color = cfg['sky_color']
            
        # Curb enabled check
        curb_enabled = cfg.get('curb_enabled', False)

        # Tunnel section ranges (Stage6 gimmick, may appear multiple times per stage)
        tunnel_ranges = [(t['start_z'], t['start_z'] + t['length']) for t in cfg.get('tunnels', [])]
        
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

            
        # トンネル天井ライトの発光用Surface（ライト本体だけを描き、後段でブラーをかけて加算合成する）
        # 黒でクリアするのは、加算合成では黒＝発光なしとして扱われるため（縮小時に黒と混ざって減衰する）
        # 弧の分割数はフレームに1つだけ決め、全トンネルセグメントで共有する（_arc_segments_for参照:
        # セグメントごとに変えると継ぎ目に空が覗く）。基準は最寄りのトンネル断面＝画面上で最も
        # 大きく写り、多角形が最も目立つ位置。トンネルが遠いフレームでは自動的に粗くなる。
        tunnel_arc_n = TUNNEL_ARC_SEGMENTS_MIN
        for t_start, t_end in tunnel_ranges:
            nearest_z = max(t_start, player_z + PROJECTION_PLANE_DIST)
            if nearest_z < t_end:
                nearest_scale = PROJECTION_PLANE_DIST / (nearest_z - player_z)
                tunnel_arc_n = max(tunnel_arc_n, Track._arc_segments_for(
                    max(TUNNEL_HALF_WIDTH, TUNNEL_HEIGHT) * nearest_scale))

        tunnel_glow_surf = None
        # 発光用Surfaceは低解像度で持つ（座標を glow_scale 倍して描く）。理由は定数の定義部を参照
        glow_scale = 1.0 / TUNNEL_LIGHT_GLOW_SURF_DOWNSCALE
        if tunnel_ranges:
            glow_size = (max(1, screen_width // TUNNEL_LIGHT_GLOW_SURF_DOWNSCALE),
                         max(1, screen_height // TUNNEL_LIGHT_GLOW_SURF_DOWNSCALE))
            if self._tunnel_glow_surf is None or self._tunnel_glow_size != glow_size:
                self._tunnel_glow_surf = pygame.Surface(glow_size)
                self._tunnel_glow_size = glow_size
            tunnel_glow_surf = self._tunnel_glow_surf
            tunnel_glow_surf.fill((0, 0, 0))

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
             # 山の森テクスチャ専用のフォグ値（水平線ブースト前の値を退避）。
             # 下の水平線ブーストは「道路が消失点に近いか」という画面上の見た目で決まるため、
             # 坑口からまだ遠い時点でもすぐ1.0に張り付いてしまい、テクスチャが実際の距離より
             # 早く消えてしまう（詳細は_blit_mountain_forest呼び出し側のコメント参照）。
             mountain_forest_fog_pct = fog_pct

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
                 
             # Tunnel section check (Stage6 gimmick) — 路面・縁石・壁のフォグ到達色を暗闇に切り替える
             # 複数区間ありうるため、このセグメントが属するトンネル区間を特定する
             cur_tunnel = None
             for t_start, t_end in tunnel_ranges:
                 if t_start <= seg['p1']['z'] < t_end:
                     cur_tunnel = (t_start, t_end)
                     break
             in_tunnel = cur_tunnel is not None

             # Use specific road fog color if defined, else global fog color
             if in_tunnel:
                 target_fog = TUNNEL_FOG_COLOR
                 # トンネル内部の明暗境界(手前の明るさ→奥の暗闇)をぼかし、影の遷移範囲を広げる。
                 # 除算(fog_pct/SOFTEN)だと奥の到達暗度ごと下がってしまう（水平線付近でも
                 # 1/2.5=0.4までしか暗くならず、グラデーションも0〜0.4に圧縮されて見えなくなる）。
                 # べき乗なら手前は緩やかに暗くなり始め、奥は必ず1.0（完全な暗闇）へ到達する。
                 tunnel_fog_pct = min(1.0, fog_pct) ** (1.0 / TUNNEL_SHADOW_SOFTEN)
                 # 外光: 坑口（入口・出口の近い方）からの奥行きで、床・路面を「外と同じ
                 # フォグ計算の色」とブレンドする。坑口では外の色に完全一致し、トンネル外の
                 # 路面とシームレスに繋がる。壁・アーチ・ライトには適用しない
                 # （tunnel_fog_pctのまま）。定数定義部を参照
                 portal_depth = min(seg['p1']['z'] - cur_tunnel[0], cur_tunnel[1] - seg['p1']['z'])
                 daylight = max(0.0, 1.0 - portal_depth / TUNNEL_DAYLIGHT_REACH)
             else:
                 target_fog = cfg.get('road_fog_color', fog_color)
                 tunnel_fog_pct = fog_pct
                 daylight = 0.0
             poly_color = Track.interpolate_color(seg['color'], target_fog, tunnel_fog_pct)
             if daylight > 0.0:
                 # 外の路面と全く同じ式（road_fog_color へ fog_pct でフェード）で照らされた色を作る
                 lit_road = Track.interpolate_color(
                     seg['color'], cfg.get('road_fog_color', fog_color), fog_pct)
                 poly_color = Track.interpolate_color(poly_color, lit_road, daylight)

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
             
             # ===== Tunnel Floor (路肩のコンクリート床 — Stage6 ギミック) =====
             # アーチの根元（±TUNNEL_HALF_WIDTH）まで床を敷き、道路端の外に見えていた
             # 背景の地面（草）を隠す。道路ポリゴンより先に描き、路面・縁石で中央を上書きさせる。
             if in_tunnel:
                 floor_color = Track.interpolate_color(TUNNEL_FLOOR_COLOR, TUNNEL_FOG_COLOR, tunnel_fog_pct)
                 if daylight > 0.0:
                     # 路面と同じく、外光の届く範囲は外と同じフォグ計算の色へ寄せる
                     lit_floor = Track.interpolate_color(
                         TUNNEL_FLOOR_COLOR, cfg.get('road_fog_color', fog_color), fog_pct)
                     floor_color = Track.interpolate_color(floor_color, lit_floor, daylight)
                 fw1 = TUNNEL_HALF_WIDTH * s1
                 fw2 = TUNNEL_HALF_WIDTH * s2
                 pygame.draw.polygon(screen, floor_color, [
                     (x2 - fw2, y2), (x2 + fw2, y2), (x1 + fw1, y1), (x1 - fw1, y1)])

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
                 curb_color = Track.interpolate_color(base_curb_color, target_fog, tunnel_fog_pct)
                 # Border color with fog
                 border_color = Track.interpolate_color(CURB_BORDER_COLOR, target_fog, tunnel_fog_pct)
                 
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

             # ===== Tunnel Section (半楕円アーチ — Stage6 単発ギミック) =====
             # 道路と同じ透視スケール(s1/s2)で、路面レベル(theta=0/pi)からアーチ頂点(theta=pi/2)
             # までを台形ポリゴンで近似し、円柱を割ったような弧を描く。分割数(tunnel_arc_n)は
             # トンネルへの近さからフレーム単位で決まる。
             # フォグは通常のfog_colorではなく暗闇(TUNNEL_FOG_COLOR)へフェードさせる。
             if in_tunnel:
                 # 坑口付近は外光で暗化を緩める（床・路面と違い外に対応物がないので
                 # ブレンド先はなく、アーチ本来の色へ近づけるだけ）。定数定義部を参照
                 arch_fog_pct = tunnel_fog_pct * (1.0 - daylight * TUNNEL_DAYLIGHT_ARCH_RELIEF)
                 arch_color = Track.interpolate_color(TUNNEL_ARCH_COLOR, TUNNEL_FOG_COLOR, arch_fog_pct)

                 def tunnel_arc_pt(theta, x, y, s, hw=TUNNEL_HALF_WIDTH, h=TUNNEL_HEIGHT):
                     return (x + hw * math.cos(theta) * s, y - h * math.sin(theta) * s)

                 arc_n = tunnel_arc_n

                 near_pts = []
                 far_pts = []
                 for k in range(arc_n + 1):
                     theta = math.pi * k / arc_n
                     near_pts.append(tunnel_arc_pt(theta, x1, y1, s1))
                     far_pts.append(tunnel_arc_pt(theta, x2, y2, s2))

                 # 最遠の可視断面を暗闇で塞ぐ。塞がないと筒が描画距離の果てで途切れ、
                 # そこから背景（空・地平線・草）が坑内の奥に透けて見える。トンネルは
                 # DRAW_DISTANCEより長いので、これは本物の出口ではなく描画の打ち切り面。
                 # 遠くから覗いたとき出口がすぐそこにあるように見える正体がこれ。
                 # far_pts は theta=0..pi の半楕円で、始点と終点が路面レベルで閉じるため
                 # そのまま塗れば断面全体になる。この位置は fog_pct=1.0 で壁自体が
                 # TUNNEL_FOG_COLOR に達しているので、蓋は壁と継ぎ目なく溶ける。
                 # 出口が描画距離の内側に入ったら塞がない（本物の出口の外光を見せる）。
                 if i == max_idx and cur_tunnel[1] > player_z + DRAW_DISTANCE:
                     pygame.draw.polygon(screen, TUNNEL_FOG_COLOR, far_pts)

                 for k in range(arc_n):
                     pygame.draw.polygon(screen, arch_color, [
                         near_pts[k], near_pts[k + 1], far_pts[k + 1], far_pts[k]])

                 # 発光用Surfaceにもアーチと同じ領域を黒で描き、このアーチ面より奥のライトの
                 # にじみを消す（黒＝発光なし）。にじみはループ後に一括加算するため、
                 # 画面へ描いたアーチでは隠れない。これがないとカーブで内側の壁の
                 # 向こうにあるライトのにじみが壁を透過し、坑内が透けて見える。
                 # このセグメント自身のライトはこの後に描くので消されない。
                 # ファセット単位ではなく帯全体を1ポリゴンで描く：低解像度の消し込みでは
                 # 塗り面積ではなく呼び出し回数がコストを支配するため（13-4の画面描画とは逆）。
                 if tunnel_glow_surf is not None:
                     pygame.draw.polygon(tunnel_glow_surf, (0, 0, 0),
                                         [(px * glow_scale, py * glow_scale) for px, py in near_pts]
                                         + [(px * glow_scale, py * glow_scale) for px, py in reversed(far_pts)])

                 # 天井ライト: 頂点(theta=pi/2)から左右に離した2灯を、弧の分割とは独立した角度で重ね描き
                 light_on = (seg['index'] % TUNNEL_LIGHT_SPACING) < TUNNEL_LIGHT_ON_LENGTH
                 if light_on:
                     # 光源なので壁ほど暗闇に沈まない。暗化をTUNNEL_LIGHT_SHADOW_RELIEFのぶん緩める
                     light_fog_pct = tunnel_fog_pct * (1.0 - TUNNEL_LIGHT_SHADOW_RELIEF)
                     light_color = Track.interpolate_color(TUNNEL_LIGHT_COLOR, TUNNEL_FOG_COLOR, light_fog_pct)
                     # 発光色は奥ほど黒へ落とす（黒＝発光なしなので、奥のライトのにじみが自然に弱まる）
                     glow_color = Track.interpolate_color(TUNNEL_LIGHT_COLOR, (0, 0, 0), light_fog_pct)
                     for side in (-1, 1):
                         center_theta = math.pi / 2 + side * TUNNEL_LIGHT_CENTER_OFFSET
                         t0 = center_theta - TUNNEL_LIGHT_HALF_ANGLE
                         t1 = center_theta + TUNNEL_LIGHT_HALF_ANGLE
                         quad = [
                             tunnel_arc_pt(t0, x1, y1, s1), tunnel_arc_pt(t1, x1, y1, s1),
                             tunnel_arc_pt(t1, x2, y2, s2), tunnel_arc_pt(t0, x2, y2, s2)]
                         pygame.draw.polygon(screen, light_color, quad)

                         # にじみは本体の形をぼかして作るので、発光用Surfaceへ描くのも本体と同じ形でよい
                         if tunnel_glow_surf is not None:
                             pygame.draw.polygon(tunnel_glow_surf, glow_color,
                                                 [(px * glow_scale, py * glow_scale) for px, py in quad])

                 # 入口セグメントにだけ、坑口の小口面（＝厚み）を描く。入口面上に外枠アーチ
                 # （半径 +THICKNESS）と内枠アーチ（＝坑内の弧と同じ半径）の二重ポリゴンを取り、
                 # 間をファセット単位の四角形で埋める。坑内の弧より外側なのでZファイティングはない。
                 # 奥行き方向へは延ばさない：内枠から奥は坑内の弧そのものが既に埋めているので
                 # 重ねると近距離でその面を舐めるように見て画面全体が小口色で覆われる。
                 # 小口面は坑外（外光側）なので、フォグは暗闇ではなく通常のfog_colorへ寄せる。
                 # 内枠は坑内の弧と同一平面・同一半径なので、分割数も弧と同じ arc_n を使う。
                 # ここだけ細かくすると内枠が弧より外へ張り出し、継ぎ目に空が覗く。
                 if (seg['p1']['z'] - STRIPE_LENGTH) < cur_tunnel[0]:
                     portal_color = Track.interpolate_color(TUNNEL_PORTAL_COLOR, fog_color, fog_pct)
                     out_hw = TUNNEL_HALF_WIDTH + TUNNEL_PORTAL_THICKNESS
                     out_h = TUNNEL_HEIGHT + TUNNEL_PORTAL_THICKNESS

                     # ===== 山（坑口の周りの地形 — 14節） =====
                     # 入口面上の1枚の多角形。左の裾→稜線→右の裾→右のアーチ根元→小口リングの外枠を
                     # たどって左のアーチ根元、と一筆で閉じる。切り欠きを坑内の弧ではなくリングの外枠
                     # (out_hw/out_h)に合わせるので、山とアーチの間に小口の帯が残り「山肌に開いた坑口」に見える。
                     # 分割数は弧と同じarc_nを共有する（13-2: ここだけ変えると継ぎ目に隙間が出る）。
                     # 坑外なのでフォグは暗闇ではなく通常のfog_colorへ寄せる（小口面と同じ扱い）。
                     # 坑内アーチ・ライトの後に描くので山が坑内を塞ぎ、この後のリングが開口部を縁取る。
                     mountain_color = Track.interpolate_color(MOUNTAIN_COLOR, fog_color, fog_pct)
                     ridge_pts = [(x1 + mx * s1, y1 - my * s1) for mx, my in self._mountain_ridge]
                     arc_pts = [tunnel_arc_pt(math.pi * k / arc_n, x1, y1, s1, out_hw, out_h)
                                for k in range(arc_n + 1)]
                     mountain_poly = ridge_pts + arc_pts

                     # ベースの塗り。稜線を下げて描くのは、塗りつぶしの硬い縁がにじみの中に
                     # 残ると、そこで色が不連続に切り替わってにじみが台無しになるため
                     # （塗りは内部で座標を丸めるので、真の稜線より上へはみ出すこともある）。
                     # にじみ幅より下げれば、硬い縁は帯の不透明な部分の下に隠れる。
                     fill_drop = MOUNTAIN_RIDGE_FEATHER_PX + 1
                     pygame.draw.polygon(screen, mountain_color,
                                         [(px, py + fill_drop) for px, py in ridge_pts] + arc_pts)

                     # 稜線と空の境の階段を消す（詳細と、pygameのaalineが使えない理由は _blit_mountain_aa）
                     self._blit_mountain_aa(screen, mountain_poly, ridge_pts, mountain_color,
                                            screen_width, screen_height)

                     # 山肌に森テクスチャを重ねて質感を出す（詳細は _blit_mountain_forest）。
                     # ベースの塗り・AAは見た目の水平線ブースト込みのfog_pctのまま（既存の見た目を変えない）。
                     # テクスチャだけは水平線ブースト抜きのmountain_forest_fog_pctを使い、
                     # もっと手前からうっすら見え始めて、実際の距離なりに緩やかに消えるようにする。
                     self._blit_mountain_forest(screen, mountain_poly, mountain_forest_fog_pct, screen_width, screen_height,
                                                 x1, y1, s1)

                     for k in range(arc_n):
                         t0 = math.pi * k / arc_n
                         t1 = math.pi * (k + 1) / arc_n
                         pygame.draw.polygon(screen, portal_color, [
                             tunnel_arc_pt(t0, x1, y1, s1, out_hw, out_h),
                             tunnel_arc_pt(t1, x1, y1, s1, out_hw, out_h),
                             tunnel_arc_pt(t1, x1, y1, s1),
                             tunnel_arc_pt(t0, x1, y1, s1)])

                     # 奥のライトのにじみを山・小口リングで遮る。にじみは発光用Surfaceへ
                     # 描きためてループ後に一括加算するため、画面へ描いた山では隠れない。
                     # 山と同じ形（切り欠きだけ坑内の弧＝開口部の内側）を黒で塗り、
                     # ここまでに描きためた奥のライトの発光を消す（黒＝発光なし）。
                     # これがないと、トンネルがカーブしてライトが開口部の外へ投影された
                     # とき、にじみが山を透過して坑内が透けたように見える。
                     if tunnel_glow_surf is not None:
                         inner_arc_pts = [tunnel_arc_pt(math.pi * k / arc_n, x1, y1, s1)
                                          for k in range(arc_n + 1)]
                         pygame.draw.polygon(tunnel_glow_surf, (0, 0, 0),
                                             [(px * glow_scale, py * glow_scale)
                                              for px, py in ridge_pts + inner_arc_pts])

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

        # トンネル天井ライトのにじみを、本体ポリゴンの上からまとめて重ねる
        if tunnel_glow_surf is not None:
            self._blit_tunnel_glow(screen, tunnel_glow_surf)

    def get_bg_colors(self, stage_id):
        cfg = STAGE_CONFIG.get(stage_id, STAGE_CONFIG[1])
        # Check if sky/ground keys exist, otherwise map from schema
        # v3 schema had straight sky_color/grass_color
        # But this method used "sky" and "ground" in the weird duplicate at bottom.
        # Let's use the standard keys.
        return cfg.get('sky_color', (0,0,0)), cfg.get('grass_color', (0,0,0))
