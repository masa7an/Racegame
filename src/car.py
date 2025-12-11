import pygame
from .track import STRIPE_LENGTH, ROAD_WORLD_WIDTH

# Physics Constants
NORMAL_MAX_SPEED = 162.0     
OFFROAD_MAX_SPEED = NORMAL_MAX_SPEED * 0.2
ACCEL_RATE = 0.525             

DECEL_RATE = 1.25
GRAVITY_FACTOR = 0.8  # 勾配による重力加速度係数 (0.6 -> 0.8: +20% adjustment)
BRAKE_RATE = 1.2  # ブレーキ減速率 (1.0 -> 1.2: +20% improvement)
STEER_SENSITIVITY_LOW = 12.0  
STEER_SENSITIVITY_HIGH = 5.0  

PLAYER_WIDTH = 60
PLAYER_HEIGHT = 40

class Car:
    def __init__(self, screen_width, screen_height, player_y):
        self.x = 0.0
        self.z = 0.0
        self.speed = 0.0
        self.offroad = False
        self.screen_width = screen_width
        self.player_y = player_y
        self.braking = False  # ブレーキ状態フラグ
        self.accel_pressed = False # アクセル状態フラグ（炎用）
        
        # Load Image
        try:
            self.img = pygame.image.load("asset/car.png").convert_alpha()
            target_width = int(screen_width * 0.4)
            orig_w, orig_h = self.img.get_size()
            if orig_w > target_width:
                ratio = target_width / orig_w
                new_h = int(orig_h * ratio)
                self.img = pygame.transform.scale(self.img, (target_width, new_h))
            
            # Store original image for rotation
            self.original_img = self.img
            self.rect = self.img.get_rect(center=(screen_width // 2, int(screen_height * 0.82)))
            
            # Load Afterfire Texture
            try:
                self.fire_img = pygame.image.load("asset/afterfire.png").convert_alpha()
                # Pre-scale if too large? Assuming reasonable size or scale in render.
                # Let's ensure it's not huge.
                fw, fh = self.fire_img.get_size()
                target_fire_w = int(target_width * 0.3) # 30% of car width
                if fw > target_fire_w:
                    ratio = target_fire_w / fw
                    self.fire_img = pygame.transform.scale(self.fire_img, (target_fire_w, int(fh * ratio)))
            except FileNotFoundError:
                print("Warning: afterfire.png not found")
                self.fire_img = None

        except FileNotFoundError:
            self.img = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT))
            self.img.fill((255, 69, 0))
            self.original_img = self.img
            self.rect = self.img.get_rect(center=(screen_width // 2, player_y))
            self.fire_img = None
            
            self.fire_img = None
            
        # Slope Physics State
        self.dynamic_max_speed = NORMAL_MAX_SPEED
        self.max_speed_boost = 5.0 # Approx 10km/h (10 * 0.485)
            
    def update(self, keys, track, dt_sec, joystick=None, stage_id=1):
        # 1. Steering
        speed_ratio = self.speed / NORMAL_MAX_SPEED # Use base for steering sensitivity to keep feel consistent
        speed_ratio = max(0.0, min(1.0, speed_ratio))
        
        current_turn_speed = STEER_SENSITIVITY_LOW + (STEER_SENSITIVITY_HIGH - STEER_SENSITIVITY_LOW) * speed_ratio
        
        # [NEW] Wet Road Steering Reduction (Stage 5)
        # Wet surface reduces tire grip, making steering less responsive (Understeer)
        # User Request: Exclude if speed < 100km/h
        # 100km/h approx 48.5 units (150 units = 310km/h)
        if stage_id == 5 and self.speed >= 48.5:
             current_turn_speed *= 0.85 
        
        # Calculate steering input (-1.0 to 1.0) for visual tilt
        self.steering_input = 0.0
        
        # Keyboard Input
        if keys[pygame.K_LEFT]:
            self.steering_input = -1.0
        if keys[pygame.K_RIGHT]:
            self.steering_input = 1.0
        
        # Controller Input (Steering)
        if joystick:
            # 1. D-pad (Hat switch)
            if joystick.get_numhats() > 0:
                hat_x, _ = joystick.get_hat(0)
                if hat_x != 0:
                    self.steering_input = float(hat_x) # -1.0 or 1.0

            # 2. Analog Stick (Axis 0) - Overrides D-pad for precision
            axis_x = joystick.get_axis(0) 
            if abs(axis_x) > 0.1: # Deadzone
                self.steering_input = axis_x

        # Apply steering to position
        if abs(self.steering_input) > 0.01:
            self.x += self.steering_input * current_turn_speed

        # Combine if both pressed (though rare) in keyboard only case, 
        # but stick handles 0 naturally. 
        if keys[pygame.K_LEFT] and keys[pygame.K_RIGHT]:
            self.steering_input = 0.0

        # ... (Rest of Physics logic remains same)
        
        # 2. Centrifugal Force
        # Get curve from track based on current Z
        curve = track.get_curve_at(self.z)
        
        # [NEW] Wet Road Drift Increase (Stage 5)
        # Wet surface increases sliding outwards (Reduced grip against lateral G)
        drift_factor = 4.0
        if stage_id == 5:
            drift_factor = 5.5 # Increased from 4.0 (~1.4x)
        
        drift = curve * speed_ratio * drift_factor 
        self.x -= drift
        
        # 3. Offroad Logic
        safe_width_half = (ROAD_WORLD_WIDTH / 2.0) * 0.9 - 500.0
        
        # [NEW] Kerb Collision Logic (Widen safe area on kerbs)
        # Check if kerbs exist at current Z
        has_left_curb, has_right_curb = track.get_curb_at(self.z, stage_id=stage_id)
        
        # Define Kerb Safe Zone (matching rendering width roughly)
        # CURB_WIDTH_RATIO = 0.06 => ~200 units. 
        # Using 190.0 (User requested +10px extension total)
        kerb_safe_zone = 200.0 
        
        left_limit = -safe_width_half
        if has_left_curb:
            left_limit -= kerb_safe_zone # Widen left
            
        right_limit = safe_width_half
        if has_right_curb:
            right_limit += kerb_safe_zone # Widen right
        
        # Tire offset from center (based on actual car width, matching render logic)
        # Render uses: tire_ox = cw * 0.38 + 15, so we use similar calculation
        tire_offset = self.rect.width * 0.38 + 15.0
        
        self.offroad_l = (self.x - tire_offset) < left_limit
        self.offroad_r = (self.x + tire_offset) > right_limit
        self.offroad = self.offroad_l or self.offroad_r
        
        # --- Phase 20: Slope Physics & Dynamic Max Speed ---
        
        # 1. Get Slope
        current_slope = track.get_slope_at(self.z)
        
        # 2. Dynamic Max Speed Calculation
        # Under downhill (slope < 0), boost max speed
        target_max_base = NORMAL_MAX_SPEED
        if current_slope < -0.01: # Distinct downhill
            target_max_base += self.max_speed_boost
            
        # Smooth interpolation (0.3s approx)
        # Lerp factor: if dt is 0.016 (60fps), we want to bridge gap in ~0.3s (approx 20 frames)
        # Factor ~ 0.1 to 0.15
        lerp_factor = 5.0 * dt_sec # equivalent to 1/0.2 = 5.0? 
        # If dt=0.016, 5*0.016 = 0.08. 
        # Reach 90% in ~28 frames (0.5s). A bit slow. 
        # Let's try 8.0 * dt_sec.
        lerp_factor = 8.0 * dt_sec
        if lerp_factor > 1.0: lerp_factor = 1.0
        
        self.dynamic_max_speed += (target_max_base - self.dynamic_max_speed) * lerp_factor
        
        # 3. Gravity Application
        # slope > 0 (上り) -> 減速 (a -= slope * G)
        # slope < 0 (下り) -> 加速 (a += -slope * G)
        gravity_accel = -current_slope * GRAVITY_FACTOR * 10.0
        
        # [FIX 2025-12-11] Reduce gravity effect when braking to allow brakes to work on downhills
        # Check braking state early (before applying gravity)
        braking_active = keys[pygame.K_s] or keys[pygame.K_DOWN] or keys[pygame.K_b]
        if joystick and joystick.get_button(1):
            braking_active = True
            
        if braking_active:
            # Reduce gravity acceleration to 20% when braking
            gravity_accel *= 0.2
        
        self.speed += gravity_accel
        
        # Debug Log (Temp)
        # if abs(current_slope) > 0.001:
        #    print(f"Slope: {current_slope:.4f}, Gravity: {gravity_accel:.4f}, Speed: {self.speed:.2f}")

        # 4. Acceleration / Deceleration / Braking
        import random
        
        # Use dynamic max speed for limits
        current_limit = OFFROAD_MAX_SPEED if self.offroad else self.dynamic_max_speed
        
        self.accel_pressed = False
        self.braking = False
        
        # Check Brake Input (S or B or Down Arrow)
        if keys[pygame.K_s] or keys[pygame.K_DOWN] or keys[pygame.K_b]:
            self.braking = True

        # See if controller adds to input
        # Button 0 = A/Cross (Accel)
        # Button 1 = B/Circle (Brake)
        if joystick:
            if joystick.get_button(1): # Brake
                self.braking = True

        if self.braking:
            # Braking Logic (Adjusted)
            curr_brake = BRAKE_RATE
            
            # Reduce brake effectiveness at high speeds
            # Speed > 100.0 (Approx 200km/h) -> Reduce effectiveness
            if self.speed > 130.0: # Very High Speed
                curr_brake *= 0.4  # 2/5 effectiveness (improved from 0.2)
            elif self.speed > 80.0: # Moderate High Speed
                curr_brake *= 0.6
                
            # [Phase 22] Stage 4 Sand: Reduced Braking
            # User Request: Disable penalty when offroad (Only apply on Track)
            if stage_id == 4 and not self.offroad:
                curr_brake *= 0.5 # 50% braking power on sand track
                
            self.speed -= curr_brake
        elif (keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE] or (joystick and joystick.get_button(0))) and self.speed < current_limit:
             # Speed Ranges (Internal Units):
             # 310 km/h ~ 150.0 units
             # 280 km/h ~ 136.0 units
             
             self.accel_pressed = True  # Accelerating
             current_accel = ACCEL_RATE
             
             if self.speed > 150.0:
                 # High Speed Accel (>310km/h): Stifled to 1/10
                 current_accel *= 0.1 
             elif self.speed > 136.0:
                 # Medium Speed Accel (280-310km/h): Halved for smoothness
                 current_accel *= 0.5
                 
             # [Phase 22] Stage 4 Sand: Slippery Acceleration (Low-Mid Speed)
             # User Request: Reduce range to 220km/h (~107.0 units) from 250km/h
             if stage_id == 4 and self.speed < 107.0:
                 # Intermittent traction loss
                 import math
                 current_time = pygame.time.get_ticks() / 1000.0
                 
                 # User Request: Prevent 0 acceleration (Stall at 0km/h).
                 # Previous: 0.6 + 0.4*sin -> min 0.2.
                 # New: 0.7 + 0.3*sin -> min 0.4, max 1.0.
                 # Also ensures it's always positive enough to overcome friction.
                 
                 # [Phase 22 Update] Mitigate penalty on Uphills
                 # If slope > 0.02 (Steep Uphill), reduce slip effect to avoid stall.
                 # current_slope is available in scope (calculated above).
                 base_grip = 0.7
                 var_grip = 0.3
                 
                 if current_slope > 0.02:
                     # Uphill Mitigation: Weak slip (Almost full traction)
                     # Range: 0.85 ~ 1.0 (mean 0.925)
                     base_grip = 0.85
                     var_grip = 0.15
                     
                 grip = base_grip + var_grip * math.sin(current_time * 15.0) 
                 
                 current_accel *= grip
                 
             self.speed += current_accel
             
        elif self.speed > current_limit:
             # Fast deceleration when offroad or coasting above max
             decel = DECEL_RATE * 4.0 if self.offroad else DECEL_RATE
             self.speed -= decel
        
        # Natural coasting deceleration when no input (and not braking)
        if not self.accel_pressed and not self.braking and self.speed > 0:
            coast_decel = DECEL_RATE * 0.5 # Default Coast friction
            
            # [Phase 22] Stage 4 Sand Offroad: Increased Natural Decel (1.2x)
            if stage_id == 4 and self.offroad:
                coast_decel *= 1.2
                
            self.speed -= coast_decel
        
        if self.speed < 0: self.speed = 0
        
        # 5. Position Update
        self.z += self.speed

    def render(self, screen, angle=0.0, offset_x=0.0, offset_y=0.0, shadow_color=(95, 95, 95)):
        # Rotate image based on angle
        target_img = self.original_img
        target_rect = self.rect
        
        if abs(angle) > 0.1:
            # Positive Angle = CCW rotation
            target_img = pygame.transform.rotate(self.original_img, angle)
            target_rect = target_img.get_rect(center=self.rect.center)
            
        # Apply Offset
        final_rect = target_rect.move(offset_x, offset_y)
        
        screen.blit(target_img, final_rect)

        # --- [NEW] Tire Correction (Horizontal Black Boxes) ---
        # Draw AFTER car to cover tilted tires
        
        # Calculate mounting points relative to center (unrotated)
        # Assuming car width ~320px. Tires at ~ +/- 120px?
        # Height: near bottom.
        
        cw, ch = self.rect.width, self.rect.height
        tire_ox = cw * 0.38 + 15 # Outward +15px (13+2)
        tire_oy = ch * 0.35  # Near bottom
        
        import math
        rad = math.radians(angle) # angle deg -> rad (CCW)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        
        # Function to rotate point
        def rotate_point(ox, oy):
            # x' = x cos - y sin
            # y' = x sin + y cos
            rx = ox * cos_a - oy * sin_a  
            ry = ox * sin_a + oy * cos_a
            return rx, ry

        # Center of visible car (with shake offset)
        cx, cy = final_rect.center
        
        # Tire Dimensions
        tw_base = int(cw * 0.14) # ~45px (base width)
        # Extend tire width inward (toward car center) to accommodate thicker tires
        tw_extension = int(cw * 0.02)  # ~6px extension (2% of car width) toward center
        tw = tw_base + tw_extension  # Total tire width
        th = int(ch * 0.08) # Reduced height (0.15 -> 0.08)
        
        # Draw Left and Right Tires
        for side in [-1, 1]:
            # Original Offset
            ox = side * tire_ox
            oy = tire_oy 
            
            # Rotated Offset - Follow Rotation
            # ox is horizontal offset, oy is vertical offset (down)
            
            # Project using angle (Pygame Rotate CCW > 0)
            # x' = x cos - y sin (Standard 2D rotation CCW)
            # y' = x sin + y cos
            # But screen Y is flipped.
            # To get visual "lean into turn":
            # If turning left (Angle < 0, CW visual), Left side dips.
            # ox < 0. ry should be positive (increase Y).
            # -ox * sin(neg) -> pos * neg = neg. oy * cos(neg) -> pos.
            # -(-120)*sin(-30) + 100*cos(-30) = 120*(-0.5) + 86 = -60 + 86 = 26.
            # Ry became SMALLER? (moved Up).
            # Wait. Left side dips means Y increases.
            # My previous calculation said it worked.
            # Let's use the formula that worked for standard rect rotation:
            
            rx = ox * cos_a + oy * sin_a
            ry = -ox * sin_a + oy * cos_a
            
            # Screen Pos (Center of tire)
            # Scale vertical offset based on car height (original was 19px for ~190px height)
            vertical_offset = int(ch * 0.1)  # ~19px for original 190px height
            # Shift tire center inward (toward car center) to prevent outer edge overflow
            # Move center by half of extension amount toward center
            center_shift = tw_extension // 2
            tx = cx + rx - (side * center_shift)  # Left tire: shift right (+), Right tire: shift left (-)
            ty = cy + ry + vertical_offset 
            
            # Draw Rect (Centered at shifted tx, ty)
            tire_rect = pygame.Rect(0, 0, tw, th)
            tire_rect.center = (int(tx), int(ty))
            
            # Extend tire rectangle inward (toward car center) only
            # Left tire (side = -1): extend right (toward center, +x direction)
            # Right tire (side = 1): extend left (toward center, -x direction)
            if side == -1:  # Left tire
                # Keep left edge, extend right edge inward
                tire_rect.width += tw_extension
            else:  # Right tire
                # Keep right edge, extend left edge inward
                tire_rect.x -= tw_extension
                tire_rect.width += tw_extension
            

            
            # --- Tire Sinking Effect ---
            # Draw a road-colored patch to hide the part of the tire that dips below ground level.
            # Ground Level is defined by the resting position (angle=0).
            # Resting Y center = cy + oy + offset (scaled by car height)
            # Resting Bottom = Resting Y center + th/2.
            # Use the same vertical_offset calculated above for consistency
            ground_y = cy + oy + vertical_offset + th // 2
            
            # If the current tire bottom is below ground_y, mask it.
            current_bottom = tire_rect.bottom
            if current_bottom > ground_y:
                # Mask Rect: specific to this tire's X, starting at ground_y
                # Extend upward (scaled by car height, original was 2px)
                # Also scale by tire height to handle larger tires better
                base_mask_offset = max(1, int(ch * 0.01))  # ~2px for original height
                # Scale by tire height ratio (if tire is taller, need more mask coverage)
                tire_height_factor = max(1.0, th / 15.0)  # Original th was ~15px
                mask_upward_offset = int(base_mask_offset * tire_height_factor)
                
                # Adjust mask position: +3px downward to better cover larger tires when tilted
                mask_y = ground_y - mask_upward_offset + 3
                
                # Calculate mask height: ensure it covers tire bottom with extra margin
                # Add extra height based on tilt angle (larger angle = more coverage needed)
                import math
                angle_rad = abs(math.radians(angle))
                # When tilted, tire extends further down, so add extra height proportional to angle
                # sin(angle) gives vertical component of tilt
                tilt_extra_height = int(abs(math.sin(angle_rad)) * th * 0.5)  # Up to 50% of tire height
                
                # Base height: cover from mask_y to tire bottom, plus safety margin
                base_mask_height = current_bottom - mask_y + mask_upward_offset
                # Add extra height for tilt and ensure minimum coverage
                extra_margin = max(5, int(th * 0.2))  # At least 20% of tire height as margin
                mask_height = base_mask_height + tilt_extra_height + extra_margin
                mask_rect = pygame.Rect(tire_rect.left, mask_y, tire_rect.width, mask_height)
                
                # Extend inward (scaled by car width, original was 10px for ~320px width)
                mask_inward_extend = max(5, int(cw * 0.03125))  # ~10px for original 320px width
                if side == -1: # Left Tire -> Extend Right (Inward)
                    mask_rect.width += mask_inward_extend
                else: # Right Tire -> Extend Left (Inward)
                    mask_rect.x -= mask_inward_extend
                    mask_rect.width += mask_inward_extend
                    
                pygame.draw.rect(screen, shadow_color, mask_rect)

        # --- Visual Effects ---
        
        # 1. Brake Lights
        if self.braking:
            # Positions relative to car center
            # Use unrotated dimensions (self.rect) for stable offsets
            
            cx, cy = final_rect.center
            
            # Initial Offsets (relative to center)
            # Inner Lights
            # Originally: final_rect.width * 0.25 + 2.5. Using self.rect instead.
            ox_inner = self.rect.width * 0.25 + 2.5
            # Outer Lights
            ox_outer = self.rect.width * 0.38 - 6.0
            
            # Y Position (Relative to center)
            # Originally: cy + (final_rect.height * 0.15) - 20
            # oy should be positive (down)
            oy_light = (self.rect.height * 0.15) - 20
            
            # Glow Radius
            glow_radius = int(self.rect.width * 0.05)
            
            # Create Glow Surface
            glow_surf = pygame.Surface((glow_radius*2, glow_radius*2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 0, 0, 100), (glow_radius, glow_radius), glow_radius)
            pygame.draw.circle(glow_surf, (255, 100, 100, 150), (glow_radius, glow_radius), int(glow_radius*0.6))
            pygame.draw.circle(glow_surf, (255, 255, 255, 200), (glow_radius, glow_radius), int(glow_radius*0.3))
            
            # Rotation Setup
            import math
            # Pygame's rotation is CCW. In screen coordinates (Y down), 
            # visualizing a CCW rotation means standard math rotation logic applies if we treat Y as Up? 
            # No, standard math (x, y) -> (x', y') assumes Y up.
            # To match Pygame's visual rotation on screen (Y down), we need to invert the angle for the calculation
            # or invert the Y axis in the formula.
            # Testing showed previous logic rotated CW when car rotated CCW.
            # Fix: Negate angle for the math calculation to match screen space visual rotation.
            
            rad = math.radians(-angle) 
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            
            def get_rotated_pos(curr_ox, curr_oy):
                rx = curr_ox * cos_a - curr_oy * sin_a
                ry = curr_ox * sin_a + curr_oy * cos_a
                return cx + rx, cy + ry

            # Rotate the glow surface itself as well (Sync tilt)
            # Even though it is currently circular, this ensures partial transparency or future shapes align.
            if abs(angle) > 1.0:
                 rotated_glow = pygame.transform.rotate(glow_surf, angle)
            else:
                 rotated_glow = glow_surf
                 
            # Note: rotating a surface changes its size. calculate offset for blit center.
            rg_w, rg_h = rotated_glow.get_size()
            rg_ox = rg_w // 2
            rg_oy = rg_h // 2

            # Draw 4 lights
            # Left Inner (-x, +y)
            lx_in, ly_in = get_rotated_pos(-ox_inner, oy_light)
            screen.blit(rotated_glow, (lx_in - rg_ox, ly_in - rg_oy), special_flags=pygame.BLEND_ADD)
            
            # Right Inner (+x, +y)
            rx_in, ry_in = get_rotated_pos(ox_inner, oy_light)
            screen.blit(rotated_glow, (rx_in - rg_ox, ry_in - rg_oy), special_flags=pygame.BLEND_ADD)
            
            # Left Outer (-x, +y)
            lx_out, ly_out = get_rotated_pos(-ox_outer, oy_light)
            screen.blit(rotated_glow, (lx_out - rg_ox, ly_out - rg_oy), special_flags=pygame.BLEND_ADD)

            # Right Outer (+x, +y)
            rx_out, ry_out = get_rotated_pos(ox_outer, oy_light)
            screen.blit(rotated_glow, (rx_out - rg_ox, ry_out - rg_oy), special_flags=pygame.BLEND_ADD)

        # 2. Exhaust Fire (Afterfire)
        # Condition: Accelerating AND Low Speed (0-100km/h ranges)
        if self.accel_pressed and 1.0 < self.speed < 55.0:
            import random
            if random.random() < 0.4: # Slight increase in flicker freq
                # Load texture if not loaded (or handled in init, but let's check safety)
                if hasattr(self, 'fire_img') and self.fire_img:
                    # Scaling variation
                    scale = random.uniform(0.8, 1.2)
                    w = int(self.fire_img.get_width() * scale)
                    h = int(self.fire_img.get_height() * scale)
                    
                    # Resize
                    curr_fire = pygame.transform.scale(self.fire_img, (w, h))
                    
                    # Random Rotation (optional, maybe slight)
                    rot_angle = random.uniform(-10, 10)
                    curr_fire = pygame.transform.rotate(curr_fire, rot_angle)
                    
                    # Position
                    # Left Exhaust
                    fx_offset_x = final_rect.width * 0.28
                    fx_offset_y = final_rect.height * 0.35
                    
                    cx, cy = final_rect.center
                    fl_x = cx - fx_offset_x
                    fl_y = cy + fx_offset_y
                    
                    # Center the fire image on the exhaust point
                    fire_rect = curr_fire.get_rect(center=(int(fl_x), int(fl_y)))
                    
                    # Blend mode ADD for glowing effect
                    screen.blit(curr_fire, fire_rect, special_flags=pygame.BLEND_ADD)
