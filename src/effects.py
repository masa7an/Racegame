import pygame

class Effects:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # --- Advanced Particle System Setup ---
        self.max_particles = 30
        self.particles = [{'active': False} for _ in range(self.max_particles)]
        self.pool_index = 0
        
        # --- Sparks (High Speed Curve) ---
        self.max_sparks = 50
        self.sparks = [{'active': False} for _ in range(self.max_sparks)]
        self.spark_pool_index = 0
        try:
            self.spark_img = pygame.image.load("asset/spark.png").convert_alpha()
        except Exception as e:
            print(f"Failed to load spark.png: {e}")
            self.spark_img = None
            
        # Load Texture
        try:
            self.sand_sheet = pygame.image.load("asset/vfx_smoke_beige_sand.png").convert_alpha()
            # User provided single texture, no split.
            self.sand_textures = [self.sand_sheet]
        except Exception as e:
            print(f"Failed to load vfx_smoke_beige_sand.png: {e}")
            self.sand_textures = []
            
        # Load Generic Dust Texture
        try:
            self.dust_sheet = pygame.image.load("asset/vfx_dirt_kickup.png").convert_alpha()
            self.dust_textures = [self.dust_sheet]
        except Exception as e:
            print(f"Failed to load vfx_dirt_kickup.png: {e}")
            self.dust_textures = [] # Fallback to circle

    def add_spark(self, x, y, flip_x=False):
        """
        Spawn a spark particle at (x, y).
        """
        if not self.spark_img: return
        
        import random
        import math
        
        p = self.sparks[self.spark_pool_index]
        self.spark_pool_index = (self.spark_pool_index + 1) % self.max_sparks
        
        p['active'] = True
        p['x'] = x
        p['y'] = y
        p['flip_x'] = flip_x
        
        # 7. Short/Variable Life (0.05s - 0.2s)
        # assuming 60FPS. 0.05s = 3 frames. 0.2s = 12 frames.
        # life unit: 1.0 = 1 second (approx).
        duration = random.uniform(0.05, 0.25)
        p['life_max'] = duration
        p['life'] = duration
        
        # 6. Size Variations (Large, Medium, Small)
        # User req: Half of previous (approx 1/10). Previous 0.12-0.15 etc.
        # Check previous: Large 0.12-0.15. Medium 0.08-0.12. Small 0.04-0.08.
        # New target: Large 0.06-0.075. Medium 0.04-0.06. Small 0.02-0.04.
        size_type = random.random()
        if size_type < 0.2: # Large (20%)
            base_scale = random.uniform(0.06, 0.075)
        elif size_type < 0.6: # Medium (40%)
            base_scale = random.uniform(0.04, 0.06)
        else: # Small (40%)
            base_scale = random.uniform(0.02, 0.04)
            
        p['scale_base'] = base_scale
        p['scale'] = base_scale
        
        # 5. Random Direction Direction (-Y is Up)
        # User req: "Like an afterfire", "Do not move it".
        # So velocity should be 0.
        p['vx'] = 0.0
        p['vy'] = 0.0
        
    def add_dust(self, x, y, steering_input):
        """
        Legacy dust (now calling sand dust if type check passed? No, keep separate for other stages).
        Spawn a dust particle at (x, y) with flow based on steering.
        Recycles particles from the pool.
        """
        import random
        
        # Keep original logic for generic dust
        p = self.particles[self.pool_index]
        self.pool_index = (self.pool_index + 1) % self.max_particles
        
        # Reset Particle
        p['active'] = True
        p['type'] = 'dust'
        p['x'] = x
        p['y'] = y
        p['life'] = 1.0
        p['scale'] = random.uniform(0.5, 1.0) # Initial scale
        p['angle'] = random.uniform(0, 360)
        
        # Velocity Flow Logic
        # Flow opposite to steering (Wind effect)
        flow_force = -steering_input * 15.0 
        # Reduced dispersion to half (User Request: 2025-12-11)
        p['vx'] = flow_force + random.uniform(-1.0, 1.0)
        # Heavy Mud: Less floaty initial rise
        p['vy'] = random.uniform(-2.0, -4.5) 
        p['color'] = (100, 80, 50) # Mud color fallback
        
        # Select random texture
        if self.dust_textures:
            p['img'] = random.choice(self.dust_textures)
        else:
            p['img'] = None

    def add_sand_dust(self, x, y, slip_ratio, ground_color=(230, 210, 160)):
        """
        Spawn a SAND dust particle.
        slip_ratio: 0.0 to 1.0 (Controls count/size elsewhere, here just phys initial state)
        """
        import random
        
        # User Request: Reduce particle count for visibility
        # Skip generation randomly (only 30% chance to spawn)
        # Since particle size and duration increased, we need fewer particles.
        if random.random() > 0.3:
            return

        p = self.particles[self.pool_index]
        self.pool_index = (self.pool_index + 1) % self.max_particles
        
        
        p['active'] = True
        # print(f"[DEBUG] Spawning Sand Particle at {x}, {y}")
        p['type'] = 'sand'
        p['x'] = x
        p['y'] = y
        
        # Life: 0.2 - 0.6s
        # 1.0 life unit = 1 sec approx in main loop logic?
        # In update: life -= 1.5 * dt -> means 1.0 / 1.5 = 0.66s.
        # We need specific control.
        # User Request: Slower fade out -> Extend duration
        duration = random.uniform(0.8, 1.5) 
        p['life_max'] = duration
        p['life'] = duration
        
        # Physics
        # Random Angle (lateral spread)
        # Z-axis spread simulated by X spread
        spread = random.uniform(-15.0, 15.0) 
        p['vx'] = spread * 0.5 # Initial burst sideways
        
        # Movement
        # "Floating" -> Light sand/smoke
        # User: "Lighter gravity, more dispersion"
        p['vy'] = random.uniform(-3.0, -1.0) # Initial upward float
        
        # Size
        p['scale'] = random.uniform(0.5, 0.9) * (1.0 + slip_ratio) # Larger dust clouds
        p['angle'] = random.uniform(0, 360)
        
        # Color variation (Earth color)
        # Random RGB +/- 5-10%
        r, g, b = ground_color
        var = random.uniform(0.9, 1.1)
        p['color'] = (min(255, int(r * var)), min(255, int(g * var)), min(255, int(b * var)))
        
        if self.sand_textures:
            p['img'] = random.choice(self.sand_textures)
        else:
            p['img'] = None

    def update_particles(self, dt):
        """
        Update all active particles.
        """
        # Dust / Sand
        for p in self.particles:
            if not p['active']: continue
            
            p_type = p.get('type', 'dust')
            
            if p_type == 'dust':
                # Dirt Kickup Logic (Heavy Mud-like)
                # Apply Gravity
                gravity = 1.5 
                p['vy'] += gravity * dt * 60 * 0.1 # Gravity accelerates downward
                
                # Drag (Air Resistance) - Mud is heavy, loses speed faster
                p['vx'] *= 0.92
                p['vy'] *= 0.92
                
                # Move
                p['x'] += p['vx'] * dt * 60 
                p['y'] += p['vy'] * dt * 60
                
                # Animate
                # Decay faster (Mud clumps disappear/fall quickly)
                p['life'] -= 2.5 * dt 
                # Grow slower (Don't expand like smoke)
                p['scale'] += 0.5 * dt
                
            elif p_type == 'sand':
                # Sand Logic
                # 1. Physics
                # Drag (Air Resistance) -> Less drag for smoke/dust to travel further
                drag = 0.96 
                p['vx'] *= drag
                p['vy'] *= drag
                
                # Gravity (Light)
                gravity = 0.2 
                p['vy'] += gravity * dt * 60 * 0.05 # Very weak gravity
                
                # Wind (Random Lateral)
                import random
                if random.random() < 0.2: # More frequent wind fluctuation
                    wind = random.uniform(-0.8, 0.8) # Stronger wind
                    p['vx'] += wind
                
                # Update Pos
                p['x'] += p['vx'] * dt * 60
                p['y'] += p['vy'] * dt * 60
                
                # 2. Life & Alpha
                p['life'] -= dt 
                
            if p['life'] <= 0:
                p['active'] = False
                
        # Sparks
        for s in self.sparks:
            if not s['active']: continue
            
            s['x'] += s['vx'] * dt * 60
            s['y'] += s['vy'] * dt * 60
            
            # Gravity?
            s['vy'] += 1.0 * dt * 60 
            
            s['life'] -= dt # Decrease by time (seconds)
            
            # 2. Scale Animation (Grow start, Shrink end)
            progress = 1.0 - (s['life'] / s['life_max']) # 0.0 -> 1.0
            if progress < 0.2:
                # Grow
                s['scale'] = s['scale_base'] * (1.0 + progress * 2.0)
            else:
                # Shrink
                s['scale'] = s['scale_base'] * (1.4 - (progress - 0.2) * 1.0)
                if s['scale'] < 0: s['scale'] = 0
            
            if s['life'] <= 0:
                s['active'] = False

    def calculate_sway(self, steering_input, speed, normal_max_speed, time_sec, is_offroad):
        """
        Calculate visual roll angle.
        """
        import math
        import random
        
        # 1. Base Tilt (Steering)
        base_tilt = -steering_input * 2.5 
        
        # 2. Offroad Tilt
        offroad_tilt = 0.0
        if is_offroad:
            # Vibrating tilt +/- 1.0 degrees
            offroad_tilt = math.sin(time_sec * 50.0) * 1.0
            
        return base_tilt + offroad_tilt

    def calculate_shake_offset(self, speed, normal_max_speed, time_sec, is_offroad):
        """
        Calculate screen/car offset (shake).
        Returns: (offset_x, offset_y)
        """
        import random
        import math
        
        ox = 0.0
        oy = 0.0
        
        # 1. High Speed Vibration (Jitter)
        if speed > 50.0 and not is_offroad:
            ratio = min(1.0, (speed - 50.0) / 100.0)
            magnitude = 2.0 * ratio
            ox = random.uniform(-magnitude, magnitude)
            oy = random.uniform(-magnitude, magnitude)

        # 2. Offroad Shake (Vertical Bounce)
        if is_offroad:
            bounce = math.sin(time_sec * 60.0) * 5.0 
            oy += bounce
            ox += random.uniform(-2.0, 2.0)
            
        return ox, oy

    def render_behind_car(self, screen):
        """
        Render effects that appear behind the car (dust, smoke).
        """
        for p in self.particles:
            if not p['active']: continue
            # if not p['img']: continue  -> Allow None for fallback drawing 
            
            # Alpha Logic
            type_p = p.get('type', 'dust')
            
            if type_p == 'sand':
                # Custom Fade: 0 -> 0.7 -> 0
                # Life goes from max -> 0
                max_l = p.get('life_max', 0.5)
                life = p['life']
                if max_l <= 0: max_l = 0.01
                
                prog = 1.0 - (life / max_l) # 0.0 -> 1.0
                
                target_alpha = 0
                if prog < 0.2: # Fade In (Fast)
                    # 0 -> 0.7
                    t = prog / 0.2
                    target_alpha = int(255 * 0.7 * t)
                else: # Fade Out
                    # 0.7 -> 0
                    t = (prog - 0.2) / 0.8
                    target_alpha = int(255 * 0.7 * (1.0 - t))
                    
                alpha = max(0, min(255, target_alpha))
                
                # Rotate? 
                # p['angle'] += 1.0
                
            else:
                # Default Dust
                alpha = int(255 * p['life'])
                if alpha < 0: alpha = 0
            
            scaled_surf = None
            rect = None
            
            # Rendering with Texture
            if p['img']:
                # Scaling
                w = int(p['img'].get_width() * p['scale'])
                h = int(p['img'].get_height() * p['scale'])
                
                if w > 0 and h > 0:
                    scaled_surf = pygame.transform.scale(p['img'], (w, h))
                    
                    # Rotation
                    if type_p == 'sand':
                        scaled_surf = pygame.transform.rotate(scaled_surf, p['angle'])
                        
                    scaled_surf.set_alpha(alpha)
                    
                    # Position (Center)
                    rect = scaled_surf.get_rect(center=(int(p['x']), int(p['y'])))
                    
                    # Render
                    if scaled_surf:
                         screen.blit(scaled_surf, rect)
                 
            # Fallback for Generic Dust (No Image)
            if not p['img'] and type_p == 'dust':
                 # Draw simple gray circle
                 alpha = int(255 * p['life'])
                 s = pygame.Surface((10, 10), pygame.SRCALPHA)
                 pygame.draw.circle(s, (200, 200, 200, alpha), (5, 5), 4)
                 screen.blit(s, (int(p['x']), int(p['y'])))
            
    def render_sparks(self, screen):
        """
        Render sparks (on top of car usually, or behind? behind is safer).
        User said 'chassis bottom', effectively barely visible or surrounding bottom.
        Render AFTER car is probably better for visibility, or BEFORE if it comes from UNDER.
        Let's render here (Effect class is updated usually, but render call order depends on main).
        """
        if not self.spark_img: return
        
        import random
        
        for s in self.sparks:
            if not s['active']: continue
            
            # 4. Color Shift & 1. Alpha Jitter
            # Calc life progress
            progress = 1.0 - (s['life'] / s['life_max'])
            
            # Color: White -> Yellow -> Orange -> Red-ish
            # R: 255
            # G: 255 -> 200 -> 100 -> 0
            # B: 255 -> 0 -> 0 -> 0 
            r = 255
            if progress < 0.2:
                # White to Yellow
                g = 255
                b = int(255 * (1.0 - (progress/0.2)))
            elif progress < 0.6:
                # Yellow to Orange
                g = int(255 - 155 * ((progress-0.2)/0.4)) # 255 -> 100
                b = 0
            else:
                # Orange to Red
                g = int(100 * (1.0 - ((progress-0.6)/0.4))) # 100 -> 0
                b = 0
                
            color = (r, max(0, g), max(0, b))
            
            # Constant Alpha Jitter (0.6 - 1.0)
            alpha_jitter = random.uniform(0.6, 1.0)
            
            # Simple scaling
            w = int(self.spark_img.get_width() * s['scale'])
            h = int(self.spark_img.get_height() * s['scale'])
            
            # Ensure at least 1px visibility if alive but scaled down
            if w <= 0: w = 1
            if h <= 0: h = 1
            
            surf = pygame.transform.scale(self.spark_img, (w, h))
            
            # Flip if needed (Right side)
            if s.get('flip_x', False):
                surf = pygame.transform.flip(surf, True, False)
            
            # Tinting logic for Additive Blend:
            # If we just BLEND_ADD, white texture adds full color.
            # To tint, we multiply color first.
            surf.fill(color, special_flags=pygame.BLEND_MULT)
            
            # Apply Alpha
            # For ADD blending, alpha often modulates the intensity (black = invisible).
            # But surface alpha works too.
            surf.set_alpha(int(255 * alpha_jitter))
            
            dest_rect = surf.get_rect(center=(int(s['x']), int(s['y'])))
            
            # 3. Additive Blending
            screen.blit(surf, dest_rect, special_flags=pygame.BLEND_ADD)
            
    def render_overlay(self, screen):
        """
        Render effects that appear on top (speed lines, lens flare).
        """
        pass

    def get_camera_offset(self):
        """
        Return (x, y) offset for camera shake.
        """
        return 0, 0

    def clear_all(self):
        """
        Clear all active particles and sparks.
        Used when starting replay to prevent lingering effects.
        """
        for p in self.particles:
            p['active'] = False
        for s in self.sparks:
            s['active'] = False
