# Pseudo 3D Racing Game

A retro-style pseudo-3D racing game built with Python and Pygame.

![Version](https://img.shields.io/badge/Version-1.1-orange.svg)
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Pygame](https://img.shields.io/badge/Pygame-2.0+-green.svg)

![Screenshot](docs/screenshot.png)

## Features

- 6 stages with unique characteristics (curves, sand, wet roads, tunnels)
- Pseudo-3D graphics with perspective scrolling
- Digital speedometer and lap timer
- Ranking system (Top 5 scores saved)
- Gamepad support

## Requirements

- Python 3.8+
- Pygame 2.x
- [Git LFS](https://git-lfs.com/) — image and sound assets in `asset/` are stored with LFS

## Installation

```bash
git lfs install        # once per machine, before cloning
git clone https://github.com/masa7an/Racegame.git
cd Racegame
pip install pygame
```

If you cloned without Git LFS installed, run `git lfs pull` to fetch the assets.

### BGM (optional)

The background music is a third-party track and is **not included** in this repository.
The game runs fine without it (silently). To enable it, download
[Experimental Model by d-elf.com](https://www.d-elf.com/archives/4196.html)
and save it as `asset/Experimental_Model_long.mp3`.

## How to Run

```bash
python main.py
```

Or double-click `run.bat` on Windows.

## Controls

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Accelerate | ↑ / W / Space | Button A |
| Brake | ↓ / S / B | Button B |
| Steer | ← → | D-Pad / Stick |

### Game Clear Screen
- **CONTINUE**: Enter / Space / C
- **EXIT**: Esc / E

## Credits

### Development
This game was created almost entirely by a non-engineer using **Antigravity** and **Gemini** AI tools (except for the BGM).

### BGM
Music by d-elf.com (Experimental Model)  
https://www.d-elf.com/archives/4196.html

## License

This project is for personal/educational use.
