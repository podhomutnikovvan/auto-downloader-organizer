#!/usr/bin/env python3
"""Generate app.ico for Auto Downloader Organizer (rounded dark square, blue folder, white arrow)."""
from PIL import Image, ImageDraw

S = 4  # supersampling factor
N = 256 * S

img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- background: rounded dark card with subtle gradient feel ---
r = int(56 * S)
d.rounded_rectangle([8*S, 8*S, N-8*S, N-8*S], radius=r, fill=(30, 34, 45, 255))
d.rounded_rectangle([8*S, 8*S, N-8*S, N-8*S], radius=r, outline=(79, 140, 255, 120), width=3*S)

# --- folder shape (blue accent) ---
fx1, fy1, fx2, fy2 = 48*S, 96*S, 208*S, 208*S
tab = (48*S, 78*S, 110*S, 100*S)  # folder tab
fr = 14 * S
d.rounded_rectangle(tab, radius=8*S, fill=(63, 111, 220, 255))
d.rounded_rectangle([fx1, fy1, fx2, fy2], radius=fr, fill=(79, 140, 255, 255))
# folder front flap slightly lighter
d.rounded_rectangle([fx1, 120*S, fx2, fy2], radius=fr, fill=(96, 156, 255, 255))

# --- white down-arrow into the folder (download symbol) ---
cx = N // 2
aw = 26 * S           # half width of arrow head
ah = 34 * S           # head height
sw = 22 * S           # shaft half width
top = 34 * S
head_bottom = 118 * S
poly = [
    (cx - sw, top),
    (cx + sw, top),
    (cx + sw, head_bottom - ah),
    (cx + aw, head_bottom - ah),
    (cx, head_bottom),
    (cx - aw, head_bottom - ah),
]
d.polygon(poly, fill=(255, 255, 255, 255))

# --- three little "sorted" dots at bottom of folder ---
for i, color in enumerate([(46, 204, 113, 255), (241, 196, 15, 255), (231, 76, 60, 255)]):
    x = cx + (i - 1) * 34 * S
    d.ellipse([x - 7*S, 178*S, x + 7*S, 192*S], fill=color)

img = img.resize((256, 256), Image.LANCZOS)
img.save("app.ico", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
img.save("app.png")
print("OK: app.ico + app.png created")
