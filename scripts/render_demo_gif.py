"""Render docs/screenshots/demo.gif from real Ghost CLI output.

Every frame shows the actual stdout/stderr of the commands below, run against
the synthetic sample case in examples/ (no real targets, no network calls).

Requires ``pip install pyte pillow`` plus ``ghost`` and ``jq`` on PATH::

    python scripts/render_demo_gif.py
"""

import glob
import os
import subprocess
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots" / "demo.gif"
COLS, ROWS = 84, 30
PAD, TOP, LINE_H = 16, 34, 19
BG, FG = (22, 24, 33), (220, 223, 228)
PALETTE = {
    "black": (40, 42, 54),
    "red": (255, 110, 110),
    "green": (110, 220, 140),
    "brown": (240, 200, 100),
    "yellow": (240, 200, 100),
    "blue": (110, 160, 255),
    "magenta": (210, 140, 255),
    "cyan": (110, 210, 230),
    "white": FG,
}

COMMANDS = [
    ("ghost import examples/sample-username-case.json", False, 1500),
    ("ghost list", False, 2600),
    ("ghost show a1b2c3d4", True, 3200),
    ("ghost export a1b2c3d4 -o case.json", True, 1200),
    ("jq '{target, scope, authorized_use, status, modules: (.findings|keys)}' case.json", False, 3500),
]


def load_font():
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    if not os.path.exists(path):
        path = glob.glob("/usr/share/fonts/**/*Mono*Regular*.ttf", recursive=True)[0]
    return ImageFont.truetype(path, 15)


def color(name, default):
    if name == "default":
        return default
    if name in PALETTE:
        return PALETTE[name]
    if isinstance(name, str) and len(name) == 6:
        try:
            return tuple(int(name[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return default
    return default


class Recorder:
    def __init__(self):
        self.font = load_font()
        self.cell_w = int(self.font.getlength("M"))
        self.width = COLS * self.cell_w + 2 * PAD
        self.height = ROWS * LINE_H + PAD + TOP
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)
        self.frames = []

    def snap(self, ms):
        img = Image.new("RGB", (self.width, self.height), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, self.width, TOP - 10], fill=(34, 36, 48))
        for i, dot in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            draw.ellipse([12 + i * 20, 7, 24 + i * 20, 19], fill=dot)
        draw.text(
            (self.width // 2 - 110, 5), "ghost — authorized self-audit demo", font=self.font, fill=(150, 155, 170)
        )
        for y in range(ROWS):
            row = self.screen.buffer[y]
            for x in range(COLS):
                cell = row[x]
                if cell.data == " " and cell.bg == "default":
                    continue
                fg, bg = color(cell.fg, FG), color(cell.bg, BG)
                if cell.reverse:
                    fg, bg = bg, fg
                px, py = PAD + x * self.cell_w, TOP + y * LINE_H
                if bg != BG:
                    draw.rectangle([px, py, px + self.cell_w, py + LINE_H], fill=bg)
                draw.text((px, py), cell.data, font=self.font, fill=fg)
        cx, cy = PAD + self.screen.cursor.x * self.cell_w, TOP + self.screen.cursor.y * LINE_H
        draw.rectangle([cx, cy + 2, cx + self.cell_w - 2, cy + LINE_H - 2], fill=(180, 180, 190))
        self.frames.append((img, ms))

    def feed(self, data: bytes):
        self.stream.feed(data)

    def run(self, cmd, hold):
        self.feed(b"\x1b[32m$\x1b[0m ")
        self.snap(400)
        for i, char in enumerate(cmd):
            self.feed(char.encode())
            if i % 2 == 1 or i == len(cmd) - 1:
                self.snap(45)
        self.snap(350)
        self.feed(b"\r\n")
        env = dict(os.environ, FORCE_COLOR="1", COLUMNS=str(COLS), TERM="xterm-256color")
        out = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=ROOT)
        self.feed(out.stdout.replace(b"\n", b"\r\n"))
        self.snap(hold)

    def save(self):
        images = [frame for frame, _ in self.frames]
        durations = [ms for _, ms in self.frames]
        images[0].save(OUT, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)


def main():
    rec = Recorder()
    rec.feed(b"\x1b[2m# Ghost: turn an authorized self-audit into a case file with provenance\x1b[0m\r\n\r\n")
    rec.snap(1200)
    for cmd, clear_first, hold in COMMANDS:
        if clear_first:
            rec.feed(b"\x1b[2J\x1b[H")
        rec.run(cmd, hold)
    rec.save()
    (ROOT / "case.json").unlink(missing_ok=True)
    print(f"wrote {OUT} ({len(rec.frames)} frames)")


if __name__ == "__main__":
    main()
