import pygame
import wave
import struct
import math
import os

class SoundManager:
    def __init__(self, start_run=False):
        # start_runフラグは、インスタンス生成時に即再生開始するかどうか（main.pyの都合に合わせる）
        
        # Initialize mixer if needed
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2)

        self.channels = {}
        self.sounds = {}
        
        # Path to engine.wav (Assumes it's in the same directory as this script)
        # However, main.py is running from project root often, or test/v18 depending on how it's executed.
        # Check current working directory to decide path
        base_path = os.path.dirname(os.path.abspath(__file__))
        wav_path = os.path.join(base_path, "asset", "engine.wav")
        
        if not os.path.exists(wav_path):
            print(f"Warning: {wav_path} not found. Engine sound will be disabled.")
            self.enabled = False
            return
        
        self.enabled = True
        
        # Load and verify WAV format
        try:
            raw_data, params = self._read_wav(wav_path)
            # params: (nchannels, sampwidth, framerate, nframes, comptype, compname)
            
            print("Layout Engine Sounds... (Processing bass boost)")
            
            # Apply Low-Pass Filter for Heavy Bass
            # オリジナルを少し太くする
            bass_data = self._apply_low_pass_filter(raw_data, params, window_size=5) 
            
            # Apply Echo Effect (Test)
            # 重低音データにエコーをかけて、響きを追加する
            # delay_ms=60ms, decay=0.4 (やや強めにかけて分かりやすくする)
            echo_data = self._apply_echo(bass_data, params, delay_ms=60, decay=0.4)

            # Low RPM (Idle-ish) - Lowered for more bass (0.7 -> 0.5)
            # Use echo data
            self.snd_low = self._create_pitch_shifted_sound(echo_data, params, 0.6)
            
            # Mid RPM - Lowered (1.1 -> 0.8)
            self.snd_mid = self._create_pitch_shifted_sound(echo_data, params, 0.9) 
            
            # High RPM - Lowered (1.6 -> 1.2)
            # Use echo data for high too for consistency
            self.snd_high = self._create_pitch_shifted_sound(echo_data, params, 1.3)
            
            # Assign Channels
            self.ch_low = pygame.mixer.Channel(1)
            self.ch_mid = pygame.mixer.Channel(2)
            self.ch_high = pygame.mixer.Channel(3)
            
            # Play all loops silently
            self.ch_low.play(self.snd_low, loops=-1)
            self.ch_mid.play(self.snd_mid, loops=-1)
            self.ch_high.play(self.snd_high, loops=-1)
            
            self.ch_low.set_volume(0)
            self.ch_mid.set_volume(0)
            self.ch_high.set_volume(0)

            self.is_muted = False

            
        except Exception as e:
            print(f"Error loading sound: {e}")
            import traceback
            traceback.print_exc()
            self.enabled = False

    def _read_wav(self, path):
        with wave.open(path, 'rb') as wf:
            params = wf.getparams()
            raw_data = wf.readframes(params.nframes)
            return raw_data, params

    def _apply_echo(self, raw_data, params, delay_ms=50, decay=0.5):
        """
        Simple Echo/Delay effect.
        Adds a delayed copy of the signal to itself.
        """
        nchannels = params.nchannels
        sampwidth = params.sampwidth
        framerate = params.framerate
        
        if sampwidth != 2:
            return raw_data

        # Calculate delay in frames
        delay_frames = int(framerate * (delay_ms / 1000.0))
        
        # Unpack
        num_frames = len(raw_data) // (sampwidth * nchannels)
        fmt = f"<{num_frames * nchannels}h"
        samples = list(struct.unpack(fmt, raw_data))
        
        new_samples = [0] * len(samples)
        
        # Apply echo
        # We process per channel implicitly because delay_frames is in 'frames' (stereo pairs)
        # But samples list is flat [L, R, L, R]. 
        # So delay index offset is delay_frames * nchannels
        
        delay_offset = delay_frames * nchannels
        
        for i in range(len(samples)):
            original = samples[i]
            
            # Get delayed sample
            delayed_idx = i - delay_offset
            if delayed_idx >= 0:
                delayed = samples[delayed_idx]
            else:
                delayed = 0
                
            # Mix
            mixed = original + int(delayed * decay)
            
            # Hard Clipping to avoid overflow noise
            mixed = max(-32767, min(32767, mixed))
            
            new_samples[i] = mixed
            
        # Repack
        new_raw_data = struct.pack(fmt, *new_samples)
        return new_raw_data

    def _apply_low_pass_filter(self, raw_data, params, window_size=3):
        """
        Simple Moving Average Filter to reduce high frequencies (Low-Pass).
        Makes the sound 'muffled' or 'bass-heavy'.
        window_size: Odd number recommend (3, 5, 7...). Higher = More muffled.
        """
        nchannels = params.nchannels
        sampwidth = params.sampwidth
        
        if sampwidth != 2:
            return raw_data # Only support 16-bit
            
        # Unpack
        num_frames = len(raw_data) // (sampwidth * nchannels)
        fmt = f"<{num_frames * nchannels}h"
        samples = list(struct.unpack(fmt, raw_data))
        
        new_samples = []
        
        # We need to filter per-channel
        half_window = window_size // 2
        
        # To avoid index out of bounds, we just skip edges or clamp
        # Doing this inefficiently for clarity and safety in Python
        
        total_len = len(samples)
        
        # Process per channel
        # Interleaved: [L, R, L, R, ...]
        for ch in range(nchannels):
            # Extract channel samples
            ch_samples = samples[ch::nchannels]
            filtered_ch = []
            
            len_ch = len(ch_samples)
            
            for i in range(len_ch):
                # Gather window
                start = max(0, i - half_window)
                end = min(len_ch, i + half_window + 1)
                
                # Average
                window = ch_samples[start:end]
                avg = sum(window) // len(window)
                filtered_ch.append(avg)
            
            # Store temporarily
            if ch == 0:
                ch0_data = filtered_ch
            else:
                ch1_data = filtered_ch
                
        # Interleave back
        if nchannels == 1:
            final_samples = ch0_data
        elif nchannels == 2:
            final_samples = []
            for i in range(len(ch0_data)):
                final_samples.append(ch0_data[i])
                final_samples.append(ch1_data[i])
        else:
            return raw_data # Todo: support >2 channels
            
        # Repack
        new_raw_data = struct.pack(f"<{len(final_samples)}h", *final_samples)
        return new_raw_data

    def _create_pitch_shifted_sound(self, raw_data, params, speed_factor):
        """
        Creates a pygame Sound object with shifted pitch.
        speed_factor > 1.0 -> Higher Pitch (Faster) -> Need to decimate samples
        speed_factor < 1.0 -> Lower Pitch (Slower) -> Need to repeat/interp samples
        
        Using simple nearest neighbor for speed (linear is better but slower in Python).
        """
        nchannels = params.nchannels
        sampwidth = params.sampwidth # Expected 2 (16-bit)
        
        # Support only 16-bit for now
        if sampwidth != 2:
            return None # Not supported
            
        # Convert raw bytes to integer list for easier processing
        # Using struct is faster than loop
        # Format for struct: 'h' * num_samples (h is short, 2 bytes)
        num_frames = len(raw_data) // (sampwidth * nchannels)
        fmt = f"<{num_frames * nchannels}h" # Little endian
        samples = struct.unpack(fmt, raw_data)
        
        # New target length
        new_num_frames = int(num_frames / speed_factor)
        
        new_samples = []
        
        # Resampling Loop
        # We need to pick 'new_num_frames' frames from original 'samples'
        # Step size in original array
        step = speed_factor
        
        for i in range(new_num_frames):
            orig_idx = int(i * step)
            if orig_idx >= num_frames:
                break
                
            # For each channel
            base_idx = orig_idx * nchannels
            for c in range(nchannels):
                val = samples[base_idx + c]
                new_samples.append(val)
                
        # Pack back to bytes
        new_fmt = f"<{len(new_samples)}h"
        new_raw_data = struct.pack(new_fmt, *new_samples)
        
        return pygame.mixer.Sound(buffer=new_raw_data)

    def update(self, speed, accel_pressed):
        if not self.enabled: return
        
        if self.is_muted:
            self.ch_low.set_volume(0)
            self.ch_mid.set_volume(0)
            self.ch_high.set_volume(0)
            return

        
        # Normalize Speed (Approx Max 300km/h = 160 internal)
        # Let's say max pitch is at 150.0
        ratio = speed / 150.0
        ratio = max(0.0, min(1.0, ratio))
        
        # Crossfade Logic
        # 0.0 - 0.3 : Low -> Mid
        # 0.3 - 0.7 : Mid
        # 0.7 - 1.0 : Mid -> High
        
        v_low = 0.0
        v_mid = 0.0
        v_high = 0.0
        
        # Overlap slightly
        if ratio < 0.4:
            # Low to Mid transition
            # ratio 0.0 -> Low 1.0, Mid 0.0
            # ratio 0.4 -> Low 0.0, Mid 1.0
            local_t = ratio / 0.4
            v_low = 1.0 - local_t
            v_mid = local_t
        elif ratio < 0.7:
            # Mostly Mid
            v_mid = 1.0
        else:
            # Mid to High transition
            # ratio 0.7 -> Mid 1.0, High 0.0
            # ratio 1.0 -> Mid 0.0, High 1.0
            local_t = (ratio - 0.7) / 0.3
            v_mid = 1.0 - local_t
            v_high = local_t

        # Master Volume Factor
        master_vol = 0.6
        if accel_pressed:
            master_vol = 0.8
        
        # Apply
        self.ch_low.set_volume(v_low * master_vol)
        self.ch_mid.set_volume(v_mid * master_vol)
        self.ch_high.set_volume(v_high * master_vol)

    def silence(self):
        """Force silence all engine channels."""
        if not self.enabled: return
        self.ch_low.set_volume(0)
        self.ch_mid.set_volume(0)
        self.ch_high.set_volume(0)

    def cleanup(self):
        if self.enabled:
            self.ch_low.stop()
            self.ch_mid.stop()
            self.ch_high.stop()

    def toggle_mute(self):
        """Toggle the mute state of the engine sound."""
        if not self.enabled: return
        
        self.is_muted = not self.is_muted
        if self.is_muted:
            print("Engine Sound: Muted")
            self.ch_low.set_volume(0)
            self.ch_mid.set_volume(0)
            self.ch_high.set_volume(0)
        else:
            print("Engine Sound: Unmuted")

