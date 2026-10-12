from PIL import Image, ImageDraw, ImageFont

# --- Иконка приложения 512x512 ---
S = 512
img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([16, 16, S - 16, S - 16], radius=96, fill=(10, 14, 26, 255))
route = [(120, 392), (176, 300), (256, 332), (332, 208), (392, 132)]
d.line(route, fill=(255, 255, 255, 255), width=56, joint='curve')
d.line(route, fill=(30, 120, 255, 255), width=32, joint='curve')
d.ellipse([332, 72, 452, 192], fill=(230, 60, 50, 255))
d.ellipse([368, 108, 416, 156], fill=(255, 255, 255, 255))
img.save('icon.png')

# --- Сплэш-экран 480x800 ---
W, H = 480, 800
p = Image.new('RGB', (W, H), (6, 7, 10))
pd = ImageDraw.Draw(p)
try:
    fb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 40)
    fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 26)
except Exception:
    fb = ImageFont.load_default()
    fs = fb
rr = [(120, 520), (180, 440), (240, 470), (300, 380), (360, 320)]
pd.line(rr, fill=(30, 120, 255), width=10, joint='curve')
pd.ellipse([330, 290, 390, 350], fill=(230, 60, 50))
pd.text((W // 2, 620), 'Трекер маршрутов', font=fb, fill=(240, 244, 255), anchor='mm')
pd.text((W // 2, 670), 'Загрузка…', font=fs, fill=(255, 200, 90), anchor='mm')
p.save('presplash.png')
print('assets ok')
