import pygame
import wave
import struct
import os

class SoundManager:
    # エンジン音は自作のループWAV 3本（低/中/高回転）を直接ロードする。
    # 生成元コード: project/engine_sound_gen/generate_engine.py（コード合成・権利問題なし）
    # 以前は第三者由来の engine.wav 1本をロード時にDSP加工＋ピッチシフトして
    # 3ループを合成していたが、素材差し替えに伴い廃止した。
    ENGINE_FILES = {
        "low": "engine_low.wav",
        "mid": "engine_mid.wav",
        "high": "engine_high.wav",
    }

    def __init__(self, start_run=False):
        # start_runフラグは、インスタンス生成時に即再生開始するかどうか（main.pyの都合に合わせる）

        # Initialize mixer if needed
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2)

        self.channels = {}
        self.sounds = {}
        self.user_volume = 1.0  # Master volume set via the settings menu (0.0-1.0)

        # Path to engine WAVs: this file lives in src/, while asset/ is a sibling
        # of src/ under the project root, so we need to go up one level.
        base_path = os.path.dirname(os.path.abspath(__file__))
        asset_dir = os.path.join(base_path, "..", "asset")

        try:
            loaded = {}
            for key, fname in self.ENGINE_FILES.items():
                wav_path = os.path.join(asset_dir, fname)
                if not os.path.exists(wav_path):
                    print(f"Warning: {wav_path} not found. Engine sound will be disabled.")
                    self.enabled = False
                    return
                loaded[key] = self._load_loop_sound(wav_path)

            self.enabled = True

            self.snd_low = loaded["low"]
            self.snd_mid = loaded["mid"]
            self.snd_high = loaded["high"]

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

    def _load_loop_sound(self, path):
        """16bit WAV を読み込み、ミキサー形式に合わせた pygame Sound を返す。
        Sound(buffer=) はミキサーの形式（44.1kHz/16bit/ステレオ）で解釈されるため、
        モノラル素材は左右に複製してステレオ化してから渡す。"""
        with wave.open(path, 'rb') as wf:
            params = wf.getparams()
            raw = wf.readframes(params.nframes)

        if params.sampwidth != 2:
            raise ValueError(f"{path}: 16bit WAVのみ対応 (got {params.sampwidth * 8}bit)")

        mixer_freq, _, mixer_ch = pygame.mixer.get_init()
        if params.framerate != mixer_freq:
            print(f"Warning: {path} is {params.framerate}Hz but mixer is "
                  f"{mixer_freq}Hz. Pitch will be shifted.")

        if params.nchannels == 1 and mixer_ch == 2:
            n = len(raw) // 2
            mono = struct.unpack(f"<{n}h", raw)
            stereo = [v for s in mono for v in (s, s)]
            raw = struct.pack(f"<{len(stereo)}h", *stereo)
        elif params.nchannels != mixer_ch:
            raise ValueError(f"{path}: {params.nchannels}ch はミキサー({mixer_ch}ch)と非互換")

        return pygame.mixer.Sound(buffer=raw)

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
        master_vol *= self.user_volume

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

    def set_master_volume(self, volume):
        """Sets the user master volume (0.0-1.0), applied on top of the engine's
        own speed-based mix on the next update() call."""
        self.user_volume = max(0.0, min(1.0, volume))

