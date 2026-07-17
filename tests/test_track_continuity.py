# Track.draw / get_road_screen_offset のセグメント境界連続性の回帰テスト。
#
# 対象のバグ（コミット済みの修正の再発防止）:
#   draw() の x_turn 積算の原点がセグメント境界(start_idx*STRIPE_LENGTH)にあり、
#   player_z が STRIPE_LENGTH の倍数を跨ぐ瞬間に道路全体が横へ飛んでいた
#   （stage5 カーブ中盤で画面行317が6.3px、画面下端が7.5px。詳細は draw() の
#   Curve Accumulation のコメント参照）。dx の初期値を「現在セグメントの進行率」で
#   シードすることで原点を player_z に一致させている。
#
# ここでは2系統で確認する:
#   - draw() 本体をダミー画面へ実際に描き、道路中心のピクセル位置が境界前後で
#     飛ばないこと（実描画経路のend-to-endテスト）
#   - get_road_screen_offset()（背景係留用に同じ積算を複製している）の返り値が
#     z の全域走査で連続であること
# 「カメラ位置では x_turn == 0」は draw() 内の assert が担い、draw を呼ぶ
# テストすべてが毎フレームそれを通る。

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from src.track import Track, STRIPE_LENGTH

SCREEN_W, SCREEN_H = 800, 600
# 修正前の飛びは6.3px以上。ピクセル判定の量子化(1px)を見込んでも大きく分離できる
PIXEL_JUMP_LIMIT = 2.0
# get_road_screen_offset の実測最大ステップは0.0115px(z刻み1.0)。10倍の余裕を持たせても
# 修正前(6.3px)とは2桁離れている
OFFSET_JUMP_LIMIT = 0.1

# stage5 z=30000 は当初の実測地点、z=59700 は z=20000..60000 走査での最悪地点
BOUNDARIES = [30000.0, 59700.0]


@pytest.fixture(scope="module")
def screen():
    pygame.init()
    return pygame.display.set_mode((SCREEN_W, SCREEN_H))


@pytest.fixture()
def make_track(screen, monkeypatch):
    # Track.__init__ は asset/forest.png を cwd 相対で即ロードする（山肌テクスチャ）。
    # アセットはリポジトリ未追跡でワークツリーには無いため、ロードをスタブして
    # テストを実行場所非依存にする。ここで検証する積算・投影はテクスチャと無関係。
    def _make(stage):
        monkeypatch.setattr(
            pygame.image, "load",
            lambda _path: pygame.Surface((4, 4), pygame.SRCALPHA))
        track = Track()
        track.create_road(stage)
        return track
    return _make


def road_center_px(screen, track, player_z, stage, row):
    """draw() を実際に描き、画面行 row 上の道路スパンの中心xを返す。"""
    background = (255, 0, 255)  # 道路・フォグに現れない色
    screen.fill(background)
    track.draw(screen, player_z, 0.0, SCREEN_W, SCREEN_H, stage,
               None, track.get_height_at(player_z))
    xs = [x for x in range(SCREEN_W)
          if screen.get_at((x, row))[:3] != background]
    assert xs, f"row {row} に道路が描かれていない (z={player_z})"
    return (xs[0] + xs[-1]) / 2.0


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_draw_road_center_continuous_across_boundary(screen, make_track, boundary):
    """実描画: 境界を跨いでも道路中心のスクリーンxが飛ばない。"""
    track = make_track(5)
    row = 317  # 地平線(300)の17px下 ≈ 奥行き26471。当初のバグ実測に使った行
    prev = None
    worst = 0.0
    z = boundary - 5.0
    while z <= boundary + 5.0:
        center = road_center_px(screen, track, z, 5, row)
        if prev is not None:
            worst = max(worst, abs(center - prev))
        prev = center
        z += 0.5
    assert worst <= PIXEL_JUMP_LIMIT, (
        f"境界 z={boundary} 前後で道路中心が {worst:.2f}px 飛んだ"
        f"（許容 {PIXEL_JUMP_LIMIT}px。修正前は6.3px）")


@pytest.mark.parametrize("stage", [1, 5, 6])
def test_bg_anchor_offset_continuous(make_track, stage):
    """get_road_screen_offset: z の1.0刻み走査で返り値が連続（境界を多数跨ぐ）。"""
    track = make_track(stage)
    depth_z = 26471.0  # main.py が渡す ground_top_z と同程度の奥行き
    z0, z1 = 20000.0, 40000.0
    assert (z1 - z0) / STRIPE_LENGTH > 50  # 境界を十分な回数跨ぐ走査であること

    prev = None
    worst = 0.0
    worst_z = None
    z = z0
    while z <= z1:
        v = track.get_road_screen_offset(z, 0.0, depth_z)
        if prev is not None and abs(v - prev) > worst:
            worst, worst_z = abs(v - prev), z
        prev = v
        z += 1.0
    assert worst <= OFFSET_JUMP_LIMIT, (
        f"stage{stage}: z={worst_z} で背景係留オフセットが {worst:.4f}px 飛んだ"
        f"（許容 {OFFSET_JUMP_LIMIT}px。修正前は6.3px）")


def test_draw_camera_origin_assert_is_active(screen, make_track):
    """draw() 内の「カメラ位置で x_turn == 0」assert が生きていることの確認。

    アサート自体は draw() 内にあり、上のテストでも毎フレーム通っているが、
    ここでは境界ちょうど・境界直前の位相でも明示的に一度ずつ通す。
    （python -O で走らせると assert は消えるが、このテスト群自体が
    通常モードでの実行を前提とする）
    """
    track = make_track(5)
    for z in (30000.0, 30299.9, 29999.9):
        track.draw(screen, z, 0.0, SCREEN_W, SCREEN_H, 5,
                   None, track.get_height_at(z))
