"""Generates the wall-art textures for the conference room (posters, whiteboard notes, corkboard, diploma).

Run: python Tools/make_wall_art.py   -> Assets/ConferenceRoom/Textures/Art/*.png
All artwork is drawn here, so there are no licence concerns.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Assets", "ConferenceRoom", "Textures", "Art")
os.makedirs(OUT, exist_ok=True)
FONT_DIR = r"C:\Windows\Fonts"


def font(size, bold=False):
    for name in (("ARIALNB.TTF" if bold else "ARIALN.TTF"), "arialbd.ttf" if bold else "arial.ttf"):
        try:
            return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        c = lerp(top, bottom, y / (h - 1))
        for x in range(w):
            px[x, y] = c
    return img


def mountains():
    w, h = 800, 600
    img = gradient(w, h, (250, 190, 120), (120, 160, 210))
    d = ImageDraw.Draw(img)
    d.ellipse((560, 120, 660, 220), fill=(255, 240, 200))
    rnd = random.Random(3)
    layers = [((90, 110, 150), 330, 90), ((60, 80, 120), 400, 110), ((35, 50, 80), 470, 120)]
    for col, base, amp in layers:
        pts = [(0, h)]
        x = 0
        y = base
        while x <= w:
            pts.append((x, y))
            x += rnd.randint(40, 90)
            y = base - rnd.randint(0, amp)
        pts += [(w, base), (w, h)]
        d.polygon(pts, fill=col)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def skyline():
    w, h = 800, 600
    img = gradient(w, h, (20, 28, 60), (240, 140, 90))
    d = ImageDraw.Draw(img)
    rnd = random.Random(8)
    x = 0
    while x < w:
        bw = rnd.randint(40, 90)
        bh = rnd.randint(120, 380)
        d.rectangle((x, h - bh, x + bw, h), fill=(18, 20, 34))
        for wy in range(h - bh + 10, h - 10, 18):
            for wx in range(x + 6, x + bw - 8, 14):
                if rnd.random() < 0.45:
                    d.rectangle((wx, wy, wx + 6, wy + 9), fill=(255, 214, 120))
        x += bw + rnd.randint(0, 6)
    return img


def abstract():
    w, h = 600, 800
    img = Image.new("RGB", (w, h), (244, 240, 232))
    d = ImageDraw.Draw(img)
    cols = [(24, 110, 125), (232, 128, 40), (200, 60, 60), (40, 50, 90), (240, 200, 90)]
    rnd = random.Random(21)
    for i in range(7):
        x0, y0 = rnd.randint(30, 360), rnd.randint(30, 560)
        s = rnd.randint(110, 280)
        c = rnd.choice(cols)
        if i % 2:
            d.ellipse((x0, y0, x0 + s, y0 + s), fill=c)
        else:
            d.rectangle((x0, y0, x0 + s, y0 + int(s * rnd.uniform(0.5, 1.4))), fill=c)
    for _ in range(5):
        d.line((rnd.randint(0, w), rnd.randint(0, h), rnd.randint(0, w), rnd.randint(0, h)), fill=(30, 30, 30), width=rnd.randint(2, 6))
    return img


def motivation():
    w, h = 800, 600
    img = gradient(w, h, (30, 45, 70), (14, 20, 36))
    d = ImageDraw.Draw(img)
    d.rectangle((24, 24, w - 24, h - 24), outline=(220, 220, 230), width=3)
    f1, f2 = font(78, True), font(30)
    d.text((w / 2, 230), "TEAMWORK", font=f1, fill=(245, 245, 250), anchor="mm")
    d.line((220, 300, w - 220, 300), fill=(232, 128, 40), width=4)
    d.text((w / 2, 360), "Great things are done by a series of small things", font=f2, fill=(200, 205, 220), anchor="mm")
    d.text((w / 2, 400), "brought together.", font=f2, fill=(200, 205, 220), anchor="mm")
    # three little figures
    for i, cx in enumerate((300, 400, 500)):
        d.ellipse((cx - 14, 450, cx + 14, 478), fill=(232, 128, 40))
        d.rectangle((cx - 18, 480, cx + 18, 520), fill=(232, 128, 40))
    return img


def whiteboard():
    S = 2   # supersampled: the board is 2.2 m wide, so it needs about 1000 px per metre to read sharply in a headset
    w, h = 1100 * S, 600 * S
    img = Image.new("RGB", (w, h), (246, 247, 248))
    ghost = Image.new("RGB", (w, h), (246, 247, 248))
    gd = ImageDraw.Draw(ghost)
    rnd = random.Random(2)
    for _ in range(14):
        x, y = rnd.randint(0, w - 200 * S), rnd.randint(0, h - 40 * S)
        gd.line((x, y, x + rnd.randint(80 * S, 260 * S), y + rnd.randint(-10 * S, 10 * S)), fill=(228, 230, 233), width=rnd.randint(8 * S, 16 * S))
    img = Image.blend(img, ghost.filter(ImageFilter.GaussianBlur(5 * S)), 0.8)
    d = ImageDraw.Draw(img)
    blue, red, green, black = (30, 60, 170), (190, 40, 40), (30, 130, 70), (35, 35, 40)
    f = font(46 * S, True)
    f2 = font(30 * S)
    d.text((60 * S, 30 * S), "Q4 ROADMAP", font=f, fill=blue)
    d.line((60 * S, 90 * S, 420 * S, 92 * S), fill=blue, width=5 * S)
    for i, (label, col) in enumerate((("Design", blue), ("Build", green), ("Launch", red))):
        x0 = (60 + i * 340) * S
        d.rounded_rectangle((x0, 140 * S, x0 + 250 * S, 250 * S), radius=14 * S, outline=col, width=5 * S)
        d.text((x0 + 125 * S, 195 * S), label, font=f2, fill=col, anchor="mm")
        if i < 2:
            d.line((x0 + 262 * S, 195 * S, x0 + 322 * S, 195 * S), fill=black, width=5 * S)
            d.polygon([(x0 + 322 * S, 183 * S), (x0 + 340 * S, 195 * S), (x0 + 322 * S, 207 * S)], fill=black)
    for i, t in enumerate(("- user interviews", "- API v2", "- load testing", "- onboarding flow")):
        d.text((70 * S, (300 + i * 52) * S), t, font=f2, fill=black)
    d.ellipse((620 * S, 300 * S, 900 * S, 460 * S), outline=red, width=5 * S)
    d.text((760 * S, 380 * S), "Aug 12", font=font(40 * S, True), fill=red, anchor="mm")
    d.text((620 * S, 490 * S), "owners: SM / JL / AK", font=f2, fill=blue)
    return img


def corkboard():
    w, h = 900, 600
    rnd = random.Random(4)
    img = Image.new("RGB", (w, h), (176, 134, 92))
    px = img.load()
    for y in range(h):
        for x in range(w):
            n = rnd.randint(-22, 22)
            r, g, b = px[x, y]
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    d = ImageDraw.Draw(img)
    notes = [((255, 235, 120), "Standup\n9:30"), ((255, 180, 190), "Ship it!"), ((170, 230, 255), "Retro\nFri"), ((190, 245, 170), "Call\nMaria"), ((255, 235, 120), "Q4 goals"), ((255, 200, 140), "Lunch?")]
    f = font(34, True)
    for i, (col, txt) in enumerate(notes):
        x, y = 40 + (i % 3) * 290 + rnd.randint(-10, 10), 40 + (i // 3) * 270 + rnd.randint(-10, 10)
        d.rectangle((x + 6, y + 8, x + 236, y + 238), fill=(120, 90, 60))
        d.rectangle((x, y, x + 230, y + 230), fill=col)
        d.ellipse((x + 105, y + 8, x + 125, y + 28), fill=(200, 40, 40))
        d.multiline_text((x + 115, y + 130), txt, font=f, fill=(50, 50, 60), anchor="mm", align="center")
    return img


def diploma():
    w, h = 800, 600
    img = Image.new("RGB", (w, h), (248, 243, 228))
    d = ImageDraw.Draw(img)
    d.rectangle((20, 20, w - 20, h - 20), outline=(150, 110, 40), width=6)
    d.rectangle((34, 34, w - 34, h - 34), outline=(150, 110, 40), width=2)
    d.text((w / 2, 110), "CERTIFICATE", font=font(64, True), fill=(60, 50, 40), anchor="mm")
    d.text((w / 2, 180), "of Professional Excellence", font=font(34), fill=(90, 75, 55), anchor="mm")
    d.line((200, 250, w - 200, 250), fill=(150, 110, 40), width=2)
    d.text((w / 2, 320), "Awarded to the Hiring Team", font=font(36), fill=(60, 50, 40), anchor="mm")
    d.text((w / 2, 380), "for outstanding commitment to its people", font=font(28), fill=(90, 75, 55), anchor="mm")
    d.ellipse((330, 430, 470, 570), fill=(190, 150, 60), outline=(120, 90, 30), width=4)
    d.text((400, 500), "*", font=font(80, True), fill=(250, 235, 170), anchor="mm")
    return img


def map_poster():
    w, h = 800, 600
    img = Image.new("RGB", (w, h), (216, 228, 232))
    d = ImageDraw.Draw(img)
    rnd = random.Random(12)
    for _ in range(8):
        pts = [(rnd.randint(0, w), rnd.randint(0, h)) for _ in range(7)]
        d.polygon(pts, fill=rnd.choice([(190, 214, 190), (232, 224, 190), (200, 220, 236)]))
    for gx in range(0, w, 80):
        d.line((gx, 0, gx, h), fill=(180, 195, 205), width=1)
    for gy in range(0, h, 80):
        d.line((0, gy, w, gy), fill=(180, 195, 205), width=1)
    for _ in range(14):
        x, y = rnd.randint(40, w - 40), rnd.randint(40, h - 40)
        d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=(200, 50, 50))
    d.text((w / 2, 40), "WHERE WE WORK", font=font(44, True), fill=(40, 60, 90), anchor="mm")
    return img


for name, fn in (("poster_mountains", mountains), ("poster_city", skyline), ("poster_abstract", abstract), ("poster_teamwork", motivation),
                 ("whiteboard_notes", whiteboard), ("corkboard", corkboard), ("certificate", diploma), ("poster_map", map_poster)):
    fn().save(os.path.join(OUT, name + ".png"))
    print("wrote", name)
