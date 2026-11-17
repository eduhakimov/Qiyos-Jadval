# -*- coding: utf-8 -*-
"""Qiyos Jadval — interfeys (PySide6)."""
import json
import os
import re
import sys
import threading

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QStandardPaths, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QFont, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QFileDialog, QPlainTextEdit, QLineEdit, QProgressBar, QCheckBox,
                               QComboBox, QMessageBox, QButtonGroup, QSizePolicy, QGraphicsDropShadowEffect)

import core

APP_NAME = "Qiyos Jadval"
ACCENT = "#4F46E5"
QUALITY = (("Tez (130 dpi)", 130), ("Standart (170 dpi)", 170), ("Yuqori (220 dpi)", 220))
TAGS = {"uz": "UZ", "ru": "RU", "en": "EN", "si": "SI"}
TAG_COLORS = {"uz": "#2563EB", "ru": "#DC2626", "en": "#059669", "si": "#D97706"}
KIND_NAMES = {"plag": "antiplagiat hisoboti", "si": "SI detektori hisoboti"}

QSS = """
* { font-family: 'Segoe UI', 'Inter', 'Arial'; font-size: 10pt; color: #1F2937; }
QWidget#root { background: #F3F4F8; }
QLabel#h1 { font-size: 17pt; font-weight: 700; color: #111827; }
QLabel#sub { color: #6B7280; }
QLabel#sec { font-size: 10.5pt; font-weight: 700; color: #111827; }
QLabel#hint { color: #6B7280; font-size: 9pt; }
QFrame#card { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; }
QFrame#slot { background: #FFFFFF; border: 1.5px dashed #CBD5E1; border-radius: 10px; }
QFrame#slot[state="filled"] { border: 1.5px solid #C7D2FE; background: #FAFAFF; }
QFrame#slot[state="need"] { border: 1.5px dashed #F59E0B; background: #FFFBEB; }
QFrame#slot[state="hover"] { border: 2px solid #4F46E5; background: #EEF2FF; }
QLabel#fname { font-weight: 600; color: #111827; }
QLabel#meta { color: #6B7280; font-size: 9pt; }
QLabel#warn { color: #B45309; font-size: 9pt; }
QLabel#req { background: #FEF3C7; color: #92400E; border-radius: 8px; padding: 1px 8px; font-size: 8.5pt; font-weight: 600; }
QLabel#opt { background: #EEF2F7; color: #64748B; border-radius: 8px; padding: 1px 8px; font-size: 8.5pt; }
QPushButton { background: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 8px; padding: 6px 12px; }
QPushButton:hover { background: #F3F4F6; }
QPushButton:disabled { color: #9CA3AF; background: #F3F4F6; }
QPushButton#primary { background: #4F46E5; color: white; border: none; font-size: 11.5pt; font-weight: 700; padding: 11px 26px; border-radius: 10px; }
QPushButton#primary:hover { background: #4338CA; }
QPushButton#primary:disabled { background: #A5B4FC; color: #EEF2FF; }
QPushButton#stop { background: #FEE2E2; color: #B91C1C; border: none; font-weight: 600; padding: 11px 20px; border-radius: 10px; }
QPushButton#x { border: none; background: transparent; color: #9CA3AF; font-size: 12pt; padding: 2px 6px; }
QPushButton#x:hover { color: #DC2626; background: #FEE2E2; border-radius: 6px; }
QPushButton#seg { border: 1px solid #D1D5DB; border-radius: 0px; padding: 6px 16px; background: #FFFFFF; }
QPushButton#seg[pos="first"] { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#seg[pos="last"] { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
QPushButton#seg:checked { background: #4F46E5; color: white; border-color: #4F46E5; font-weight: 600; }
QPushButton#link { border: none; background: transparent; color: #4F46E5; font-weight: 600; padding: 4px 6px; }
QPushButton#link:hover { text-decoration: underline; }
QLineEdit, QPlainTextEdit, QComboBox { background: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 8px; padding: 6px 8px; selection-background-color: #C7D2FE; selection-color: #111827; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1.5px solid #4F46E5; }
QComboBox::drop-down { border: none; width: 22px; }
QProgressBar { background: #E5E7EB; border: none; border-radius: 5px; height: 10px; text-align: center; }
QProgressBar::chunk { background: #4F46E5; border-radius: 5px; }
QLabel#status { color: #374151; }
QLabel#done { color: #047857; font-weight: 700; font-size: 10.5pt; }
QLabel#err { color: #B91C1C; font-weight: 600; }
QCheckBox { spacing: 8px; }
"""


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def settings_path():
    d = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "sozlamalar.json")


def load_settings():
    try:
        with open(settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa
        return {}


def save_settings(d):
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:  # noqa
        pass


def pdf_paths(mime):
    out = []
    if mime.hasUrls():
        for u in mime.urls():
            p = u.toLocalFile()
            if p and p.lower().endswith(".pdf") and os.path.isfile(p):
                out.append(p)
    return out


class Slot(QFrame):
    """Bitta til uchun PDF qabul qiluvchi katak."""
    changed = Signal(str)
    dropped = Signal(str, list)

    def __init__(self, lang):
        super().__init__()
        self.lang = lang
        self.path = ""
        self.info = None
        self.required = False
        self.setObjectName("slot")
        self.setAcceptDrops(True)
        self.setMinimumHeight(74)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 10, 10)
        lay.setSpacing(12)
        tag = QLabel(TAGS[lang])
        tag.setFixedSize(44, 44)
        tag.setAlignment(Qt.AlignCenter)
        tag.setStyleSheet("background:%s; color:white; border-radius:10px; font-weight:700; font-size:11pt;"
                          % TAG_COLORS[lang])
        lay.addWidget(tag)
        mid = QVBoxLayout()
        mid.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = QLabel(core.LANG_NAMES[lang])
        self.title.setObjectName("fname")
        self.badge = QLabel("Ixtiyoriy")
        self.badge.setObjectName("opt")
        top.addWidget(self.title)
        top.addWidget(self.badge)
        top.addStretch(1)
        mid.addLayout(top)
        self.meta = QLabel()
        self.meta.setObjectName("meta")
        self.meta.setTextInteractionFlags(Qt.NoTextInteraction)
        mid.addWidget(self.meta)
        lay.addLayout(mid, 1)
        self.btn = QPushButton("Tanlash")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.choose)
        lay.addWidget(self.btn)
        self.x = QPushButton("✕")
        self.x.setObjectName("x")
        self.x.setToolTip("Faylni olib tashlash")
        self.x.setCursor(Qt.PointingHandCursor)
        self.x.clicked.connect(lambda: self.set_file(""))
        lay.addWidget(self.x)
        self.refresh()

    def set_required(self, req):
        self.required = req
        self.refresh()

    def choose(self):
        start = os.path.dirname(self.path) if self.path else load_settings().get("last_dir", "")
        p, _ = QFileDialog.getOpenFileName(self, core.LANG_NAMES[self.lang] + " — PDF hisobotni tanlang", start,
                                           "PDF hujjat (*.pdf)")
        if p:
            self.set_file(p)

    def set_file(self, path, info=None):
        self.path = path
        self.info = (info or core.inspect_pdf(path)) if path else None
        self.refresh()
        self.changed.emit(self.lang)

    def refresh(self):
        self.badge.setText("Majburiy" if self.required else "Ixtiyoriy")
        self.badge.setObjectName("req" if self.required else "opt")
        self.x.setVisible(bool(self.path))
        self.btn.setText("Almashtirish" if self.path else "Tanlash")
        if self.path:
            i = self.info or {}
            name = os.path.basename(self.path)
            self.title.setText(name if len(name) < 46 else name[:30] + "…" + name[-13:])
            self.title.setToolTip(self.path)
            if i.get("error"):
                self.meta.setText("⚠ " + i["error"])
                self.meta.setObjectName("warn")
            else:
                parts = ["%d sahifa" % i.get("pages", 0)]
                warn = ""
                if i.get("kind") is None:
                    warn = "belgilangan parchalar topilmadi — to‘g‘ri hisobotmi?"
                elif i.get("lang") and i["lang"] != self.lang:
                    warn = "bu fayl “%s” hisobotiga o‘xshaydi" % core.LANG_NAMES[i["lang"]]
                else:
                    parts.append(KIND_NAMES.get(i.get("kind"), ""))
                if warn:
                    self.meta.setText("⚠ " + parts[0] + " · " + warn)
                    self.meta.setObjectName("warn")
                else:
                    self.meta.setText(" · ".join(parts))
                    self.meta.setObjectName("meta")
            self.setProperty("state", "filled")
        else:
            self.title.setText(core.LANG_NAMES[self.lang])
            self.title.setToolTip("")
            self.meta.setText("PDF faylni shu yerga tashlang yoki “Tanlash”ni bosing")
            self.meta.setObjectName("meta")
            self.setProperty("state", "need" if self.required else "")
        for w in (self, self.badge, self.meta):
            w.style().unpolish(w)
            w.style().polish(w)

    # sudrab tashlash
    def dragEnterEvent(self, e):
        if pdf_paths(e.mimeData()):
            e.acceptProposedAction()
            self._old = self.property("state")
            self.setProperty("state", "hover")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, e):
        self.refresh()

    def dropEvent(self, e):
        ps = pdf_paths(e.mimeData())
        e.acceptProposedAction()
        if len(ps) == 1:
            self.set_file(ps[0])
        else:
            self.refresh()
            self.dropped.emit(self.lang, ps)


class Worker(QThread):
    progress = Signal(int, int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, inputs, out, title, signers, opts):
        super().__init__()
        self.args = (inputs, out, title, signers, opts)
        self.cancel = threading.Event()

    def run(self):
        inputs, out, title, signers, opts = self.args
        try:
            r = core.build(inputs, out, title, signers, opts,
                           progress=lambda d, t, m: self.progress.emit(d, t, m), cancel=self.cancel)
            self.finished_ok.emit(r)
        except core.Cancelled:
            self.failed.emit("")
        except PermissionError:
            self.failed.emit("Faylga yozib bo‘lmadi. Hujjat Word dasturida ochiq bo‘lsa, uni yoping va qayta urinib ko‘ring.")
        except Exception as e:  # noqa
            self.failed.emit(str(e) or e.__class__.__name__)


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle(APP_NAME)
        self.setAcceptDrops(True)
        self.cfg = load_settings()
        self.worker = None
        self.title_auto = True
        self.out_auto = True
        self.last_result = None
        ico = resource("icon.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        head = QHBoxLayout()
        tl = QVBoxLayout()
        tl.setSpacing(0)
        h1 = QLabel(APP_NAME)
        h1.setObjectName("h1")
        sub = QLabel("Antiplagiat va SI hisobotlaridagi belgilangan parchalarni qirqib, Word jadvaliga joylaydi")
        sub.setObjectName("sub")
        tl.addWidget(h1)
        tl.addWidget(sub)
        head.addLayout(tl, 1)
        ver = QLabel("v" + core.VERSION)
        ver.setObjectName("hint")
        head.addWidget(ver, 0, Qt.AlignTop)
        root.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(14)
        root.addLayout(cols, 1)

        # ---- chap: fayllar
        left = self.card()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 14, 16, 14)
        ll.setSpacing(9)
        row = QHBoxLayout()
        s1 = QLabel("1. Dissertatsiya tili")
        s1.setObjectName("sec")
        row.addWidget(s1)
        row.addStretch(1)
        self.seg = QButtonGroup(self)
        seg_lay = QHBoxLayout()
        seg_lay.setSpacing(0)
        for i, (code, text) in enumerate((("uz", "O‘zbek"), ("ru", "Rus"), ("en", "Ingliz"))):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("pos", "first" if i == 0 else ("last" if i == 2 else "mid"))
            b.setProperty("code", code)
            self.seg.addButton(b, i)
            seg_lay.addWidget(b)
        row.addLayout(seg_lay)
        ll.addLayout(row)
        hint = QLabel("Shu tildagi hisobot majburiy, qolganlari ixtiyoriy. Jadval tartibi: UZ → RU → EN → SI.")
        hint.setObjectName("hint")
        ll.addWidget(hint)
        s2 = QLabel("2. PDF hisobotlar")
        s2.setObjectName("sec")
        ll.addSpacing(4)
        ll.addWidget(s2)
        self.slots = {}
        for lang in core.LANGS:
            s = Slot(lang)
            s.changed.connect(self.on_slot_changed)
            s.dropped.connect(lambda lang, ps: self.add_files(ps))
            self.slots[lang] = s
            ll.addWidget(s)
        tip = QLabel("Maslahat: bir nechta PDF faylni birdaniga oynaga tashlasangiz, dastur tilini o‘zi aniqlab joylaydi.")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        ll.addWidget(tip)
        ll.addStretch(1)
        cols.addWidget(left, 11)

        # ---- o'ng: hujjat sozlamalari
        right = self.card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 14, 16, 14)
        rl.setSpacing(8)
        s3 = QLabel("3. Hujjat sarlavhasi")
        s3.setObjectName("sec")
        rl.addWidget(s3)
        self.title_edit = QPlainTextEdit()
        self.title_edit.setPlaceholderText("Sarlavha matni (PDF tanlanganda avtomatik to‘ldiriladi, tahrirlash mumkin)")
        self.title_edit.setMinimumHeight(108)
        self.title_edit.textChanged.connect(self.on_title_edited)
        rl.addWidget(self.title_edit, 1)
        s4 = QLabel("Imzolovchilar")
        s4.setObjectName("sec")
        rl.addSpacing(2)
        rl.addWidget(s4)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.signers = {}
        for i, (key, label, ph) in enumerate((("rais", "Ilmiy kengash raisi", "I.F.Familiya"),
                                              ("kotib", "Ilmiy kotib", "I.F.Familiya"),
                                              ("rahbar", "Ilmiy rahbar", "I.F.Familiya"),
                                              ("talabgor", "Talabgor", "I.F.Familiya"))):
            grid.addWidget(QLabel(label), i, 0)
            e = QLineEdit(self.cfg.get("signers", {}).get(key, "") if key in ("rais", "kotib") else "")
            e.setPlaceholderText(ph)
            self.signers[key] = e
            grid.addWidget(e, i, 1)
        rl.addLayout(grid)
        s5 = QLabel("Rasm sozlamalari")
        s5.setObjectName("sec")
        rl.addSpacing(2)
        rl.addWidget(s5)
        orow = QHBoxLayout()
        orow.addWidget(QLabel("Sifat"))
        self.quality = QComboBox()
        for t, v in QUALITY:
            self.quality.addItem(t, v)
        self.quality.setCurrentIndex(max(0, [v for _, v in QUALITY].index(self.cfg.get("dpi", 170))
                                         if self.cfg.get("dpi", 170) in [v for _, v in QUALITY] else 1))
        orow.addWidget(self.quality, 1)
        rl.addLayout(orow)
        self.fade = QCheckBox("Parchaga tegishli bo‘lmagan qo‘shni matnni xiralashtirish")
        self.fade.setChecked(self.cfg.get("fade", True))
        self.fade.setToolTip("Yoqilsa, har bir rasmda faqat shu satrga tegishli parcha aniq ko‘rinadi,\n"
                             "birinchi va oxirgi qatordagi begona matn oqartiriladi.")
        rl.addWidget(self.fade)
        cols.addWidget(right, 9)

        # ---- past: saqlash va ishga tushirish
        bottom = self.card()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(10)
        prow = QHBoxLayout()
        lab = QLabel("Saqlash joyi")
        lab.setObjectName("sec")
        prow.addWidget(lab)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Natija Word hujjati (.docx)")
        self.out_edit.textEdited.connect(lambda: setattr(self, "out_auto", False))
        prow.addWidget(self.out_edit, 1)
        b = QPushButton("…")
        b.setFixedWidth(40)
        b.clicked.connect(self.choose_out)
        prow.addWidget(b)
        bl.addLayout(prow)
        run = QHBoxLayout()
        run.setSpacing(12)
        st = QVBoxLayout()
        st.setSpacing(6)
        self.status = QLabel("Majburiy PDF hisobotni tanlang")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.bar.setValue(0)
        st.addWidget(self.status)
        st.addWidget(self.bar)
        run.addLayout(st, 1)
        self.open_btn = QPushButton("Hujjatni ochish")
        self.open_btn.setObjectName("link")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(self.open_doc)
        self.folder_btn = QPushButton("Papkani ochish")
        self.folder_btn.setObjectName("link")
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.clicked.connect(self.open_folder)
        self.open_btn.hide()
        self.folder_btn.hide()
        run.addWidget(self.open_btn)
        run.addWidget(self.folder_btn)
        self.stop_btn = QPushButton("To‘xtatish")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.hide()
        run.addWidget(self.stop_btn)
        self.go = QPushButton("Jadvalni yaratish")
        self.go.setObjectName("primary")
        self.go.setCursor(Qt.PointingHandCursor)
        self.go.clicked.connect(self.start)
        run.addWidget(self.go)
        bl.addLayout(run)
        root.addWidget(bottom)

        self.seg.idClicked.connect(self.on_lang)
        idx = {"uz": 0, "ru": 1, "en": 2}.get(self.cfg.get("main_lang", "uz"), 0)
        self.seg.button(idx).setChecked(True)
        self.on_lang(idx)
        self.resize(1060, 720)
        self.setMinimumSize(940, 660)
        QTimer.singleShot(300, lambda: threading.Thread(target=core.warm_up, daemon=True).start())

    def card(self):
        f = QFrame()
        f.setObjectName("card")
        sh = QGraphicsDropShadowEffect(f)
        sh.setBlurRadius(18)
        sh.setOffset(0, 2)
        sh.setColor(QColor(15, 23, 42, 22))
        f.setGraphicsEffect(sh)
        return f

    # ------------------------------------------------------------------ holat
    def main_lang(self):
        return self.seg.checkedButton().property("code")

    def on_lang(self, _id):
        ml = self.main_lang()
        for lang, s in self.slots.items():
            s.set_required(lang == ml)
        self.update_state()

    def on_title_edited(self):
        if not getattr(self, "_setting_title", False):
            self.title_auto = not self.title_edit.toPlainText().strip()

    def best_info(self):
        order = [self.main_lang(), "uz", "si", "ru", "en"]
        for lang in order:
            s = self.slots[lang]
            if s.path and s.info and s.info.get("name") and s.info.get("topic"):
                return s.info
        return None

    def on_slot_changed(self, lang):
        s = self.slots[lang]
        if s.path:
            self.cfg["last_dir"] = os.path.dirname(s.path)
        info = self.best_info()
        if self.title_auto:
            self._setting_title = True
            self.title_edit.setPlainText(core.default_title(info) if info else "")
            self._setting_title = False
            self.title_auto = True
        if info and not self.signers["talabgor"].text().strip():
            self.signers["talabgor"].setText(self.short_name(info["name"]))
        if self.out_auto:
            first = next((self.slots[l].path for l in [self.main_lang()] + list(core.LANGS) if self.slots[l].path), "")
            if first:
                who = " ".join((info["name"].split()[:2])) if info else os.path.splitext(os.path.basename(first))[0]
                who = re.sub(r'[\\/:*?"<>|_]+', " ", who).strip()
                self.out_edit.setText(os.path.join(os.path.dirname(first), "%s Qiyosiy jadval.docx" % who))
            else:
                self.out_edit.setText("")
        self.hide_result()
        self.update_state()

    @staticmethod
    def short_name(full):
        p = full.split()
        if len(p) >= 3:
            return "%s.%s.%s" % (p[1][0], p[2][0], p[0])
        if len(p) == 2:
            return "%s.%s" % (p[1][0], p[0])
        return full

    def update_state(self):
        if self.worker:
            return
        ml = self.main_lang()
        ok = bool(self.slots[ml].path) and not (self.slots[ml].info or {}).get("error")
        self.go.setEnabled(ok)
        if not self.last_result:
            n = sum(1 for s in self.slots.values() if s.path)
            if ok:
                self.status.setText("Tayyor: %d ta hisobot tanlandi. “Jadvalni yaratish”ni bosing." % n)
            else:
                self.status.setText("Majburiy hisobotni tanlang: %s" % core.LANG_NAMES[ml])
            self.status.setObjectName("status")
            self.repolish(self.status)

    def repolish(self, w):
        w.style().unpolish(w)
        w.style().polish(w)

    # ------------------------------------------------------------- fayl qo'shish
    def add_files(self, paths):
        """Bir nechta PDF: tilini aniqlab mos katakka joylash."""
        leftover = []
        for p in paths:
            info = core.inspect_pdf(p)
            lang = info.get("lang")
            if lang and not self.slots[lang].path:
                self.slots[lang].set_file(p, info)
            else:
                leftover.append((p, info))
        for p, info in leftover:
            lang = info.get("lang")
            target = None
            if lang and len(paths) == 1:
                target = lang                      # bitta fayl: o'z katagini almashtiradi
            else:
                target = next((l for l in [self.main_lang()] + list(core.LANGS) if not self.slots[l].path), None)
            if target:
                self.slots[target].set_file(p, info)

    def dragEnterEvent(self, e):
        if pdf_paths(e.mimeData()) and not self.worker:
            e.acceptProposedAction()

    def dropEvent(self, e):
        ps = pdf_paths(e.mimeData())
        if ps and not self.worker:
            e.acceptProposedAction()
            self.add_files(ps)

    def choose_out(self):
        start = self.out_edit.text().strip() or self.cfg.get("last_dir", "")
        p, _ = QFileDialog.getSaveFileName(self, "Natijani saqlash", start, "Word hujjat (*.docx)")
        if p:
            if not p.lower().endswith(".docx"):
                p += ".docx"
            self.out_edit.setText(p)
            self.out_auto = False

    # ------------------------------------------------------------------- ish
    def start(self):
        inputs = {l: s.path for l, s in self.slots.items() if s.path}
        out = self.out_edit.text().strip()
        if not out:
            self.choose_out()
            out = self.out_edit.text().strip()
            if not out:
                return
        if not out.lower().endswith(".docx"):
            out += ".docx"
            self.out_edit.setText(out)
        d = os.path.dirname(out)
        if d and not os.path.isdir(d):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:  # noqa
                QMessageBox.warning(self, APP_NAME, "Saqlash papkasi topilmadi:\n" + d)
                return
        if os.path.exists(out) and not self.out_auto_confirmed(out):
            return
        signers = {k: e.text().strip() for k, e in self.signers.items()}
        opts = {"dpi": self.quality.currentData(), "fade": self.fade.isChecked()}
        self.cfg.update({"main_lang": self.main_lang(), "dpi": opts["dpi"], "fade": opts["fade"],
                         "signers": {"rais": signers["rais"], "kotib": signers["kotib"]}})
        save_settings(self.cfg)
        self.hide_result()
        self.set_busy(True)
        self.bar.setRange(0, 0)
        self.status.setText("Tahlil qilinmoqda…")
        self.worker = Worker(inputs, out, self.title_edit.toPlainText(), signers, opts)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def out_auto_confirmed(self, out):
        r = QMessageBox.question(self, APP_NAME, "Bu nomli hujjat allaqachon bor:\n%s\n\nUstidan yozilsinmi?"
                                 % os.path.basename(out), QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        return r == QMessageBox.Yes

    def set_busy(self, busy):
        self.go.setVisible(not busy)
        self.stop_btn.setVisible(busy)
        self.stop_btn.setEnabled(True)
        for s in self.slots.values():
            s.setEnabled(not busy)
        for b in self.seg.buttons():
            b.setEnabled(not busy)

    def on_progress(self, done, total, msg):
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(done)
        self.status.setText("%s  %d / %d sahifa" % (msg, done, total))

    def stop(self):
        if self.worker:
            self.worker.cancel.set()
            self.stop_btn.setEnabled(False)
            self.status.setText("To‘xtatilmoqda…")

    def finish(self):
        if self.worker:
            self.worker.wait(3000)
        self.worker = None
        self.set_busy(False)
        self.bar.setRange(0, 100)

    def on_done(self, r):
        self.finish()
        self.last_result = r
        self.bar.setValue(100)
        parts = ["%s: %d" % (TAGS[l], r["counts"][l]) for l in core.LANGS if l in r["counts"]]
        self.status.setText("✓ Tayyor — %d ta satr (%s) · %.1f soniya" % (r["total"], ", ".join(parts), r["seconds"]))
        self.status.setObjectName("done")
        self.repolish(self.status)
        self.open_btn.show()
        self.folder_btn.show()
        self.go.setEnabled(True)

    def on_failed(self, msg):
        self.finish()
        self.bar.setValue(0)
        self.last_result = None
        if msg:
            self.status.setText("Xato: " + msg)
            self.status.setObjectName("err")
            self.repolish(self.status)
        else:
            self.update_state()
        self.go.setEnabled(True)

    def hide_result(self):
        self.last_result = None
        self.open_btn.hide()
        self.folder_btn.hide()
        self.bar.setValue(0)
        self.status.setObjectName("status")
        self.repolish(self.status)

    def open_doc(self):
        if self.last_result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_result["path"]))

    def open_folder(self):
        if self.last_result:
            p = self.last_result["path"]
            if sys.platform == "win32":
                import subprocess
                subprocess.Popen('explorer /select,"%s"' % os.path.normpath(p))
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(p)))

    def closeEvent(self, e):
        if self.worker:
            self.worker.cancel.set()
            self.worker.wait(2000)
        core.reset_pool()
        e.accept()


def run(argv=None):
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv or sys.argv)
    app.setApplicationName("QiyosJadval")
    app.setOrganizationName("QiyosJadval")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    ico = resource("icon.ico")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    w = Main()
    files = [a for a in (argv or sys.argv)[1:] if a.lower().endswith(".pdf") and os.path.isfile(a)]
    w.show()
    if files:
        w.add_files(files)
    return app, w
