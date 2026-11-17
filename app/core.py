# -*- coding: utf-8 -*-
"""Qiyos Jadval — yadro: PDF hisobotdan parchalarni qirqish va Word jadvalini yig'ish."""
import io
import os
import re
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from xml.sax.saxutils import escape

import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageFilter

pymupdf.TOOLS.mupdf_display_errors(False)

VERSION = "2.1"

# Tartib: uz -> ru -> en -> si
LANGS = ("uz", "ru", "en", "si")
SECTION_TITLES = {
    "uz": "O‘zbek tilidagi matn",
    "ru": "Rus tilidagi matn",
    "en": "Ingliz tilidagi matn",
    "si": "Sun’iy intellektdagi matn",
}
LANG_NAMES = {
    "uz": "O‘zbek tili",
    "ru": "Rus tili",
    "en": "Ingliz tili",
    "si": "Sun’iy intellekt (SI) detektori",
}

HL_COLOR = (1.0, 0.447, 0.227)      # antiplagiat hisobotidagi belgi rangi
LINE_WIDTH_CM = 10.0                # jadvalda matn satrining uzunligi (rasm shu o'lchamga keltiriladi)
MAX_IMG_HEIGHT_CM = 14.5            # bitta rasmning eng katta bo'yi (sahifaga sig'ishi uchun)
PAD_X = 2.0
PAD_Y = 2.5

DEFAULT_OPTS = {
    "dpi": 170,          # rasm sifati
    "fade": True,        # parchaga tegishli bo'lmagan qismni xiralashtirish
    "si_min_words": 1,   # SI: shundan kam so'zli parchalar tashlab ketiladi
    "colors": 128,       # PNG palitrasi (hajmni kichraytiradi); 0 = to'liq rang
}


# --------------------------------------------------------------------------- #
# Hujjat turini aniqlash
# --------------------------------------------------------------------------- #
def _close(c, t, e=0.06):
    return c is not None and len(c) == 3 and all(abs(a - b) < e for a, b in zip(c, t))


def _is_hl(d):
    return _close(d.get("fill"), HL_COLOR) and (d.get("fill_opacity") or 1) < 0.9


def _is_badge(d):
    if not _close(d.get("fill"), HL_COLOR) or (d.get("fill_opacity") or 1) < 0.9:
        return False
    r = d["rect"]
    return (r[2] - r[0]) < 70 and 8 < (r[3] - r[1]) < 40


def inspect_pdf(path):
    """PDF haqida tezkor ma'lumot: turi (plag/si), tili, sahifalar soni, sarlavha taxmini."""
    info = {"path": path, "kind": None, "lang": None, "pages": 0, "marks": 0,
            "name": "", "topic": "", "code": "", "degree": "", "error": ""}
    try:
        doc = pymupdf.open(path)
    except Exception as e:  # noqa
        info["error"] = "PDF ochilmadi: %s" % e
        return info
    try:
        if doc.needs_pass:
            info["error"] = "PDF parol bilan himoyalangan"
            return info
        n = len(doc)
        info["pages"] = n
        first = doc[0].get_text() if n else ""
        probe = list(range(0, min(n, 14)))
        ann = 0
        hl = 0
        for i in probe:
            p = doc[i]
            for a in p.annots() or []:
                if a.type[0] == 8:
                    ann += 1
            if not ann:
                for d in p.get_cdrawings():
                    if _is_badge(d) and i > 0:
                        hl += 1
        low = first.lower()
        if ann or "si detektori" in low or "sun'iy intellekt" in low:
            info["kind"] = "si"
            info["lang"] = "si"
        elif hl or "hisobot to'g'risidagi" in low or "qidirish modullari" in low:
            info["kind"] = "plag"
            if "translate_ru_" in low:
                info["lang"] = "ru"
            elif "translate_en_" in low:
                info["lang"] = "en"
            else:
                info["lang"] = _guess_lang(doc)
        info.update(_guess_title(doc))
    except Exception as e:  # noqa
        info["error"] = "PDF o'qishda xato: %s" % e
    finally:
        doc.close()
    return info


def _guess_lang(doc):
    n = len(doc)
    text = ""
    for i in range(min(n - 1, 8), min(n, 20)):
        text += doc[i].get_text()
    if not text.strip():
        return "uz"
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "uz"
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ") / len(letters)
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    if cyr > 0.5:
        # kirill: o'zbekcha (ў қ ғ ҳ) yoki ruscha
        uzc = sum(low.count(ch) for ch in "ўқғҳ")
        return "uz" if uzc > len(letters) * 0.01 else "ru"
    en = sum(low.count(w) for w in (" the ", " of ", " and ", " in ", " to "))
    uz = sum(low.count(w) for w in (" va ", " bilan ", " uchun ", " bo", " hamda "))
    return "en" if en > uz else "uz"


def _guess_title(doc):
    """Titul varaqdan F.I.Sh., mavzu, ixtisoslik va darajani topishga urinish."""
    out = {"name": "", "topic": "", "code": "", "degree": ""}
    for i in range(min(len(doc), 6)):
        txt = doc[i].get_text()
        if "DISSERTATSIYA" not in txt.upper() and "ДИССЕРТАЦИЯ" not in txt.upper():
            continue
        lines = [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines()]
        lines = [l for l in lines if l]
        code_i = None
        for k, l in enumerate(lines):
            if re.match(r"^\d{2}\.\d{2}\.\d{2}", l):
                code_i = k
                out["code"] = l
                break
        if code_i is None:
            continue
        # koddan yuqoridagi BOSH harfli satrlar: avval F.I.Sh., keyin mavzu
        caps = []
        k = code_i - 1
        while k >= 0:
            l = lines[k]
            letters = [c for c in l if c.isalpha()]
            if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8:
                caps.insert(0, l)
                k -= 1
            else:
                break
        if len(caps) >= 2:
            out["name"] = _title_case(caps[0])
            topic = " ".join(caps[1:])
            out["topic"] = topic[:1].upper() + topic[1:].lower()
        for l in lines[code_i + 1: code_i + 5]:
            if "fanlari" in l.lower() or "наук" in l.lower():
                out["degree"] = l
                break
        break
    return out


def _title_case(s):
    parts = []
    for w in s.split():
        parts.append(w[:1].upper() + w[1:].lower())
    return " ".join(parts)


def default_title(info, org="Andijon davlat universiteti"):
    name = info.get("name") or "............................................"
    topic = info.get("topic") or "............................................"
    code = info.get("code") or "00.00.00 – ................"
    code = re.sub(r"\s*[–-]\s*", " – ", code, count=1)
    deg = info.get("degree") or ""
    m = re.search(r"(\w+)\s+fanlari\s+b\S+\s+(.+)", deg, re.I)
    if m:
        branch = m.group(1).lower()
        degree = re.sub(r"[оО]", "o", m.group(2)).strip().rstrip(".")
        degree = degree.replace("dоktоri", "doktori")
    else:
        branch, degree = ".........", "falsafa doktori (PhD)"
    for a, b in (("о", "o"), ("О", "O"), ("ʻ", "‘"), ("'", "‘"), ("’", "‘"), ("`", "‘")):
        branch = branch.replace(a, b)
    return ("%s tadqiqotchisi %sning “%s” mavzusidagi %s ixtisosligidan %s fanlari "
            "bo‘yicha %s ilmiy darajasini olish uchun taqdim qilgan dissertatsiyasini "
            "plagiat holati mavjudligini o‘rganish uchun tekshirish natijalari yuzasidan"
            % (org, name, topic, code, branch, degree))


# --------------------------------------------------------------------------- #
# Sahifa tahlili
# --------------------------------------------------------------------------- #
def text_bounds(path, kind):
    """Matn maydonining chap va o'ng chegarasi (barcha rasmlar bir xil enda bo'lishi uchun)."""
    doc = pymupdf.open(path)
    try:
        n = len(doc)
        start = 3 if (kind == "plag" and n > 6) else (1 if n > 3 else 0)
        idx = list(range(start, n))
        if len(idx) > 30:
            step = len(idx) / 30.0
            idx = [idx[int(i * step)] for i in range(30)]
        sizes = {}
        for i in idx:
            p = doc[i]
            key = (round(p.rect.width), round(p.rect.height))
            ws = [w for w in p.get_text("words") if w[4].strip()]
            if len(ws) < 30:
                continue
            sizes.setdefault(key, []).append((min(w[0] for w in ws), max(w[2] for w in ws)))
        res = {}
        for key, v in sizes.items():
            ls = sorted(a for a, _ in v)
            rs = sorted(b for _, b in v)
            res[key] = (ls[len(ls) // 5], rs[(len(rs) * 4) // 5])
        return res
    finally:
        doc.close()


def _plag_pieces(page):
    """Antiplagiat hisoboti: har bir raqamli belgigacha bo'lgan oraliq = bitta parcha."""
    hl, badges = [], []
    for d in page.get_cdrawings():
        if _is_hl(d):
            hl.append(tuple(d["rect"]))
        elif _is_badge(d):
            badges.append(tuple(d["rect"]))
    if not hl:
        return []
    end_at = {}
    for b in badges:
        best, bd = None, 1e9
        for i, r in enumerate(hl):
            dist = abs(r[2] - b[0]) + abs(r[3] - b[3])
            if abs(r[2] - b[0]) < 2.5 and abs(r[3] - b[3]) < 4 and dist < bd:
                best, bd = i, dist
        if best is not None:
            end_at[best] = b
    pieces, cur = [], []
    prev_badge, sx = None, None
    for i, r in enumerate(hl):
        if not cur:
            sx = r[0]
            # oldingi parchaning raqami shu satrda bo'lsa, parcha o'sha raqamdan keyin boshlanadi
            if prev_badge and abs(prev_badge[3] - r[3]) < 4 and r[0] <= prev_badge[2] + 2:
                sx = prev_badge[2]
        cur.append(r)
        if i in end_at:
            b = end_at[i]
            num = page.get_text("text", clip=pymupdf.Rect(b)).strip()
            pieces.append({"rects": cur, "badge": b, "num": num, "open_end": False,
                           "open_start": False, "color": "plag", "start_x": sx})
            cur = []
            prev_badge = b
    if cur:
        pieces.append({"rects": cur, "badge": None, "num": "", "open_end": True,
                       "open_start": False, "color": "plag", "start_x": sx})
    if pieces:
        pieces[0]["open_start"] = True   # oldingi sahifa ochiq qolgan bo'lsa ulanadi
    return pieces


def _si_pieces(page, min_words=1):
    """SI detektori: uzluksiz bir xil rangda belgilangan matn = bitta parcha."""
    ann = []
    for a in page.annots() or []:
        if a.type[0] != 8:
            continue
        col = a.colors.get("stroke") or a.colors.get("fill") or [1, 1, 0]
        r = a.rect
        ann.append((r.x0, r.y0, r.x1, r.y1, "si" if col[2] > 0.79 else "ehtimoliy"))
    if not ann:
        return []
    H = page.rect.height
    words = [w for w in page.get_text("words") if w[4].strip()]

    def body(w):
        cy = (w[1] + w[3]) / 2
        return not (w[4].strip().isdigit() and (cy > 0.9 * H or cy < 0.07 * H))

    words = [w for w in words if body(w)]
    marks = []
    for w in words:
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        m = None
        for a in ann:
            if a[0] - 1 <= cx <= a[2] + 1 and a[1] <= cy <= a[3]:
                m = a
                break
        marks.append(m)
    pieces, run, run_col = [], [], None

    def flush():
        nonlocal run, run_col
        if run and len(run) >= min_words:
            lines, order = {}, []
            for w, a in run:
                key = (w[5], w[6], round(a[1]))
                if key not in lines:
                    lines[key] = [w[0], a[1], w[2], a[3]]
                    order.append(key)
                else:
                    L = lines[key]
                    L[0] = min(L[0], w[0])
                    L[2] = max(L[2], w[2])
            pieces.append({"rects": [tuple(lines[k]) for k in order], "badge": None, "num": "",
                           "open_end": False, "open_start": False, "color": run_col})
        run, run_col = [], None

    for idx, (w, a) in enumerate(zip(words, marks)):
        col = a[4] if a else None
        if col != run_col:
            flush()
        if a:
            run.append((w, a))
            run_col = col
    last_open = bool(run)
    flush()
    if pieces:
        if marks and marks[0] is not None:
            pieces[0]["open_start"] = True
        if last_open and marks and marks[-1] is not None:
            pieces[-1]["open_end"] = True
    return pieces


def _group_lines(rects):
    """To'rtburchaklarni satrlarga guruhlash -> [(y0, y1, x0, x1), ...] yuqoridan pastga."""
    lines = []
    for r in sorted(rects, key=lambda r: (r[1], r[0])):
        if lines and r[1] < lines[-1][1] - (lines[-1][1] - lines[-1][0]) * 0.45:
            L = lines[-1]
            lines[-1] = (min(L[0], r[1]), max(L[1], r[3]), min(L[2], r[0]), max(L[3], r[2]))
        else:
            lines.append((r[1], r[3], r[0], r[2]))
    return lines


def render_pages(job):
    """Ishchi jarayon: berilgan sahifalardagi parchalarni topadi va rasm qilib qirqadi."""
    path, kind, pages, opts, bounds = job
    dpi = opts.get("dpi", 170)
    fade = opts.get("fade", False)
    ncol = opts.get("colors", 128)
    zoom = dpi / 72.0
    out = []
    doc = pymupdf.open(path)
    try:
        for pno in pages:
            page = doc[pno]
            pieces = _plag_pieces(page) if kind == "plag" else _si_pieces(page, opts.get("si_min_words", 1))
            if not pieces:
                out.append((pno, []))
                continue
            W, H = page.rect.width, page.rect.height
            words = [w for w in page.get_text("words") if w[4].strip()]
            bdg = [pc["badge"] for pc in pieces if pc["badge"]]
            if bdg:   # raqamli belgilar ichidagi son matn hisoblanmaydi
                words = [w for w in words if not any(
                    g[0] - 1 <= (w[0] + w[2]) / 2 <= g[2] + 1 and g[1] - 1 <= (w[1] + w[3]) / 2 <= g[3] + 1
                    for g in bdg)]
            b = bounds.get((round(W), round(H)))
            if b is None:
                b = (min(w[0] for w in words), max(w[2] for w in words)) if words else (W * 0.1, W * 0.93)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            img = Image.frombuffer("RGB", (pix.width, pix.height), pix.samples, "raw", "RGB", pix.stride, 1)
            res = []
            for pc in pieces:
                rects = list(pc["rects"])
                allr = rects + ([pc["badge"]] if pc["badge"] else [])
                x0 = max(0, min(b[0], min(r[0] for r in allr)) - PAD_X)
                x1 = min(W, max(b[1], max(r[2] for r in allr)) + PAD_X)
                lines = _group_lines(allr)
                line_pt = max(50.0, b[1] - b[0])
                wcm = LINE_WIDTH_CM * (x1 - x0) / line_pt      # satr uzunligi doim 10 sm bo'ladi
                max_h = MAX_IMG_HEIGHT_CM / LINE_WIDTH_CM * line_pt
                # juda baland parchani satr chegarasidan bo'laklarga ajratamiz
                chunks, cur = [], []
                for L in lines:
                    if cur and (L[1] - cur[0][0]) > max_h:
                        chunks.append(cur)
                        cur = []
                    cur.append(L)
                if cur:
                    chunks.append(cur)
                start_x = pc.get("start_x") or rects[0][0]
                end_x = (pc["badge"][2] if pc["badge"] else rects[-1][2])
                imgs = []
                for ci, ch in enumerate(chunks):
                    top, bot = ch[0][0], ch[-1][1]
                    y0, y1, erase, ft, fb = _clean_edges(words, allr, ch[0], ch[-1], x0, x1, H)
                    box = (int(x0 * zoom), int(-(-y0 * zoom // 1)), int(round(x1 * zoom)), int(y1 * zoom))
                    if box[3] - box[1] < 4:
                        box = (box[0], int(top * zoom), box[2], int(round(bot * zoom)))
                    crop = img.crop(box)
                    crop.load()
                    for e in erase:
                        _erase(crop, (int(e[0] * zoom) - box[0], int(e[1] * zoom) - box[1],
                                      int(e[2] * zoom) + 1 - box[0], int(e[3] * zoom) + 1 - box[1]), zoom)
                    if ft:
                        _flood_clean(crop, "top", int(ft[0] * zoom) + 1, int(ft[1] * zoom) + 1, zoom)
                    if fb:
                        _flood_clean(crop, "bottom", int(fb[0] * zoom) + 1, int(fb[1] * zoom) + 1, zoom)
                    if fade:
                        if ci == 0 and start_x - x0 > 8:
                            _fade(crop, 0, 0, int((start_x - x0 - 1) * zoom), int((ch[0][1] - y0 + 1) * zoom))
                        if ci == len(chunks) - 1 and x1 - end_x > 8 and not pc["open_end"]:
                            _fade(crop, int((end_x - x0 + 1) * zoom), int((ch[-1][0] - y0 - 1) * zoom),
                                  crop.width, crop.height)
                    imgs.append(_encode(crop, ncol) + (wcm,))
                res.append({"imgs": imgs, "num": pc["num"], "color": pc["color"],
                            "open_start": pc["open_start"], "open_end": pc["open_end"]})
            out.append((pno, res))
    finally:
        doc.close()
    return out


_INK_LUT = [255 if v < 235 else 0 for v in range(256)]
_ORANGE_LUT = [255 if v < 150 else 0 for v in range(256)]


def _clean_edges(words, rects, first, last, x0, x1, H):
    """Rasmning yuqori va pastki chegarasini tanlaydi: o'z satri butun qoladi, qo'shni satrlar
    kirmaydi. Qaytaradi: (y0, y1, o'chiriladigan to'rtburchaklar, yuqori tozalash balandligi,
    pastki tozalash balandligi) — hammasi sahifa birliklarida (pt)."""
    top, bot = first[0], last[1]
    inx = [w for w in words if w[2] > x0 and w[0] < x1]

    def is_own(w):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        for r in rects:
            if r[0] - 1.5 <= cx <= r[2] + 1.5 and r[1] - 1 <= cy <= r[3] + 1:
                return True
        return False

    own_all = [w for w in inx if is_own(w)]
    others = [w for w in inx if not is_own(w)]
    erase = []
    flood_top = flood_bot = None

    # ---- yuqori chegara
    line = [w for w in own_all if first[0] <= (w[1] + w[3]) / 2 <= first[1]] or \
           [w for w in inx if first[0] <= (w[1] + w[3]) / 2 <= first[1]]
    own_top = min([w[1] for w in line] or [top])
    lh = max([w[3] - w[1] for w in line] or [12.0])
    margin = max(0.8, 0.075 * lh)
    above = [w for w in others if (w[1] + w[3]) / 2 < min(first[0], own_top)]
    y0 = min(top - PAD_Y, own_top - margin)
    near = [w for w in above if w[3] > y0 - 1.5]
    if near:
        m = max(w[3] for w in near)
        gap = own_top - m
        if gap >= 2.4:
            y0 = m + gap / 2
        else:
            y0 = own_top - margin
            flood_top = (max(m, own_top) + 1.3 - y0, own_top + 0.3 - y0)
    y0 = max(0.0, y0)
    for w in others:
        if w[1] < y0 - 0.2 and w[3] - y0 > 2.6:
            lim = [o[1] for o in own_all if o[2] > w[0] and o[0] < w[2] and o[3] > y0]
            yb = min([w[3] + 1.0] + [v + 0.5 for v in lim])
            if yb > y0:
                erase.append((w[0] - 1.5, y0, w[2] + 1.5, yb))

    # ---- pastki chegara
    line = [w for w in own_all if last[0] <= (w[1] + w[3]) / 2 <= last[1]] or \
           [w for w in inx if last[0] <= (w[1] + w[3]) / 2 <= last[1]]
    own_bot = max([w[3] for w in line] or [bot])
    lh = max([w[3] - w[1] for w in line] or [12.0])
    margin = max(0.8, 0.075 * lh)
    below = [w for w in others if (w[1] + w[3]) / 2 > max(last[1], own_bot)]
    y1 = max(bot + PAD_Y, own_bot + margin)
    near = [w for w in below if w[1] < y1 + 1.5]
    if near:
        m = min(w[1] for w in near)
        gap = m - own_bot
        if gap >= 2.4:
            y1 = own_bot + gap / 2
        else:
            y1 = own_bot + margin
            flood_bot = (y1 - (min(m, own_bot) - 1.3), y1 - (own_bot + 0.7))
    y1 = min(H, y1)
    for w in others:
        if w[3] > y1 + 0.2 and y1 - w[1] > 2.6:
            lim = [o[3] for o in own_all if o[2] > w[0] and o[0] < w[2] and o[1] < y1]
            ya = max([w[1] - 1.0] + [v - 0.5 for v in lim])
            if ya < y1:
                erase.append((w[0] - 1.5, ya, w[2] + 1.5, y1))
    return y0, y1, erase, flood_top, flood_bot


def _flood_clean(im, edge, hs, zone, zoom):
    """Rasm chetidagi tor zonada turgan va ichkariga o'tib ketmaydigan siyoh bo'laklarini (qo'shni
    satr harflarining uchlari, tagchiziqlari) fon rangi bilan yopadi. Jadval chiziqlari saqlanadi."""
    W, Ht = im.size
    hs = max(2, min(hs, Ht // 2))
    zone = max(1, min(zone, hs - 1))
    box = (0, 0, W, hs) if edge == "top" else (0, Ht - hs, W, Ht)
    strip = im.crop(box)
    r_, g_, b_ = strip.split()
    # siyoh: fon (oq yoki och rangli belgi) bo'lmagan hamma narsa — matn, chiziq, raqamli belgi
    mask = ImageChops.lighter(ImageChops.lighter(ImageChops.lighter(r_, g_), b_).point(_INK_LUT), g_.point(_ORANGE_LUT))
    rows = range(0, zone) if edge == "top" else range(hs - 1, hs - 1 - zone, -1)
    found = False
    for e in rows:
        if mask.crop((0, e, W, e + 1)).point(_EQ255).getbbox() is None:
            continue
        px = mask.load()
        for x in range(W):
            if px[x, e] != 255:
                continue
            ImageDraw.floodfill(mask, (x, e), 128)
            bb = mask.point(_EQ128).getbbox()
            through = bb is not None and (bb[3] >= hs if edge == "top" else bb[1] <= 0)
            mask = mask.point(_TO64 if through else _TO200)
            px = mask.load()
            found = found or not through
    if not found:
        return
    rem = mask.point(_EQ200).filter(ImageFilter.MaxFilter(3))
    # fon: o'chirilgan har bir nuqta shu ustundagi eng yaqin toza (siyohsiz) nuqta rangini oladi
    bad = ImageChops.lighter(rem, mask.point(_NONZERO))      # manba bo'la olmaydigan nuqtalar
    todo = rem
    for dy in (1, -1) if edge == "top" else (-1, 1):
        src, src_bad = strip, bad
        for _ in range(hs):
            if todo.getbbox() is None:
                break
            src = _shift(src, dy, (255, 255, 255))
            src_bad = _shift(src_bad, dy, 255)
            ok = ImageChops.subtract(todo, src_bad)           # manbasi toza bo'lgan nuqtalar
            if ok.getbbox() is not None:
                strip.paste(src, (0, 0), ok)
                todo = ImageChops.subtract(todo, ok)
    if todo.getbbox() is not None:
        k = int(zoom * 2.2) * 2 + 1
        strip.paste(strip.filter(ImageFilter.MaxFilter(k)), (0, 0), todo)
    im.paste(strip, box[:2])


def _shift(im, dy, fill):
    """Tasvirni dy qatorga suradi (dy=1: har nuqta o'zidan pastdagi nuqtani oladi)."""
    out = Image.new(im.mode, im.size, fill)
    out.paste(im, (0, -dy))
    return out


_NONZERO = [255 if v else 0 for v in range(256)]


_EQ255 = [255 if v == 255 else 0 for v in range(256)]
_EQ128 = [255 if v == 128 else 0 for v in range(256)]
_EQ200 = [255 if v == 200 else 0 for v in range(256)]
_TO64 = [64 if v == 128 else v for v in range(256)]
_TO200 = [200 if v == 128 else v for v in range(256)]


def _erase(im, box, zoom):
    """Qo'shni satrdan qolgan izni fon rangi bilan yopadi (belgi rangi saqlanadi)."""
    x0, y0 = max(0, box[0]), max(0, box[1])
    x1, y1 = min(im.width, box[2]), min(im.height, box[3])
    if x1 - x0 < 1 or y1 - y0 < 1:
        return
    k = int(zoom * 2.2) * 2 + 1
    reg = im.crop((x0, y0, x1, y1))
    im.paste(reg.filter(ImageFilter.MaxFilter(k)), (x0, y0))


def _fade(im, x0, y0, x1, y1):
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(im.width, x1), min(im.height, y1)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return
    reg = im.crop((x0, y0, x1, y1))
    white = Image.new("RGB", reg.size, (255, 255, 255))
    im.paste(Image.blend(reg, white, 0.72), (x0, y0))


def _encode(im, ncol):
    w, h = im.size
    if ncol:
        im = im.quantize(colors=ncol, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    im.save(buf, "PNG", compress_level=6)
    return (buf.getvalue(), w, h)


def _stitch(parts, ncol):
    ims = [Image.open(io.BytesIO(p[0])).convert("RGB") for p in parts]
    W = max(i.width for i in ims)
    Ht = sum(i.height for i in ims)
    canvas = Image.new("RGB", (W, Ht), (255, 255, 255))
    y = 0
    for i in ims:
        canvas.paste(i, (0, y))
        y += i.height
    return _encode(canvas, ncol) + (max(p[3] for p in parts),)


# --------------------------------------------------------------------------- #
# Asosiy quvur
# --------------------------------------------------------------------------- #
class Cancelled(Exception):
    pass


_POOL = None
_POOL_N = 0


def _noop(i):
    return i


def get_pool(n=None):
    """Ishchi jarayonlar hovuzi bir marta yaratiladi va keyingi ishlarda qayta ishlatiladi."""
    global _POOL, _POOL_N
    n = n or max(1, min(os.cpu_count() or 2, 8))
    if _POOL is None or _POOL_N != n:
        if _POOL is not None:
            _POOL.shutdown(wait=False, cancel_futures=True)
        _POOL = ProcessPoolExecutor(max_workers=n)
        _POOL_N = n
    return _POOL


def warm_up():
    """Ilova ochilganda ishchilarni oldindan ishga tushirib qo'yadi (birinchi ish tez boshlanadi)."""
    try:
        pool = get_pool()
        list(pool.map(_noop, range(_POOL_N * 2)))
    except Exception:  # noqa
        reset_pool()


def reset_pool():
    global _POOL
    if _POOL is not None:
        try:
            _POOL.shutdown(wait=False, cancel_futures=True)
        except Exception:  # noqa
            pass
    _POOL = None


def build(inputs, out_path, title="", signers=None, opts=None, progress=None, cancel=None, workers=None):
    """inputs: {"uz": path, "ru": path, "en": path, "si": path} (bo'shlari tashlab ketiladi).

    Natija: {"counts": {lang: n}, "total": n, "seconds": s, "path": out_path}
    """
    o = dict(DEFAULT_OPTS)
    o.update(opts or {})
    t0 = time.time()
    say = progress or (lambda *a, **k: None)
    docs = []
    for lang in LANGS:
        p = inputs.get(lang)
        if not p:
            continue
        info = inspect_pdf(p)
        if info["error"]:
            raise ValueError("%s: %s" % (os.path.basename(p), info["error"]))
        kind = info["kind"] or ("si" if lang == "si" else "plag")
        docs.append((lang, p, kind, info["pages"]))
    if not docs:
        raise ValueError("Hech qanday PDF tanlanmagan")
    total_pages = sum(d[3] for d in docs)
    say(0, total_pages, "Tahlil qilinmoqda…")

    jobs = []
    chunk = 4
    for lang, p, kind, n in docs:
        bounds = text_bounds(p, kind)
        for s in range(0, n, chunk):
            jobs.append((lang, (p, kind, list(range(s, min(n, s + chunk))), o, bounds)))
    results = {d[0]: {} for d in docs}
    done = 0
    nw = workers or max(1, min(os.cpu_count() or 2, 8))
    if nw == 1:
        for lang, job in jobs:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            for pno, res in render_pages(job):
                results[lang][pno] = res
            done += len(job[2])
            say(done, total_pages, "Qirqilmoqda…")
    else:
        ex = get_pool(workers)
        try:
            futs = {ex.submit(render_pages, job): (lang, job) for lang, job in jobs}
        except Exception:  # hovuz buzilgan bo'lsa qayta yaratamiz
            reset_pool()
            ex = get_pool(workers)
            futs = {ex.submit(render_pages, job): (lang, job) for lang, job in jobs}
        try:
            for f in as_completed(futs):
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                lang, job = futs[f]
                for pno, res in f.result():
                    results[lang][pno] = res
                done += len(job[2])
                say(done, total_pages, "Qirqilmoqda…")
        except BaseException as e:
            for f in futs:
                f.cancel()
            if not isinstance(e, Cancelled):
                reset_pool()
            raise

    # sahifadan sahifaga o'tgan parchalarni birlashtirish
    sections, counts = [], {}
    for lang, p, kind, n in docs:
        rows = []
        prev_open, prev_page = False, -5
        for pno in range(n):
            res = results[lang].get(pno) or []
            for i, pc in enumerate(res):
                joined = False
                if i == 0 and prev_open and prev_page == pno - 1 and pc["open_start"] and rows \
                        and rows[-1]["color"] == pc["color"]:
                    rows[-1]["imgs"].extend(pc["imgs"])
                    rows[-1]["num"] = pc["num"] or rows[-1]["num"]
                    joined = True
                if not joined:
                    rows.append({"imgs": list(pc["imgs"]), "num": pc["num"], "color": pc["color"], "page": pno + 1})
            if res:
                prev_open, prev_page = res[-1]["open_end"], pno
            else:
                prev_open = False
        for r in rows:
            if len(r["imgs"]) > 1:
                r["imgs"] = _merge_images(r["imgs"], o.get("colors", 128))
        counts[lang] = len(rows)
        sections.append((lang, rows))
    say(total_pages, total_pages, "Word hujjat yozilmoqda…")
    write_docx(out_path, sections, title, signers or {})
    return {"counts": counts, "total": sum(counts.values()), "seconds": time.time() - t0, "path": out_path}


def _merge_images(imgs, ncol):
    """Ketma-ket bo'laklarni balandlik chegarasidan oshmaguncha bitta rasmga ulash."""
    out, cur = [], []

    def h_cm(parts):
        return sum(p[3] * p[2] / p[1] for p in parts)

    for im in imgs:
        if cur and h_cm(cur + [im]) > MAX_IMG_HEIGHT_CM:
            out.append(cur)
            cur = []
        cur.append(im)
    if cur:
        out.append(cur)
    return [g[0] if len(g) == 1 else _stitch(g, ncol) for g in out]


# --------------------------------------------------------------------------- #
# Word (.docx) yozish — to'g'ridan-to'g'ri, tez
# --------------------------------------------------------------------------- #
W_NUM, W_IMG, W_NOTE = 700, 6500, 7370
MAX_IMG_WIDTH_CM = 11.05            # rasm ustuniga sig'adigan eng katta en
EMU_CM = 360000

_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
       'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
       'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
       'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def _run(text, bold=False, size=24):
    rpr = "<w:rPr>%s<w:sz w:val=\"%d\"/><w:szCs w:val=\"%d\"/></w:rPr>" % ("<w:b/><w:bCs/>" if bold else "", size, size)
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, escape(text))


def _par(text="", bold=False, size=24, jc="left", extra=""):
    return "<w:p><w:pPr>%s<w:jc w:val=\"%s\"/><w:rPr>%s<w:sz w:val=\"%d\"/><w:szCs w:val=\"%d\"/></w:rPr></w:pPr>%s</w:p>" % (
        extra, jc, "<w:b/><w:bCs/>" if bold else "", size, size, _run(text, bold, size) if text else "")


def _cell(width, content, span=1, valign="top"):
    return "<w:tc><w:tcPr><w:tcW w:w=\"%d\" w:type=\"dxa\"/>%s<w:vAlign w:val=\"%s\"/></w:tcPr>%s</w:tc>" % (
        width, '<w:gridSpan w:val="%d"/>' % span if span > 1 else "", valign, content)


def _drawing(rid, n, w_px, h_px, wcm):
    cx = int(min(wcm, MAX_IMG_WIDTH_CM) * EMU_CM)
    cy = int(cx * h_px / w_px)
    return ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            '<wp:extent cx="%d" cy="%d"/><wp:docPr id="%d" name="Rasm %d"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic><pic:nvPicPr><pic:cNvPr id="%d" name="Rasm %d"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>') % (cx, cy, n, n, n, n, rid, cx, cy)


def write_docx(out_path, sections, title="", signers=None):
    signers = signers or {}
    body = []
    if title.strip():
        for line in title.strip().splitlines():
            if line.strip():
                body.append(_par(line.strip(), True, 28, "center"))
    body.append(_par("QIYOSIY JADVAL", True, 28, "center", '<w:spacing w:before="120" w:after="120"/>'))
    tbl = ['<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:tblBorders>' % (W_NUM + W_IMG + W_NOTE)]
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tbl.append('<w:%s w:val="single" w:sz="4" w:space="0" w:color="000000"/>' % side)
    tbl.append('</w:tblBorders><w:tblLayout w:type="fixed"/>'
               '<w:tblCellMar><w:left w:w="108" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>'
               '</w:tblPr><w:tblGrid><w:gridCol w:w="%d"/><w:gridCol w:w="%d"/><w:gridCol w:w="%d"/></w:tblGrid>'
               % (W_NUM, W_IMG, W_NOTE))
    tbl.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>%s%s%s</w:tr>' % (
        _cell(W_NUM, _par("№", True, 28, "center"), valign="center"),
        _cell(W_IMG, _par("Elektron matndagi matn", True, 28, "center"), valign="center"),
        _cell(W_NOTE, _par("Izoh", True, 28, "center"), valign="center")))
    media, rels = [], []
    n = 0
    num_p = ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr><w:jc w:val="center"/>'
             '</w:pPr></w:p>')
    note_p = ('<w:p><w:pPr><w:ind w:firstLine="465"/><w:jc w:val="both"/><w:rPr><w:sz w:val="24"/>'
              '<w:szCs w:val="24"/></w:rPr></w:pPr></w:p>')
    for lang, rows in sections:
        tbl.append('<w:tr>%s</w:tr>' % _cell(W_NUM + W_IMG + W_NOTE,
                                             _par(SECTION_TITLES[lang], True, 28, "center"), span=3))
        for row in rows:
            pics = []
            for data, w, h, wcm in row["imgs"]:
                n += 1
                rid = "rId%d" % (n + 10)
                name = "rasm%d.png" % n
                media.append((name, data))
                rels.append('<Relationship Id="%s" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                            'relationships/image" Target="media/%s"/>' % (rid, name))
                pics.append('<w:p><w:pPr><w:jc w:val="left"/></w:pPr>%s</w:p>' % _drawing(rid, n, w, h, wcm))
            tbl.append('<w:tr>%s%s%s</w:tr>' % (_cell(W_NUM, num_p), _cell(W_IMG, "".join(pics)),
                                                _cell(W_NOTE, note_p)))
    tbl.append('</w:tbl>')
    body.append("".join(tbl))
    body.append(_par())
    body.append(_par())
    roles = (("rais", "Ilmiy kengash raisi:"), ("kotib", "Ilmiy kotib:"),
             ("rahbar", "Ilmiy rahbar:"), ("talabgor", "Talabgor:"))
    sig_ppr = ('<w:spacing w:line="276" w:lineRule="auto"/><w:tabs><w:tab w:val="left" w:pos="10206"/></w:tabs>'
               '<w:ind w:left="2977"/>')
    for i, (key, label) in enumerate(roles):
        name = (signers.get(key) or "").strip()
        runs = _run(label, True, 28) + '<w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:tab/></w:r>' + _run(name, True, 28)
        body.append('<w:p><w:pPr>%s<w:jc w:val="left"/></w:pPr>%s</w:p>' % (sig_ppr, runs))
        if i < len(roles) - 1:
            body.append('<w:p><w:pPr>%s</w:pPr></w:p>' % sig_ppr)
    sect = ('<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
            '<w:pgMar w:top="1701" w:right="1134" w:bottom="850" w:left="1134" w:header="708" w:footer="708" '
            'w:gutter="0"/></w:sectPr>')
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document %s><w:body>%s%s</w:body>'
                '</w:document>') % (_NS, "".join(body), sect)
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles %s><w:docDefaults><w:rPrDefault><w:rPr>'
              '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" '
              'w:cs="Times New Roman"/><w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="uz-Latn-UZ"/></w:rPr>'
              '</w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
              '</w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
              '<w:name w:val="Normal"/><w:qFormat/></w:style></w:styles>') % _NS
    numbering = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering %s>'
                 '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0">'
                 '<w:start w:val="1"/><w:numFmt w:val="decimal"/><w:suff w:val="nothing"/><w:lvlText w:val="%%1."/>'
                 '<w:lvlJc w:val="center"/><w:pPr><w:ind w:left="0" w:firstLine="0"/></w:pPr>'
                 '<w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:lvl></w:abstractNum>'
                 '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>') % _NS
    settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings %s><w:compat>'
                '<w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" '
                'w:val="15"/></w:compat></w:settings>') % _NS
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
          'wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/'
          'vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" '
          'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
          '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.'
          'wordprocessingml.settings+xml"/></Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                 'officeDocument" Target="word/document.xml"/></Relationships>')
    base = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="%sstyles" Target="styles.xml"/>'
                '<Relationship Id="rId2" Type="%snumbering" Target="numbering.xml"/>'
                '<Relationship Id="rId3" Type="%ssettings" Target="settings.xml"/>%s</Relationships>'
                ) % (base, base, base, "".join(rels))
    tmp = out_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/numbering.xml", numbering)
        z.writestr("word/settings.xml", settings)
        for name, data in media:
            z.writestr(zipfile.ZipInfo("word/media/" + name, date_time=time.localtime()[:6]), data,
                       compress_type=zipfile.ZIP_STORED)
    os.replace(tmp, out_path)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    out = args[0]
    inp = dict(a.split("=", 1) for a in args[1:])
    r = build(inp, out, progress=lambda d, t, m: None)
    print(r)
