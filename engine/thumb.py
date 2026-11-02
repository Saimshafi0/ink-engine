"""YouTube thumbnails (1280x720) in the drawn style."""
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from . import draw as D

W, H, K = 1280, 720, 2


def make_thumbnail(text, bg="desert", face="shocked", pose="scared", props=("coin",), mark=None,
                   side_text="right", seed=1, ai_image=None):
    img = D.new_canvas(W, H, K)
    pen = D.Pen(img, K, seed=seed, wobble=.7)
    if ai_image is not None:
        a = ai_image.convert("RGB").resize((W * K, H * K), Image.LANCZOS)
        img.paste(a)
        gy = H * .95
    else:
        gy = D.draw_bg(pen, bg, W, H, seed=seed)
    text_right = side_text != "left"
    px = W * (.3 if text_right else .7)
    ph = H * .78
    D.draw_person(pen, px, H * 1.02, ph, pose, face, lw=H * .009, flip=not text_right)
    props = [p for p in (props or []) if p][:2]
    for i, p in enumerate(props):
        x = W * ((.62 if text_right else .38) + i * (.16 if text_right else -.16))
        D.draw_prop(pen, p, x, H * .72, H * .3, lw=H * .008)
        if mark and i == 0:
            D.draw_prop(pen, mark, x, H * .72, H * .3)
    img = D.finish(img, W, H)
    img = ImageEnhance.Color(img).enhance(1.25)
    img = ImageEnhance.Contrast(img).enhance(1.06)
    _yellow_text(img, text.upper(), text_right)
    return img


def _yellow_text(img, text, right=True):
    words = text.split()
    lines = [text] if len(words) <= 2 else [" ".join(words[:len(words) // 2 + len(words) % 2]), " ".join(words[len(words) // 2 + len(words) % 2:])]
    box_w = W * .52
    size = 230
    f = D.font("bangers", size)
    while size > 60:
        f = D.font("bangers", size)
        ws = [f.getbbox(l)[2] - f.getbbox(l)[0] for l in lines]
        if max(ws) <= box_w and len(lines) * size * .95 <= H * .62:
            break
        size -= 6
    x = W * .97 if right else W * .03
    anchor = "ra" if right else "la"
    y = H * .05
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for i, l in enumerate(lines):
        sd.text((x + 8, y + 10 + i * size * .95), l, font=f, fill=(0, 0, 0, 150), anchor=anchor, stroke_width=11, stroke_fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    img.paste(sh, (0, 0), sh)
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        d.text((x, y + i * size * .95), l, font=f, fill=D.YELLOW, anchor=anchor, stroke_width=10, stroke_fill=D.INK)


def phone_preview(img):
    """168x94 preview (how it looks on a phone)."""
    return img.resize((168, 94), Image.LANCZOS)
