# -*- coding: utf-8 -*-
"""Qiyos Jadval — ishga tushirish nuqtasi."""
import multiprocessing
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def _log_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "QiyosJadval")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:  # noqa
        d = HERE
    return os.path.join(d, "xato.log")


def _fatal(text):
    """Dastur ochilmay qolsa, sababini faylga yozadi va oynada ko'rsatadi."""
    path = _log_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:  # noqa
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "Dasturni ishga tushirishda xato yuz berdi.\n\n%s\n\nTo‘liq ma’lumot: %s"
                % (text.strip().splitlines()[-1][:300], path), "Qiyos Jadval", 0x10)
        except Exception:  # noqa
            pass


def main():
    # Buyruq satri rejimi:  main.py --cli natija.docx uz=Uz.pdf ru=Ru.pdf en=En.pdf si=Si.pdf
    if len(sys.argv) > 2 and sys.argv[1] == "--cli":
        import core
        out = sys.argv[2]
        inputs = dict(a.split("=", 1) for a in sys.argv[3:] if "=" in a)
        info = next((core.inspect_pdf(p) for p in inputs.values()), {})
        r = core.build(inputs, out, title=core.default_title(info))
        try:
            print(r)
        except Exception:  # noqa
            pass
        return 0
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QiyosJadval.App")
        except Exception:  # noqa
            pass
    from ui import run
    app, w = run()
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        code = main()
    except SystemExit:
        raise
    except Exception:  # noqa
        _fatal(traceback.format_exc())
        code = 1
    sys.exit(code)
