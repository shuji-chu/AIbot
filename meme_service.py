from PIL import Image, ImageDraw, ImageFont
import io, os, textwrap

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# 尝试找中文字体
for _p in ["/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc", "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc", "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Medium.ttc"]:
    if os.path.exists(_p):
        FONT_PATH = _p
        break


def _get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()


def make_meme(text, style="classic"):
    """生成表情包：文字 + 简单背景"""
    styles = {
        "classic": {"bg": (255, 255, 255), "fg": (0, 0, 0), "border": (0, 0, 0)},
        "dark": {"bg": (30, 30, 30), "fg": (255, 255, 255), "border": (255, 255, 255)},
        "pink": {"bg": (255, 228, 240), "fg": (200, 50, 100), "border": (255, 100, 150)},
        "yellow": {"bg": (255, 250, 200), "fg": (60, 60, 60), "border": (250, 200, 50)},
        "green": {"bg": (220, 255, 220), "fg": (30, 100, 30), "border": (100, 200, 100)},
        "blue": {"bg": (220, 240, 255), "fg": (30, 60, 120), "border": (100, 150, 220)},
    }
    s = styles.get(style, styles["classic"])

    W, H = 600, 600
    img = Image.new("RGB", (W, H), s["bg"])
    draw = ImageDraw.Draw(img)

    # 边框
    border_w = 8
    draw.rectangle([border_w//2, border_w//2, W-border_w//2, H-border_w//2],
                   outline=s["border"], width=border_w)

    # 计算字体大小
    font_size = 60
    lines = []
    while font_size > 20:
        font = _get_font(font_size)
        # 按字符数换行
        chars_per_line = max(4, int((W - 100) / (font_size * 0.95)))
        lines = textwrap.wrap(text, width=chars_per_line)
        total_h = len(lines) * font_size * 1.3
        if total_h < H - 150:
            break
        font_size -= 5

    font = _get_font(font_size)
    line_h = font_size * 1.3
    total_h = len(lines) * line_h
    y = (H - total_h) / 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (W - w) / 2
        # 描边
        for dx in [-2, 0, 2]:
            for dy in [-2, 0, 2]:
                draw.text((x+dx, y+dy), line, font=font, fill=s["border"] if s["fg"] != s["border"] else (128,128,128))
        draw.text((x, y), line, font=font, fill=s["fg"])
        y += line_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
