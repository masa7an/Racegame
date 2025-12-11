# v23_stable
# 2025-12-11
import pygame
import sys
import os
from src.logger import log_info, log_phase

# Modules
from src.car import Car
from src.track import Track, STAGE_CONFIG, HORIZON_Y
from src.ui import UI, HUD_FONT_SIZE
from src.effects import Effects
from src.background import BackgroundManager
from src.sound import SoundManager

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Game States
STATE_PLAYING = 0
STATE_GOAL = 1
STATE_STAGE_CLEAR = 2
STATE_NEXT_STAGE_INIT = 3
STATE_GAME_CLEAR = 4
STATE_REPLAY = 5 # NEW: Replay Mode

import json

def save_ranking(new_score):
    """
    Saves the new score to ranking.json if it qualifies for top 5.
    Returns the sorted top 5 scores.
    """
    file_path = "ranking.json"
    scores = []
    
    # Read existing
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                scores = json.load(f)
        except Exception as e:
            print(f"Error reading ranking: {e}")

    # Add new and sort
    scores.append(new_score)
    scores.sort() # Ascending (Lower Time is Better)
    scores = scores[:5]
    
    # Write back
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(scores, f)
    except Exception as e:
        print(f"Error writing ranking: {e}")
        
    return scores


def main():
    # --- Initialization ---
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Race Game v23_stable")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, HUD_FONT_SIZE)

    # --- BGM Setup ---
    try:
        bgm_file = "asset/Experimental_Model_long.mp3" 
        pygame.mixer.music.load(bgm_file)
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)
        print(f"Playing BGM: {bgm_file}")
    except Exception as e:
        print(f"BGM Error: {e}")

    # --- Instances ---
    player_y = SCREEN_HEIGHT - 60
    car = Car(SCREEN_WIDTH, SCREEN_HEIGHT, player_y)
    
    track = Track()
    ui = UI(SCREEN_WIDTH, SCREEN_HEIGHT, font)
    effects = Effects(SCREEN_WIDTH, SCREEN_HEIGHT)
    bg_manager = BackgroundManager(SCREEN_WIDTH, SCREEN_HEIGHT)
    sound_manager = SoundManager()

    # State Variables
    current_state = STATE_PLAYING
    stage_id = 1
    state_timer = 0.0
    
    start_time = pygame.time.get_ticks()
    final_time = 0.0 # Time when goal reached
    goal_speed = 0.0 # Speed when crossing goal line
    smoothed_camera_y = 0.0  # カメラ高さのローパスフィルタ用変数
    smoothed_camera_y = 0.0  # カメラ高さのローパスフィルタ用変数
    smoothed_slope = 0.0  # 勾配のローパスフィルタ用変数（背景同期用）

    # Score Variables
    stage_times = {} 
    ranking_data = []
    total_time_result = 0.0
    
    # Replay Variables
    replay_data = [] 
    replay_index = 0
    replay_active = False
    
    # Initial Route Setup
    track.create_road(stage_id)
    bg_manager.set_stage(stage_id)
    
    # --- Controller Setup ---
    pygame.joystick.init()
    joystick = None
    if pygame.joystick.get_count() > 0:
        try:
            joystick = pygame.joystick.Joystick(0)
            # joystick.init()
            print(f"Controller detected: {joystick.get_name()}")
        except Exception as e:
            print(f"Controller Init Error: {e}")
    else:
        print("No controller detected.")
    
    log_phase("13_main_v4", {"mode": "modular_refactor"})

    try:
        running = True
        while running:
            dt = clock.tick(FPS)
            dt_sec = dt / 1000.0
            
            # --- Event Handling ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.KEYDOWN:
                    # Debug Keys
                    if event.key == pygame.K_F1:
                        # Warp near goal
                        if current_state == STATE_PLAYING and track.goal_distance > 1000:
                            car.z = track.goal_distance - 1000.0
                    elif event.key == pygame.K_F2:
                        current_state = STATE_NEXT_STAGE_INIT
                    elif event.key == pygame.K_F3:
                        stage_id = max(1, stage_id - 1)
                        stage_id -= 1 # Logic below handles +1, so decrement to re-init same or prev
                        current_state = STATE_NEXT_STAGE_INIT
                    elif event.key == pygame.K_0:
                        sound_manager.toggle_mute()
                    elif event.key == pygame.K_u:
                        bg_manager.adjust_ground_offset(1)
                    elif event.key == pygame.K_j:
                        bg_manager.adjust_ground_offset(-1)


            keys = pygame.key.get_pressed()

            # --- Update ---
            
            if current_state == STATE_NEXT_STAGE_INIT:
                stage_id += 1
                if stage_id > 5:
                    # All Cleared
                    current_state = STATE_GAME_CLEAR
                    total_time_result = sum(stage_times.values())
                    ranking_data = save_ranking(total_time_result)
                    print(f"[DEBUG] GAME CLEAR! Total Time: {total_time_result:.2f}, Saved Ranking: {ranking_data}")
                    
                    pygame.mixer.music.fadeout(1000)
                    sound_manager.silence() # Engine sound off
                else:
                    track.create_road(stage_id)
                    bg_manager.set_stage(stage_id)
                        
                    car.z = 0.0
                    car.x = 0.0
                    car.speed = 0.0
                    smoothed_camera_y = 0.0  # カメラ高さもリセット
                    smoothed_slope = 0.0  # 勾配もリセット
                    start_time = pygame.time.get_ticks()
                    current_state = STATE_PLAYING
            
            if current_state == STATE_PLAYING:
                # Update Car Logic
                car.update(keys, track, dt_sec, joystick, stage_id=stage_id)
                
                # Record Replay Data
                replay_data.append({
                    'x': car.x, 'z': car.z, 
                    'speed': car.speed, 'steering_input': car.steering_input,
                    # 'angle': car.angle, # REMOVED: Calculated in render loop, not stored in Car
                    'stage_id': stage_id,
                    'offroad_l': car.offroad_l, 'offroad_r': car.offroad_r,
                    'braking': car.braking,
                    'camera_y': smoothed_camera_y
                })
                
                # Sound Update
                sound_manager.update(car.speed, car.accel_pressed)
                
                # Update Background (Parallax)
                # Need curve value at player pos
                curve_val = track.get_curve_at(car.z)
                # Update Background (Parallax)
                # Need curve value at player pos
                curve_val = track.get_curve_at(car.z)
                # Pitch from slope
                # Slope 0.05 -> Pitch ?
                # Heuristic: 0.05 slope ~= 100px shift?
                slope = track.get_slope_at(car.z)
                pitch_val = slope * 800.0 # Adjust multiplier as needed
                
                bg_manager.update(dt_sec, curve_val, car.speed)
                
                # カメラ高さと勾配のローパスフィルタ（投影ジャンプ防止）
                target_camera_y = track.get_height_at(car.z)
                smoothed_camera_y += (target_camera_y - smoothed_camera_y) * 0.1
                
                # 勾配も同じフィルタで滑らかに（背景と道路の同期のため）
                target_slope = track.get_slope_at(car.z)
                smoothed_slope += (target_slope - smoothed_slope) * 0.1
                
                # 背景にカメラ高さを通知（消失点同期用）
                bg_manager.set_camera_y_offset(smoothed_camera_y)

                
                # Update Effects
                effects.update_particles(dt_sec)
                
                # Spawn Dust/Sand if Offroad
                # Independent Left/Right Logic
                import random
                
                # Determine Stage Type
                # is_stage4_sand = (stage_id == 4) # Direct check is safer
                
                # Sand Color for Stage 4 (Approximating road/ground color)
                # Changed to brighter color as per user request (was 210, 180, 140)
                # Using very bright sand/white to avoid darkening texture too much in BLEND_MULT
                sand_color_ref = (255, 245, 225) 
                # Check Track Config if possible or hardcode for now based on Stage 4 theme
                
                # Function to spawn
                def spawn_tire_effect(gx, gy, steering):
                    if stage_id == 4:
                        # Sand Dust - Frequency based on speed/slip?
                        # User: "Output amount = slip amount".
                        # Here simplistic: if offroad, full slip.
                        effects.add_sand_dust(gx, gy, slip_ratio=0.5, ground_color=sand_color_ref)
                    else:
                        # Normal Dust
                        effects.add_dust(gx, gy, steering)
                
                # Left Tire
                if car.offroad_l and car.speed > 10.0:
                     if random.random() < 0.3: 
                         # Add randomness to X (Tire Width)
                         spawn_x = car.rect.bottomleft[0] + 5 + random.uniform(-10, 10)
                         spawn_y = car.rect.bottomleft[1] - 25 
                         spawn_tire_effect(spawn_x, spawn_y, car.steering_input)

                # [Phase 22] Stage 4 Sand: Slip Dust (Acceleration Slip)
                if stage_id == 4 and car.accel_pressed and car.speed < 107.0: # < 220km/h
                    # "Slip State" -> Spawn dust
                    # Frequency check
                    # User Request: Half overall freq (0.05 -> 0.025)
                    prob = 0.025 
                    if car.speed < 73.0: # < 150km/h (~73 units)
                        # User Request: 1.5x at low speed (was 2x)
                        prob = 0.025 * 1.5 # = 0.0375
                    
                    if random.random() < prob:
                        # Spawn at rear tires (random left or right or both)
                        # Let's verify car rect positions
                        # Spawn near bottom
                        sx = car.rect.centerx + random.uniform(-40, 40)
                        sy = car.rect.bottom - 10
                        effects.add_sand_dust(sx, sy, slip_ratio=0.8, ground_color=sand_color_ref)
                
                # [Phase 22] Stage 4 Sand: Brake Dust
                # Spawn dust when braking on sand
                if stage_id == 4 and car.braking and car.speed > 10.0:
                    if random.random() < 0.3: # 30% chance per frame
                        # Front tires? or Rear?
                        # Usually 4 wheels lock/slide. Let's do front mostly for visual diff?
                        # Or Rear is safer. Let's do random position near all tires.
                        
                        # Generate 1 or 2 particles
                        for _ in range(random.randint(1, 2)):
                             # Random tire position
                             offset_x = random.choice([-1, 1]) * (car.rect.width * 0.38)
                             spawn_x = car.rect.centerx + offset_x + random.uniform(-10, 10)
                             spawn_y = car.rect.bottom - 15
                             effects.add_sand_dust(spawn_x, spawn_y, slip_ratio=0.6, ground_color=sand_color_ref)

                # Right Tire
                if car.offroad_r and car.speed > 10.0:
                     if random.random() < 0.3:
                         spawn_x = car.rect.bottomright[0] - 5 + random.uniform(-10, 10)
                         spawn_y = car.rect.bottomright[1] - 25 
                         spawn_tire_effect(spawn_x, spawn_y, car.steering_input)

                # Sparks (High Speed Cornering)
                # Condition: Speed > 150.0 (~310km/h) AND (Strong Curve OR Strong Steering)
                # Curve > 1.0 or Steering > 0.5
                if car.speed > 150.0:
                    should_spark = False
                    spark_x = 0
                    spark_flip = False # Default False (Left side?)
                    
                    # Logic: If turning RIGHT, Left side scrapes? (Weight transfer)
                    # For simplicity, let's spawn from "Lower Side" of the chassis (Outer side of turn)
                    # Turn Right (curve > 0) -> Left side (bottomleft) scrapes?
                    # Actually, if curve > 0, we are turning Right. Centrifugal force pushes car Left.
                    # Left suspension compresses. Skid plate on Left might scrape.
                    
                    # User req: Inner side.
                    # Right Curve -> Right side.
                    # Left Curve -> Left side.
                    
                    # Using Curve Value from Track
                    if curve_val > 1.5: # Sharp Right Curve
                        if random.random() < 0.03: 
                             should_spark = True
                             # User req: Inner side (Right), Outward 15px
                             spark_x = car.rect.bottomright[0] + 15
                             spark_flip = True # Right side -> Flip
                    elif curve_val < -1.5: # Sharp Left Curve
                        if random.random() < 0.03:
                             should_spark = True
                             # User req: Inner side (Left), Outward 15px
                             spark_x = car.rect.bottomleft[0] - 15
                             spark_flip = False # Left side -> Normal
                    
                    # Also check steering input for drift-like sparks
                    if not should_spark and abs(car.steering_input) > 0.7:
                         if random.random() < 0.02: 
                             should_spark = True
                             if car.steering_input > 0: # Steering Right
                                 # Right side
                                 spark_x = car.rect.bottomright[0] + 15
                                 spark_flip = True
                             else:
                                 # Left side
                                 spark_x = car.rect.bottomleft[0] - 15
                                 spark_flip = False
                    
                    if should_spark:
                         # User req: y-10px (Total -20 from bottom)
                         spark_y = car.rect.bottom - 20 
                         effects.add_spark(spark_x, spark_y, flip_x=spark_flip)
                
                # Goal Check (Use car front position for natural feel)
                # Add forward offset: approximately half of car's visual length in world space
                car_front_offset = 700.0  # 車の長さ + α
                if car.z + car_front_offset >= track.goal_distance:
                    current_state = STATE_GOAL
                    state_timer = 0.0
                    goal_speed = car.speed # Capture speed for display
                    car.speed = 0
                    # Reset offroad state to prevent persistent effects in replay
                    car.offroad_l = False
                    car.offroad_r = False
                    # Capture finish time
                    final_time = (pygame.time.get_ticks() - start_time) / 1000.0
                    stage_times[stage_id] = final_time
                    
            elif current_state == STATE_GOAL:
                state_timer += dt_sec
                if state_timer >= 1.5:
                    current_state = STATE_STAGE_CLEAR
                    state_timer = 0.0
                    
            elif current_state == STATE_STAGE_CLEAR:
                 state_timer += dt_sec
                 if state_timer >= 1.0:
                     current_state = STATE_NEXT_STAGE_INIT
            
            elif current_state == STATE_GAME_CLEAR:
                 # Handle Continue / Exit / Replay
                 keys = pygame.key.get_pressed()
                 
                 # "Continue" (Restart from Stage 1) -> Enter or Space or C or A button
                 continue_pressed = keys[pygame.K_RETURN] or keys[pygame.K_SPACE] or keys[pygame.K_c]
                 if joystick and joystick.get_button(0):  # A button
                     continue_pressed = True
                 
                 if continue_pressed:
                     # Restart Game
                     stage_id = 0 # Will incr to 1 in INIT
                     stage_times = {}
                     smoothed_camera_y = 0.0
                     smoothed_slope = 0.0
                     current_state = STATE_NEXT_STAGE_INIT
                     # Restart BGM and engine sound
                     pygame.mixer.music.play(-1)
                     sound_manager.update(0, False)  # Reset engine sound
                     continue # Skip rendering this frame (avoid stage_id=0 crash)
                     
                 # "Exit" -> Escape or E or B button
                 exit_pressed = keys[pygame.K_ESCAPE] or keys[pygame.K_e]
                 if joystick and joystick.get_button(1):  # B button
                     exit_pressed = True
                 
                 if exit_pressed:
                     running = False
                     
                 # "Replay" -> R or X button
                 replay_pressed = keys[pygame.K_r]
                 if joystick and joystick.get_button(2):  # X button
                     replay_pressed = True
                 
                 if replay_pressed:
                     current_state = STATE_REPLAY
                     replay_index = 0
                     replay_active = True
                     # [FIX 2025-12-11] Clear effects and reset car state at replay start
                     effects.clear_all()  # Clear any lingering particles
                     car.offroad_l = False
                     car.offroad_r = False
                     # [FIX 2025-12-11] Reset to Stage 1 track at replay start
                     if len(replay_data) > 0:
                         first_stage = replay_data[0].get('stage_id', 1)
                         stage_id = first_stage
                         track.create_road(stage_id)
                         bg_manager.set_stage(stage_id)
                     # Wait for key release ideally, but K_r transition is fine
                     
            elif current_state == STATE_REPLAY:
                 if replay_index < len(replay_data):
                     d = replay_data[replay_index]
                     car.x = d['x']
                     car.z = d['z']
                     car.speed = d['speed']
                     car.steering_input = d['steering_input']
                     # car.angle = d['angle'] # REMOVED
                     # [FIX 2025-12-11] Reset offroad flags only on first replay frame
                     # After first frame, restore from recorded data for realistic replay
                     if replay_index == 0:
                         car.offroad_l = False
                         car.offroad_r = False
                         car.offroad = False
                     else:
                         car.offroad_l = d['offroad_l']
                         car.offroad_r = d['offroad_r']
                         car.offroad = car.offroad_l or car.offroad_r
                     car.braking = d['braking']
                     
                     # [FIX 2025-12-11] Detect stage change during replay and recreate track
                     new_stage = d['stage_id']
                     if new_stage != stage_id:
                         stage_id = new_stage
                         track.create_road(stage_id)
                         bg_manager.set_stage(stage_id)
                     
                     # Restore Camera Y
                     # If recorded as 0 (bug or flat), recalculate fallback
                     rec_cam_y = d.get('camera_y', 0.0)
                     if rec_cam_y == 0.0 and stage_id in [2,3,5]: # Stages with hills
                         # Fallback to calculated height
                         rec_cam_y = track.get_height_at(car.z)
                     
                     smoothed_camera_y = rec_cam_y
                     
                     replay_index += 1
                 else:
                     current_state = STATE_GAME_CLEAR
                     
                 # Exit Replay (Brake)
                 if keys[pygame.K_DOWN] or keys[pygame.K_b] or (joystick and joystick.get_button(0)):
                     current_state = STATE_GAME_CLEAR

            # --- Rendering ---
            render_stage_id = stage_id
            if render_stage_id > 5: render_stage_id = 5
            
            # 1. Background
            # 1. Background
            # Use calculated pitch_val from Update loop? 
            # Or recalculate. Update logic is above.
            # Calculating here again for safety or storing in variable?
            # Let's use the one from Update.
            current_slope = track.get_slope_at(car.z)
            
            # [TUNING] Pitch Offset
            # フィルタ済みの勾配を使用（道路のカメラ高さと同期）
            pitch_offset = -smoothed_slope * 300.0 
            
            bg_manager.draw(screen, pitch_offset=pitch_offset)


            
            # 2. Track
            # Safer background fill
            bg_sky, bg_ground = track.get_bg_colors(render_stage_id)
            pygame.draw.rect(screen, bg_sky, (0, 0, SCREEN_WIDTH, HORIZON_Y))
            pygame.draw.rect(screen, bg_ground, (0, HORIZON_Y, SCREEN_WIDTH, SCREEN_HEIGHT - HORIZON_Y))
            
            # Re-draw BG over fill (BG manager handles transparency naturally)
            bg_manager.draw(screen, pitch_offset=pitch_offset)

            
            current_fog_color = bg_manager.get_fog_color(render_stage_id)
            accumulated_curve = track.draw(screen, car.z, car.x, SCREEN_WIDTH, SCREEN_HEIGHT, render_stage_id, current_fog_color, smoothed_camera_y)
            
            # カーブ累積値を背景に反映（地面テクスチャの消失点をカーブに連動させる）
            if accumulated_curve is not None:
                bg_manager.set_curve_offset(accumulated_curve)
            
            # [TEST] 道路描画後の霧オーバーレイ（水平線近くを馴染ませる）
            if current_fog_color:
                fog_overlay_height = 80  # 水平線から80px下まで
                fog_overlay = pygame.Surface((SCREEN_WIDTH, fog_overlay_height), pygame.SRCALPHA)
                for i in range(fog_overlay_height):
                    # 非線形グラデーション（三乗で上が濃く下が薄い）
                    t = i / float(fog_overlay_height)  # 0 (top) to 1 (bottom)
                    fade = (1.0 - t) ** 3  # 三乗で急激にフェード
                    alpha = int(fade * 200)  # 最大200（強め）
                    pygame.draw.line(fog_overlay, (*current_fog_color, alpha), 
                                   (0, i), (SCREEN_WIDTH, i))
                screen.blit(fog_overlay, (0, HORIZON_Y))
            
            # 3. Car
            total_time_sec = (pygame.time.get_ticks() - start_time) / 1000.0
            
            from src.car import NORMAL_MAX_SPEED
            
            sway_angle = effects.calculate_sway(
                car.steering_input, 
                car.speed, 
                NORMAL_MAX_SPEED, 
                total_time_sec,
                car.offroad
            )
            
            shake_x, shake_y = effects.calculate_shake_offset(
                car.speed,
                NORMAL_MAX_SPEED,
                total_time_sec,
                car.offroad
            )
            
            # Use road_dark color for tire shadow mask
            shadow_c = STAGE_CONFIG[render_stage_id].get('road_dark', (95, 95, 95))
            
            car.render(screen, angle=sway_angle, offset_x=shake_x, offset_y=shake_y, shadow_color=shadow_c)
            
            # [FIX] Render Dust/Sand ON TOP OF Car (User Request)
            effects.render_behind_car(screen)
            
            
            # Sparks (Render on top of car or just below HUD?)
            # Render relative to car so they look like they come from it
            effects.render_sparks(screen)
            # 4. HUD
            if current_state == STATE_GAME_CLEAR:
                ui.draw_game_clear(screen, total_time_result, ranking_data)
            elif current_state == STATE_REPLAY:
                ui.draw_replay_status(screen)
            else:
                if current_state == STATE_PLAYING:
                     elapsed_time = (pygame.time.get_ticks() - start_time) / 1000.0
                else:
                     # Show frozen time
                     elapsed_time = final_time

                rem_dist = max(0, int((track.goal_distance - car.z)/100))
                ui.draw_hud(screen, stage_id, elapsed_time, rem_dist)
                
            # Show active speed or frozen goal speed
            display_speed = car.speed
            is_speed_frozen = False
            if current_state in [STATE_GOAL, STATE_STAGE_CLEAR]:
                display_speed = goal_speed
                is_speed_frozen = True
            
            ui.draw_speedometer(screen, display_speed, is_frozen=is_speed_frozen)


            
            if current_state == STATE_GOAL:
                ui.draw_message(screen, "GOAL!!", (255, 0, 0))
            elif current_state == STATE_STAGE_CLEAR:
                 ui.draw_message(screen, f"STAGE {stage_id} CLEAR", (0, 255, 255), scale=3.0)
            elif current_state == STATE_GAME_CLEAR:
                 pass # UI drawn above

            pygame.display.flip()

    except Exception as e:
        import traceback
        with open("crash_log.txt", "w") as f:
            f.write(traceback.format_exc())
            print("CRASH DETECTED! Saved to crash_log.txt")
        raise e

    # Cleanup
    sound_manager.cleanup()
    log_info("Application Exit")
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
