import pygame
import random

# HUD Constants
HUD_FONT_SIZE = 40

class UI:
    def __init__(self, screen_width, screen_height, font):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.font = font
        
        # Determine speed scale based on physics constants 
        # (Pass these in or define commonly? Safe to define here for now or pass in methods)
        self.speed_scale = 334.0 / 162.0 
        self.normal_max_speed = 162.0
        self.display_speed = 0.0 # for smoothing

    def draw_speedometer(self, screen, speed, is_frozen=False):
        """
        Draw digital speedometer (7-segment style)
        """
        # Smooth the display speed
        # Filter factor: 0.1 per frame (approx 0.3s to settle)
        self.display_speed += (speed - self.display_speed) * 0.08
        
        # Use smoothed value for display
        display_val = int(self.display_speed * self.speed_scale)
        
        # Fluctuation at max speed checks against RAW speed or Display?
        # Let's use raw speed for the "shaking" condition, but display_val for number
        if speed >= self.normal_max_speed * 0.99 and not is_frozen:
            display_val += random.randint(-1, 1) 
        
        # Determine color (White -> Yellow -> Red)
        # Thresholds: ~120km/h and ~150km/h
        val_for_color = abs(display_val)
        if val_for_color > 280: # 300km/h range
             color = (255, 0, 0)
             # Flicker at very high speed?
             if random.random() < 0.2: color = (255, 100, 100)
        elif val_for_color > 200:
             # Gradient from Yellow to Red? Or just Yellow?
             # Let's simple steps
             if val_for_color > 280:
                 color = (255, 0, 0)
             elif val_for_color > 240:
                 color = (255, 140, 0) # Orange
             else:
                 color = (255, 255, 0) # Yellow
        else:
            color = (255, 255, 255) # White
        
        # Position
        base_x = self.screen_width - 40
        base_y = self.screen_height - 30
        digit_size = 40  # height approx 80
        spacing = 47 # Increased spacing by +2px (45 -> 47) 
        
        # Draw Semi-transparent background box
        # Covers approx 3 digits and "km/h" label
        # Draw Semi-transparent background box
        # Covers approx 3 digits and "km/h" label
        # Reduced width to 185px as requested
        bg_width = 185
        bg_height = 110
        bg_right = self.screen_width - 10
        bg_bottom = self.screen_height - 10
        bg_rect = pygame.Rect(bg_right - bg_width, bg_bottom - bg_height, bg_width, bg_height)
        
        s = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
        s = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 100)) # More transparent (160 -> 100)
        screen.blit(s, bg_rect)

        # Draw "km/h" label
        label = self.font.render("km/h", True, (200, 200, 200)) # Simple font for label
        # Ideally smaller font, but using self.font is OK for now
        # Creating a smaller font on the fly is expensive, assume HUD_FONT_SIZE is ~40.
        # Maybe scale it down?
        label_scaled = pygame.transform.rotozoom(label, 0, 0.6)
        label_rect = label_scaled.get_rect(bottomright=(self.screen_width - 20, self.screen_height - 15))
        screen.blit(label_scaled, label_rect)

        # Draw digits from right to left
        str_val = str(display_val)
        cursor_x = label_rect.left - 10
        
        for char in reversed(str_val):
             try:
                 digit = int(char)
                 self._draw_digit(screen, cursor_x - spacing + 10, base_y - 80, digit_size, digit, color)
             except:
                 pass # ignore minus sign or decimal for now
             cursor_x -= spacing

    def _draw_digit(self, screen, x, y, size, digit, color):
        """
        Draws a 7-segment digit with glow.
        """
        # Configuration
        w = size
        h = size 
        thickness = size * 0.25
        gap = size * 0.1
        skew = -0.3
        
        # Segment definitions
        segments_map = {
            0: [1, 1, 1, 1, 1, 1, 0],
            1: [0, 1, 1, 0, 0, 0, 0],
            2: [1, 1, 0, 1, 1, 0, 1],
            3: [1, 1, 1, 1, 0, 0, 1],
            4: [0, 1, 1, 0, 0, 1, 1],
            5: [1, 0, 1, 1, 0, 1, 1],
            6: [1, 0, 1, 1, 1, 1, 1],
            7: [1, 1, 1, 0, 0, 0, 0],
            8: [1, 1, 1, 1, 1, 1, 1],
            9: [1, 1, 1, 1, 0, 1, 1]
        }
        
        # Helper to apply skew (offsets relative to x,y)
        def t(px, py):
            return (px + (py * skew) + 40, py) # Removed x,y addition to keep local coords
            
        # Define polygons in local coordinates (0,0 is top-left of digit)
        # We will draw to a temporary surface first for glow effect
        
        poly_a = [t(gap, 0), t(w-gap, 0), t(w-gap-thickness, thickness), t(gap+thickness, thickness)]
        poly_b = [t(w, gap), t(w, h-gap), t(w-thickness, h-gap-thickness/2), t(w-thickness, gap+thickness)]
        poly_c = [t(w, h+gap), t(w, 2*h-gap), t(w-thickness, 2*h-gap-thickness), t(w-thickness, h+gap+thickness/2)]
        poly_d = [t(w-gap, 2*h), t(gap, 2*h), t(gap+thickness, 2*h-thickness), t(w-gap-thickness, 2*h-thickness)]
        poly_e = [t(0, 2*h-gap), t(0, h+gap), t(thickness, h+gap+thickness/2), t(thickness, 2*h-gap-thickness)]
        poly_f = [t(0, h-gap), t(0, gap), t(thickness, gap+thickness), t(thickness, h-gap-thickness/2)]
        poly_g = [t(gap, h), t(gap+thickness, h-thickness/2), t(w-gap-thickness, h-thickness/2),
                  t(w-gap, h), t(w-gap-thickness, h+thickness/2), t(gap+thickness, h+thickness/2)]
        
        polys = [poly_a, poly_b, poly_c, poly_d, poly_e, poly_f, poly_g]
        active = segments_map.get(digit, [])
        
        # Surface size needs to cover the skewed digit
        # Width approx w + (2*h * absskew) + padding
        # Height approx 2*h + padding
        surf_w = int(w + 2*h * 0.5 + 60) 
        surf_h = int(2*h + 20)
        
        # 1. Create a surface for the digit
        digit_surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
        
        # Draw "Off" segments (Ghosting) on the main screen directly? 
        # Or on the digit surface? Let's draw on screen directly to save surface ops for active ones.
        # But we need to use global coords for screen.
        
        # Actually, let's just use the surface for EVERYTHING for simplicity of skew handling
        # Drawing ghost on digit_surf might be blurred too if we blur the whole thing.
        # User asked for "blurred copy overlap on the lit part".
        # So ghost shouldn't be blurred/glowing.
        
        # Draw Ghosting to SCREEN directly (using x,y)
        ghost_color = (30, 30, 30)
        for poly in polys:
             # Shift local poly to global x,y
             global_poly = [(p[0] + x, p[1] + y) for p in poly]
             pygame.draw.polygon(screen, ghost_color, global_poly)

        # Draw Active segments to digit_surf (White/Bright core for color tinted glow?)
        # User said "Overlap blurred copy on the lit part".
        # Strategy:
        # 1. Draw active segments on digit_surf with TARGET COLOR.
        # 2. Smoothscale down and up to create "glow_surf" (Blurred).
        # 3. Blit glow_surf to screen with ADD.
        # 4. Draw active segments on screen directly (Core).
        
        for i, is_on in enumerate(active):
            if is_on:
                pygame.draw.polygon(digit_surf, color, polys[i])
                
        # Create Glow
        # Scale down to 1/4 size then back up
        small_w, small_h = max(1, surf_w // 4), max(1, surf_h // 4)
        small_surf = pygame.transform.smoothscale(digit_surf, (small_w, small_h))
        glow_surf = pygame.transform.smoothscale(small_surf, (surf_w, surf_h))
        
        # Blit Glow (Additive)
        screen.blit(glow_surf, (x, y), special_flags=pygame.BLEND_ADD)
        
        # Extra Glow for RED color (High speed)
        # Check if color is red-ish (High R, Low G/B)
        if color[0] > 200 and color[1] < 150:
             # Create a secondary, wider blur (1/8 scale)
             tiny_w, tiny_h = max(1, surf_w // 8), max(1, surf_h // 8)
             tiny_surf = pygame.transform.smoothscale(digit_surf, (tiny_w, tiny_h))
             extra_glow_surf = pygame.transform.smoothscale(tiny_surf, (surf_w, surf_h))
             
             # Reduce intensity (Multiply by ~0.35)
             # "Toned down" further (128 -> 90)
             extra_glow_surf.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
             
             # Blit Extra Glow
             screen.blit(extra_glow_surf, (x, y), special_flags=pygame.BLEND_ADD)
        
        # Draw Core (Sharp)
        # Using a slightly lighter version of color for core? Or same color?
        # Let's use the same color for core to keep it simple and legible.
        for i, is_on in enumerate(active):
            if is_on:
                # Shift to global
                # Need to access polys[i]
                global_poly = [(p[0] + x, p[1] + y) for p in polys[i]]
                pygame.draw.polygon(screen, color, global_poly)

    def draw_hud(self, screen, stage_id, elapsed_time, rem_dist):
        # Stage (1.5x size, italic)
        # Create italic font for stage display
        italic_font = pygame.font.Font(None, HUD_FONT_SIZE)
        italic_font.set_italic(True)
        stage_s = italic_font.render(f"STAGE: {stage_id}", True, (255, 255, 0))
        stage_s_scaled = pygame.transform.rotozoom(stage_s, 0, 1.5)
        screen.blit(stage_s_scaled, (20, 20))

        # Time
        time_surface = self.font.render(f"TIME: {elapsed_time:.2f}", True, (255, 255, 255))
        screen.blit(time_surface, (20, 60))
        
        # Dist
        d_s = self.font.render(f"DIST: {rem_dist}m", True, (200, 200, 200))
        screen.blit(d_s, (20, 100))





    def draw_message(self, screen, text_str, color=(255, 0, 0), scale=1.0):
        t = self.font.render(text_str, True, color)
        if scale != 1.0:
            t = pygame.transform.rotozoom(t, 0, scale)
        tr = t.get_rect(center=(self.screen_width/2, self.screen_height/2))
        screen.blit(t, tr)

    def draw_game_clear(self, screen, total_time, ranking_data):
        # Overlay
        s = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 200)) # Dark overlay
        screen.blit(s, (0, 0))

        # "ALL STAGES CLEARED!" at the top
        top_msg = self.font.render("ALL STAGES CLEARED!", True, (255, 215, 0))
        top_rect = top_msg.get_rect(center=(self.screen_width/2, 60))
        screen.blit(top_msg, top_rect)

        # Title (Moved down slightly to accommodate top message)
        title = self.font.render("CONGRATULATIONS!", True, (255, 215, 0))
        title_rect = title.get_rect(center=(self.screen_width/2, 110))
        screen.blit(title, title_rect)
        
        # Total Time
        time_s = self.font.render(f"TOTAL TIME: {total_time:.2f}", True, (255, 255, 255))
        time_rect = time_s.get_rect(center=(self.screen_width/2, 170))
        screen.blit(time_s, time_rect)
        
        # Ranking Header
        rank_h = self.font.render("TOP 5 RECORDS", True, (200, 200, 255))
        rank_h_rect = rank_h.get_rect(center=(self.screen_width/2, 230))
        screen.blit(rank_h, rank_h_rect)
        
        # Ranking Entries
        start_y = 270
        ordinals = ["1st", "2nd", "3rd", "4th", "5th"]
        for i, score in enumerate(ranking_data):
            color = (255, 255, 255)
            # Highlight current score (simple float comparison)
            if abs(score - total_time) < 0.001: 
                color = (255, 255, 0) 
            
            rank_str = ordinals[i] if i < len(ordinals) else f"{i+1}th"
            entry = self.font.render(f"{rank_str} {score:.2f}", True, color)
            entry_rect = entry.get_rect(center=(self.screen_width/2, start_y + i * 40))
            screen.blit(entry, entry_rect)
            
        # Buttons/Instructions
        # Replay (Left)
        rep = self.font.render("[R] REPLAY", True, (100, 200, 255))
        rep_rect = rep.get_rect(center=(self.screen_width/2 - 150, 500))
        screen.blit(rep, rep_rect)
        
        # Exit (Right)
        ex = self.font.render("[ESC] EXIT", True, (255, 100, 100))
        ex_rect = ex.get_rect(center=(self.screen_width/2 + 130, 500))
        screen.blit(ex, ex_rect)
        
        # Continue (Bottom)
        cont = self.font.render("[ENTER] CONTINUE", True, (100, 255, 100))
        cont_rect = cont.get_rect(center=(self.screen_width/2, 550))
        screen.blit(cont, cont_rect)

    def draw_replay_status(self, screen):
        """
        Draws blinking REPLAY text indicator.
        """
        import time
        # Blink every 1 sec
        if int(time.time() * 2) % 2 == 0:
            color = (255, 0, 0)
        else:
            color = (255, 100, 100)
            
        # REPLAY text (2x size)
        msg = self.font.render("REPLAY", True, color)
        msg_scaled = pygame.transform.rotozoom(msg, 0, 2.0)
        rect = msg_scaled.get_rect(topright=(self.screen_width - 20, 20))
        screen.blit(msg_scaled, rect)
        
        # Exit instruction
        jp_guide = self.font.render("Press the brake key to exit", True, (255, 255, 0))
        jp_guide_s = pygame.transform.rotozoom(jp_guide, 0, 1.0)
        jp_rect = jp_guide_s.get_rect(topright=(self.screen_width - 20, 95))
        screen.blit(jp_guide_s, jp_rect)


