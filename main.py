"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IASTRAL — Sauvegarde & Migration de données Windows                         ║
║  Compatible Python 3.7+  |  Lance avec : pythonw.exe main.py                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Dépendances :
    pip install customtkinter pillow matplotlib fpdf2 psutil
"""

# ─── COMPATIBILITÉ : from __future__ doit être la 1re instruction ───────────
from __future__ import annotations

import sys
import os

# ─── VÉRIFICATION VERSION PYTHON (3.7 minimum) ───────────────────────────────
if sys.version_info < (3, 7):
    try:
        import tkinter as _tk
        _r = _tk.Tk()
        _r.title("IASTRAL - Erreur Python")
        _r.geometry("500x200")
        _tk.Label(_r, text="Python 3.7 minimum requis.\nVersion detectee : %d.%d" %
                  (sys.version_info.major, sys.version_info.minor),
                  font=("Segoe UI", 13), pady=40).pack()
        _tk.Button(_r, text="Fermer", command=_r.destroy,
                   font=("Segoe UI", 11), padx=20, pady=6).pack()
        _r.mainloop()
    except Exception:
        pass
    sys.exit(1)

# ─── IMPORTS STDLIB ──────────────────────────────────────────────────────────
import hashlib
import json
import shutil
import string
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

# ─── IMPORTS TIERS OBLIGATOIRES ──────────────────────────────────────────────
try:
    import customtkinter as ctk
    from PIL import Image
except ImportError as _e:
    try:
        import tkinter as _tk2
        _r2 = _tk2.Tk()
        _r2.title("IASTRAL - Dépendances manquantes")
        _r2.geometry("560x200")
        _tk2.Label(_r2, text="Modules manquants : %s\n\nInstallez avec :\npip install customtkinter pillow matplotlib fpdf2 psutil" % _e,
                   font=("Segoe UI", 11), pady=30, justify="left").pack()
        _tk2.Button(_r2, text="Fermer", command=_r2.destroy,
                    font=("Segoe UI", 11), padx=20, pady=6).pack()
        _r2.mainloop()
    except Exception:
        pass
    sys.exit(1)

# ─── PATCH CTk 5.2.2 / Python 3.14 ──────────────────────────────────────────
# Sur Python 3.14, tkinter.Tk.__init__ modifie le comportement de self._w :
# après destroy() d'une instance Tk temporaire, le compteur interne Tcl est
# perturbé et la prochaine fenêtre reçoit "{}" comme chemin au lieu de ".".
# La vraie cause : CTkAppearanceModeBaseClass.add() appelle
# get_tk_root_of_widget() qui boucle sur current_widget.master — sur Python
# 3.14 master peut valoir la chaîne "{}" → boucle infinie ou crash.
# FIX : patcher get_tk_root_of_widget pour sortir proprement sur str invalide.
def _p3_14_get_tk_root(widget):
    import tkinter as _tk
    seen, cur = set(), widget
    while True:
        if isinstance(cur, _tk.Tk):
            return cur
        m = getattr(cur, "master", None)
        if m is None or isinstance(m, str) or id(m) in seen:
            return widget
        seen.add(id(cur))
        cur = m
try:
    from customtkinter.windows.widgets.appearance_mode.appearance_mode_tracker import (
        AppearanceModeTracker as _AMT)
    _AMT.get_tk_root_of_widget = staticmethod(_p3_14_get_tk_root)
except Exception:
    pass
# ─────────────────────────────────────────────────────────────────────────────

# ─── IMPORTS OPTIONNELS ──────────────────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from fpdf import FPDF, XPos, YPos
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False


# =============================================================================
#  PALETTES (Obsidian — zéro bleu)
# =============================================================================

PALETTE_DARK = {
    "BG":        "#0d0d0d",
    "CARD":      "#181818",
    "CARD2":     "#222222",
    "BORDER":    "#2e2e2e",
    "ACCENT":    "#56a370",
    "ACCENT2":   "#3d7a52",
    "TEAL":      "#4a9e6e",
    "ORANGE":    "#c07030",
    "RED":       "#b03838",
    "RED2":      "#7a2828",
    "TEXT":      "#d2d2d2",
    "MUTED":     "#646464",
    "SUCCESS":   "#56a370",
    "WARN":      "#c0982a",
    "HEADER_BG": "#101010",
}

PALETTE_LIGHT = {
    "BG":        "#f2f2f2",
    "CARD":      "#fafafa",
    "CARD2":     "#e8e8e8",
    "BORDER":    "#cccccc",
    "ACCENT":    "#3d7a52",
    "ACCENT2":   "#2a5c3c",
    "TEAL":      "#3a7050",
    "ORANGE":    "#9a5020",
    "RED":       "#882828",
    "RED2":      "#5e1818",
    "TEXT":      "#1a1a1a",
    "MUTED":     "#606060",
    "SUCCESS":   "#3d7a52",
    "WARN":      "#886010",
    "HEADER_BG": "#e0e0e0",
}


def _auto_theme():
    # type: () -> str
    return "light" if 7 <= datetime.now().hour < 20 else "dark"


# =============================================================================
#  UTILITAIRES
# =============================================================================

def _safe_str(text):
    # type: (str) -> str
    """Remplace les caractères Unicode problématiques pour fpdf/latin-1."""
    subs = {
        "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2026": "...",
    }
    for old, new in subs.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def format_size(size_bytes):
    # type: (int) -> str
    gb = size_bytes / (1024 ** 3)
    if gb >= 1:
        return "{:.2f} Go".format(gb)
    mb = size_bytes / (1024 ** 2)
    if mb >= 1:
        return "{:.2f} Mo".format(mb)
    kb = size_bytes / 1024
    return "{:.1f} Ko".format(kb)


def sha256_file(path, chunk=1 << 20):
    # type: (Path, int) -> str
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def verify_copy(src, dst):
    # type: (Path, Path) -> bool
    try:
        return sha256_file(src) == sha256_file(dst)
    except Exception:
        return False


def copy_with_retry(src, dst, log_cb=None, max_attempts=3, delay=5.0, verify=True):
    # type: (Path, Path, object, int, float, bool) -> bool
    dst.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            shutil.copy2(str(src), str(dst))
            if verify:
                ok = verify_copy(src, dst)
                if log_cb:
                    log_cb("{} {}".format("[HASH OK]" if ok else "[HASH FAIL]", src.name))
                if not ok:
                    return False
            return True
        except PermissionError as e:
            last_err = e
            if log_cb:
                log_cb("[RETRY {}/{}] Fichier verrouille, reessai dans {}s : {}".format(
                    attempt, max_attempts, delay, src.name))
            time.sleep(delay)
        except Exception as e:
            last_err = e
            break
    if log_cb:
        log_cb("[ERREUR] Abandon apres {} essais : {} - {}".format(
            max_attempts, src.name, last_err))
    return False


def scan_folder(path, cancel_check=None):
    # type: (Path, object) -> tuple
    fc = ts = 0
    if not path.exists():
        return 0, 0
    try:
        for root, _dirs, files in os.walk(str(path)):
            if cancel_check and cancel_check():
                return 0, 0
            fc += len(files)
            for f in files:
                try:
                    ts += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return fc, ts


def get_disk_usage(path):
    # type: (Path) -> tuple
    u = shutil.disk_usage(str(path))
    return u.total, u.used, u.free


def check_space(source_size, dest_path):
    # type: (int, Path) -> tuple
    try:
        _, _, free = get_disk_usage(dest_path)
        return free >= source_size, free
    except OSError:
        return False, 0


def detect_removable_drives():
    # type: () -> list
    drives = []
    if HAS_PSUTIL:
        for part in psutil.disk_partitions(all=False):
            removable = ("removable" in part.opts.lower() or
                         "usb" in part.opts.lower())
            if not removable and os.name == "nt":
                try:
                    import ctypes as _ct
                    removable = _ct.windll.kernel32.GetDriveTypeW(part.mountpoint) == 2
                except Exception:
                    pass
            if not removable:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
                drives.append({"letter": part.mountpoint,
                                "label":  part.device or part.mountpoint,
                                "free":   u.free, "total": u.total})
            except Exception:
                pass
        return drives
    # Fallback Windows sans psutil
    try:
        import ctypes as _ct2
        buf = _ct2.create_unicode_buffer(256)
        for ltr in string.ascii_uppercase:
            drv = "{}:\\".format(ltr)
            if _ct2.windll.kernel32.GetDriveTypeW(drv) != 2:
                continue
            try:
                _ct2.windll.kernel32.GetVolumeInformationW(
                    drv, buf, 256, None, None, None, None, 0)
                label = buf.value or "USB {}:".format(ltr)
                t, _, fr = get_disk_usage(Path(drv))
                drives.append({"letter": drv, "label": label,
                                "free": fr, "total": t})
            except Exception:
                pass
        return drives
    except Exception:
        pass
    # Fallback Linux/Mac
    for base in [Path("/media"), Path("/mnt"), Path("/run/media")]:
        if not base.exists():
            continue
        for entry in base.rglob("*"):
            if entry.is_mount():
                try:
                    t, _, fr = get_disk_usage(entry)
                    drives.append({"letter": str(entry), "label": entry.name,
                                   "free": fr, "total": t})
                except OSError:
                    pass
    return drives


def write_log_file(log_path, message):
    # type: (Path, str) -> None
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(log_path), "a", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(datetime.now().strftime("%H:%M:%S"), message))
    except OSError:
        pass


# =============================================================================
#  NAVIGATEURS
# =============================================================================

def get_browser_paths():
    # type: () -> dict
    home    = Path.home()
    appdata = Path(os.environ.get("APPDATA",      str(home / "AppData" / "Roaming")))
    local   = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))

    def _cr(base):
        return {
            "base": base,
            "bookmarks": [
                "Default/Bookmarks", "Default/Bookmarks.bak",
                "Profile */Bookmarks", "Profile */Bookmarks.bak",
            ],
            "passwords": [
                "Default/Login Data", "Default/Login Data For Account",
                "Profile */Login Data", "Profile */Login Data For Account",
                "Local State",
            ],
        }

    return {
        "Chrome":            _cr(local / "Google" / "Chrome" / "User Data"),
        "Edge":              _cr(local / "Microsoft" / "Edge" / "User Data"),
        "Brave":             _cr(local / "BraveSoftware" / "Brave-Browser" / "User Data"),
        "Vivaldi":           _cr(local / "Vivaldi" / "User Data"),
        "Firefox": {
            "base": appdata / "Mozilla" / "Firefox" / "Profiles",
            "bookmarks": ["*.default-release/places.sqlite", "*.default/places.sqlite"],
            "passwords": ["*.default-release/key4.db", "*.default-release/logins.json",
                          "*.default/key4.db", "*.default/logins.json"],
        },
        "Opera": {
            "base": appdata / "Opera Software" / "Opera Stable",
            "bookmarks": ["Bookmarks", "Bookmarks.bak"],
            "passwords": ["Login Data", "Local State"],
        },
        "Opera GX": {
            "base": appdata / "Opera Software" / "Opera GX Stable",
            "bookmarks": ["Bookmarks", "Bookmarks.bak"],
            "passwords": ["Login Data", "Local State"],
        },
        "Internet Explorer": {
            "base":      home / "Favorites",
            "bookmarks": ["."],
            "passwords": [],
        },
    }


def collect_browser_files(browser_name, browser_info, mode):
    # type: (str, dict, str) -> list
    base     = browser_info["base"]
    patterns = browser_info.get(mode, [])
    found, seen = [], set()

    def _add(p):
        if p not in seen:
            seen.add(p)
            found.append(p)

    if not base.exists():
        return found

    for pattern in patterns:
        if pattern == ".":
            _add(base)
        elif "*" in pattern:
            head = pattern.split("/", 1)[0]
            tail = pattern.split("/", 1)[1] if "/" in pattern else ""
            for d in sorted(base.glob(head)):
                c = d / tail if tail else d
                if c.exists():
                    _add(c)
        else:
            c = base / pattern
            if c.exists():
                _add(c)

    return found


# =============================================================================
#  RAPPORT PDF — design soigne (bandeau logo, badges, cartes stats, tableaux)
# =============================================================================

_PDF_ACCENT  = (86, 163, 112)    # vert IASTRAL (#56a370)
_PDF_ACCENT2 = (61, 122, 82)     # vert fonce   (#3d7a52)
_PDF_DARK    = (35, 35, 35)
_PDF_GRAY    = (110, 110, 110)
_PDF_LIGHT   = (242, 242, 242)
_PDF_LIGHT2  = (250, 250, 250)
_PDF_RED     = (176, 56, 56)
_PDF_RED_BG  = (250, 233, 233)
_PDF_ORANGE  = (192, 112, 48)
_PDF_WHITE   = (255, 255, 255)
_PDF_BORDER  = (220, 220, 220)


class _IastralPDF(FPDF):
    """PDF avec bandeau d'en-tete (logo + titre) et pied de page numerote."""

    def __init__(self, logo_path=None):
        super(_IastralPDF, self).__init__()
        self._logo_path = logo_path
        self._gen_date  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.set_auto_page_break(auto=True, margin=22)
        self.alias_nb_pages()

    def header(self):
        self.set_fill_color(*_PDF_ACCENT)
        self.rect(0, 0, 210, 20, style="F")

        if self._logo_path and Path(self._logo_path).exists():
            try:
                self.image(str(self._logo_path), x=8, y=3.5, h=13)
            except Exception:
                pass

        self.set_text_color(*_PDF_WHITE)
        self.set_xy(0, 4)
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 7, "IASTRAL", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_x(0)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, _safe_str("Rapport de Migration & Sauvegarde"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        self.set_y(26)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*_PDF_BORDER)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_PDF_GRAY)
        self.cell(95, 8, _safe_str("IASTRAL - genere le {}".format(self._gen_date)),
                  border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, align="L")
        self.cell(95, 8, "Page {} / {{nb}}".format(self.page_no()),
                  border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, align="R")


def _pdf_section(pdf, title):
    """Titre de section avec soulignement accent."""
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_PDF_ACCENT2)
    pdf.cell(0, 8, _safe_str(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    y = pdf.get_y()
    pdf.set_draw_color(*_PDF_ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(10, y, 200, y)
    pdf.ln(3)


def _pdf_badge(pdf, text, rgb):
    """Pastille colorée centrée (statut de migration)."""
    pdf.set_font("Helvetica", "B", 11)
    bw = 130
    bx = (210 - bw) / 2.0
    pdf.set_xy(bx, pdf.get_y())
    pdf.set_fill_color(*rgb)
    pdf.set_text_color(*_PDF_WHITE)
    pdf.cell(bw, 9, _safe_str(text), align="C", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(10)
    pdf.ln(4)


def _pdf_kv_table(pdf, rows):
    """Tableau cle/valeur avec lignes alternees."""
    for idx, (label, value, value_rgb) in enumerate(rows):
        pdf.set_fill_color(*(_PDF_LIGHT if idx % 2 == 0 else _PDF_WHITE))
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_PDF_GRAY)
        pdf.cell(55, 8, _safe_str(label), border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*(value_rgb or _PDF_DARK))
        pdf.cell(0, 8, _safe_str(str(value)), border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(3)


def _pdf_stat_cards(pdf, cards):
    """Range de cartes statistiques (nombre + libelle)."""
    n     = len(cards)
    gap   = 4.0
    total = 190.0
    cw    = (total - gap * (n - 1)) / n
    ch    = 24.0
    y0    = pdf.get_y()

    for i, (number, label, rgb) in enumerate(cards):
        x = 10 + i * (cw + gap)
        pdf.set_fill_color(*_PDF_LIGHT2)
        pdf.rect(x, y0, cw, ch, style="F")
        pdf.set_fill_color(*rgb)
        pdf.rect(x, y0, cw, 1.4, style="F")

        pdf.set_xy(x, y0 + 5)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*_PDF_DARK)
        pdf.cell(cw, 9, _safe_str(str(number)), align="C")

        pdf.set_xy(x, y0 + 15)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_PDF_GRAY)
        pdf.cell(cw, 6, _safe_str(label), align="C")

    pdf.set_xy(10, y0 + ch + 6)


def _pdf_folder_table(pdf, selected_folders, folder_stats):
    """Tableau de repartition par dossier (Dossier | Fichiers | Taille)."""
    if not selected_folders:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*_PDF_GRAY)
        pdf.cell(0, 7, _safe_str("Aucun dossier selectionne."), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
        return

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_PDF_WHITE)
    pdf.set_fill_color(*_PDF_ACCENT)
    pdf.cell(90, 8, _safe_str("Dossier"),  border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="L")
    pdf.cell(50, 8, _safe_str("Fichiers"), border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="C")
    pdf.cell(50, 8, _safe_str("Taille"),   border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, align="C")

    pdf.set_font("Helvetica", "", 10)
    for idx, name in enumerate(selected_folders):
        fc, sz = folder_stats.get(name, (0, 0))
        pdf.set_fill_color(*(_PDF_LIGHT if idx % 2 == 0 else _PDF_WHITE))
        pdf.set_text_color(*_PDF_DARK)
        pdf.cell(90, 7, _safe_str(name), border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="L")
        pdf.cell(50, 7, "{:,}".format(fc), border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="C")
        pdf.cell(50, 7, _safe_str(format_size(sz)), border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, align="C")

    pdf.ln(3)


def _pdf_browsers_table(pdf, browsers_backup):
    """Tableau des navigateurs sauvegardes (Navigateur | Favoris | Mots de passe)."""
    if not browsers_backup:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*_PDF_GRAY)
        pdf.cell(0, 7, _safe_str("Aucun navigateur selectionne."), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
        return

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_PDF_WHITE)
    pdf.set_fill_color(*_PDF_ACCENT)
    pdf.cell(90, 8, _safe_str("Navigateur"),       border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="L")
    pdf.cell(50, 8, _safe_str("Favoris"),          border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="C")
    pdf.cell(50, 8, _safe_str("Mots de passe"),    border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, align="C")

    pdf.set_font("Helvetica", "", 10)
    for idx, (bname, fav, pwd) in enumerate(browsers_backup):
        pdf.set_fill_color(*(_PDF_LIGHT if idx % 2 == 0 else _PDF_WHITE))
        pdf.set_text_color(*_PDF_DARK)
        pdf.cell(90, 7, _safe_str(bname), border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="L")

        pdf.set_text_color(*(_PDF_ACCENT2 if fav else _PDF_GRAY))
        pdf.cell(50, 7, _safe_str("Oui" if fav else "-"), border=0, new_x=XPos.RIGHT,   new_y=YPos.TOP, fill=True, align="C")

        pdf.set_text_color(*(_PDF_ORANGE if pwd else _PDF_GRAY))
        pdf.cell(50, 7, _safe_str("Oui" if pwd else "-"), border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, align="C")

    pdf.ln(3)


def _pdf_text_block(pdf, lines, text_rgb, bg_rgb, max_lines, max_chars=108):
    """Bloc de texte monospace avec fond colore (logs / erreurs)."""
    pdf.set_font("Courier", "", 8)
    for line in lines[-max_lines:] if max_lines < 0 else lines[:max_lines]:
        pdf.set_fill_color(*bg_rgb)
        pdf.set_text_color(*text_rgb)
        safe = _safe_str(line[:max_chars]) + ("..." if len(line) > max_chars else "")
        pdf.cell(0, 5, safe, border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)


def generate_pdf_report(report_path, logo_path, stats, log_lines, error_lines,
                         folder_stats=None, selected_folders=None,
                         browsers_backup=None):
    if not HAS_FPDF:
        return False

    # --- CORRECTION ICI : Création automatique du dossier ---
    report_path = Path(report_path)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Erreur : Impossible de créer le dossier de rapport. {e}")
        return False
    # --------------------------------------------------------

    folder_stats     = folder_stats or {}
    selected_folders = selected_folders or []
    browsers_backup  = browsers_backup or []

    pdf = _IastralPDF(logo_path=logo_path)
    pdf.add_page()

    # ── Badge de statut ────────────────────────────────────────────────────
    if stats.get("dry_run"):
        _pdf_badge(pdf, "SIMULATION - aucun fichier copie", _PDF_ORANGE)
    else:
        _pdf_badge(pdf, "MIGRATION REELLE", _PDF_ACCENT)

    # ── Resume ─────────────────────────────────────────────────────────────
    _pdf_section(pdf, "Resume")
    _pdf_kv_table(pdf, [
        ("Date",                stats.get("date", "-"), None),
        ("Source",              stats.get("source", "-"), None),
        ("Destination",         stats.get("destination", "-"), None),
        ("Verif. SHA-256",      "Oui" if stats.get("verify") else "Non",
         _PDF_ACCENT2 if stats.get("verify") else _PDF_GRAY),
    ])

    # ── Statistiques (cartes) ─────────────────────────────────────────────
    _pdf_section(pdf, "Statistiques")
    skipped = stats.get("files_skipped", 0)
    _pdf_stat_cards(pdf, [
        ("{:,}".format(stats.get("files_detected", 0)), "Fichiers detectes", _PDF_ACCENT),
        ("{:,}".format(stats.get("files_copied", 0)),    "Fichiers copies",   _PDF_ACCENT2),
        ("{:,}".format(skipped),                         "Fichiers ignores",
         _PDF_RED if skipped > 0 else _PDF_GRAY),
        (stats.get("total_size_human", "-"),             "Taille totale",     _PDF_ORANGE),
    ])

    # ── Repartition par dossier ────────────────────────────────────────────
    _pdf_section(pdf, "Repartition par dossier")
    _pdf_folder_table(pdf, selected_folders, folder_stats)

    # ── Navigateurs sauvegardes ────────────────────────────────────────────
    _pdf_section(pdf, "Navigateurs sauvegardes")
    _pdf_browsers_table(pdf, browsers_backup)

    # ── Erreurs ────────────────────────────────────────────────────────────
    if error_lines:
        _pdf_section(pdf, "Erreurs ({})".format(len(error_lines)))
        _pdf_text_block(pdf, error_lines, _PDF_RED, _PDF_RED_BG, max_lines=80)

    # ── Journal d'activite ─────────────────────────────────────────────────
    pdf.add_page()
    _pdf_section(pdf, "Journal d'activite (50 dernieres lignes)")
    _pdf_text_block(pdf, log_lines, _PDF_GRAY, _PDF_LIGHT2, max_lines=-50)

    try:
        pdf.output(str(report_path))
        return True
    except Exception:
        return False


# =============================================================================
#  APPLICATION PRINCIPALE
# =============================================================================

class IASTRAL(ctk.CTk):
    """Fenêtre principale IASTRAL — stable, compatible Python 3.7+ / 3.14"""

    # ── Données statiques des dossiers ────────────────────────────────────────
    FOLDER_DEFS = [
        ("Bureau",          ["Bureau", "Desktop"],            "Desktop"),
        ("Documents",       ["Documents"],                    "Documents"),
        ("Telechargements", ["Telechargements", "Downloads"], "Downloads"),
        ("Images",          ["Images", "Pictures"],           "Pictures"),
        ("Musique",         ["Musique", "Music"],             "Music"),
        ("Videos",          ["Videos"],                       "Videos"),
    ]
    FOLDER_LABELS = {
        "Bureau":          "💻  Bureau",
        "Documents":       "📃  Documents",
        "Telechargements": "📃  Telechargements",
        "Images":          "🖼️  Images",
        "Musique":         "🎵  Musique",
        "Videos":          "🎥  Videos",
    }

    def __init__(self):
        # ── Fenêtre CTk principale ────────────────────────────────────────
        # set_appearance_mode / set_default_color_theme sont appelés au
        # niveau module (fin de fichier, avant if __name__) — c'est la seule
        # configuration requise pour Python 3.14 + CTk 5.2.2.
        super().__init__()

        # ── ÉTAPE 2 : attributs Python purs (zéro interaction Tk) ─────────
        self.theme     = _CTK_THEME
        self.C         = dict(PALETTE_DARK if self.theme == "dark"
                              else PALETTE_LIGHT)
        self._widgets        = {}         # registre des widgets reconfigurables
        self._logo_img = None       # garde la référence CTkImage en vie

        self.destination      = ctk.StringVar()
        self.cancel_requested = False
        self.dry_run_mode     = False
        self.verify_hashes    = True

        self.total_files   = 0
        self.total_size    = 0
        self.copied_files  = 0
        self.skipped_files = 0
        self._log_lines    = []   # type: list
        self._error_lines  = []   # type: list
        self._folder_stats = {}   # type: dict  -> {folder_name: (files, bytes)}
        self._realtime_log_path = None  # type: object  # fichier log temps-reel

        self.folder_checkboxes    = {}  # type: dict
        self.browser_bookmark_cbs = {}  # type: dict
        self.browser_password_cbs = {}  # type: dict

        # ── ÉTAPE 3 : configuration fenêtre ───────────────────────────────
        self.title("IASTRAL - Sauvegarde & Migration")
        self.geometry("1200x900")
        self.minsize(900, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── ÉTAPE 4 : données métier (pas de widgets) ─────────────────────
        _here = Path(__file__).resolve().parent
        self.logo_path = None  # type: object
        for _c in [_here / "logo-IASTRAL.jpg",
                   _here / "assets" / "logo.jpg",
                   _here / "logo.jpg"]:
            if _c.exists():
                self.logo_path = _c
                break

        # Icone fenetre : cherche .ico en priorite, puis .jpg converti via PIL
        _icon_set = False
        for _ico in [_here / "logo-IASTRAL.ico",
                     _here / "assets" / "logo.ico",
                     _here / "icon.ico"]:
            if _ico.exists():
                try:
                    self.iconbitmap(str(_ico))
                    _icon_set = True
                    break
                except Exception:
                    pass
        if not _icon_set and self.logo_path:
            try:
                _pil_img = Image.open(str(self.logo_path)).resize((32, 32))
                import tempfile, os as _os
                _tmp_ico = Path(tempfile.gettempdir()) / "iastral_icon.png"
                _pil_img.save(str(_tmp_ico))
                _tk_img = tk.PhotoImage(file=str(_tmp_ico))
                self.iconphoto(True, _tk_img)
                self._icon_ref = _tk_img   # garder la reference
            except Exception:
                pass

        self.folders = self._detect_user_folders()  # type: dict

        # ── ÉTAPE 5 : construction UI ──────────────────────────────────────
        self._build_ui()

        # ── ÉTAPE 6 : tâches différées ────────────────────────────────────
        # Charger l'état sauvegardé (destination + checkboxes) si disponible
        self.after(100, self._load_state)
        self.after(500, lambda: threading.Thread(
            target=self._auto_detect_usb, daemon=True).start())

    # ─────────────────────────────────────────────────────────────────────────
    #  Persistance d'état (destination + sélections)
    # ─────────────────────────────────────────────────────────────────────────

    def _state_file(self):
        # type: () -> Path
        return Path(__file__).resolve().parent / ".iastral_state.json"

    def _save_state(self):
        """Sauvegarde destination + état des checkboxes dans un fichier JSON."""
        state = {
            "destination": self.destination.get(),
            "folders":     {k: bool(cb.get()) for k, cb in self.folder_checkboxes.items()},
            "bookmarks":   {k: bool(cb.get()) for k, cb in self.browser_bookmark_cbs.items()},
            "passwords":   {k: bool(cb.get()) for k, cb in self.browser_password_cbs.items()},
        }
        try:
            with open(str(self._state_file()), "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_state(self):
        """Restaure l'état sauvegardé au démarrage."""
        sf = self._state_file()
        if not sf.exists():
            return
        try:
            with open(str(sf), encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            return
        # Destination
        dest = state.get("destination", "")
        if dest and Path(dest).exists():
            try:
                self.destination.set(dest)
            except Exception:
                pass
        # Checkboxes dossiers
        for k, val in state.get("folders", {}).items():
            cb = self.folder_checkboxes.get(k)
            if cb:
                try:
                    cb.select() if val else cb.deselect()
                except Exception:
                    pass
        # Checkboxes navigateurs
        for k, val in state.get("bookmarks", {}).items():
            cb = self.browser_bookmark_cbs.get(k)
            if cb:
                try:
                    if cb.cget("state") != "disabled":
                        cb.select() if val else cb.deselect()
                except Exception:
                    pass
        for k, val in state.get("passwords", {}).items():
            cb = self.browser_password_cbs.get(k)
            if cb:
                try:
                    if cb.cget("state") != "disabled":
                        cb.select() if val else cb.deselect()
                except Exception:
                    pass
        self.log("Etat precedent restaure.")

    # ─────────────────────────────────────────────────────────────────────────
    def _show_help(self):
        # 1️⃣ Éviter les doublons de fenêtres
        if hasattr(self, '_help_window') and self._help_window.winfo_exists():
            self._help_window.destroy()

        # Création de la fenêtre de Toplevel
        win = ctk.CTkToplevel(self)
        self._help_window = win 
        
        win.title("Aide — IASTRAL")
        win.geometry("700x620")
        
        # 🔓 Autorise le contrôle complet (Agrandir / Réduire / Restreindre)
        win.resizable(True, True) 
        
        # Rend la fenêtre d'aide indépendante tout en restant au premier plan
        win.attributes("-topmost", True)
        
        C = self.C
        win.configure(fg_color=C["BG"])
        
        # ── EN-TÊTE (Fixe en haut) ──────────────────────────────────────
        hdr = ctk.CTkFrame(win, fg_color=C["ACCENT"], corner_radius=0, height=52)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="ℹ️  Comment utiliser IASTRAL ?",
            font=("Segoe UI", 15, "bold"), text_color="#ffffff").pack(
            side="left", padx=20, pady=14)
            
        # ── PIED DE PAGE FIXE (Contient le bouton Fermer) ────────────────
        foot = ctk.CTkFrame(win, fg_color=C["CARD2"], height=48)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        ctk.CTkButton(foot, text="Fermer", width=120, height=32,
            font=("Segoe UI", 12, "bold"),
            fg_color=C["ACCENT"], hover_color=C["ACCENT2"],
            corner_radius=8, command=win.destroy).pack(
            side="right", padx=16, pady=8)

        # ── ZONE DE FOND (Prend tout l'espace disponible) ────────────────
        body_frame = ctk.CTkFrame(win, fg_color=C["CARD"], corner_radius=0)
        body_frame.pack(fill="both", expand=True, side="top")
        
        # 🎯 LE SECRET DU CENTRAGE : Un conteneur invisible au centre avec une largeur fixe.
        # Il va maintenir le texte parfaitement regroupé au milieu, peu importe la taille de la fenêtre.
        center_container = ctk.CTkFrame(body_frame, fg_color=C["CARD"], width=560)
        center_container.pack(fill="y", expand=True, pady=20)
        center_container.pack_propagate(False) # Force le respect de la largeur idéale pour la lecture
        
        txt = ctk.CTkTextbox(center_container, font=("Segoe UI", 13),
            fg_color=C["CARD"], text_color=C["TEXT"],
            border_width=0, corner_radius=0,
            scrollbar_button_color=C["ACCENT"],
            scrollbar_button_hover_color=C["ACCENT2"])
        txt.pack(fill="both", expand=True) 
        
        # Le texte est propre, sans espaces artificiels au début ni ligne de séparation sous le titre principal
        HELP = "\n".join([
            "IASTRAL — Sauvegarde & Migration de données",
            "",
            "",
            "💡 À QUOI ÇA SERT ?",
            "",
            "IASTRAL copie vos fichiers personnels (Bureau, Documents,",
            "Téléchargements, Images, Musique, Vidéos) ainsi que vos",
            "données de navigateurs (favoris, mots de passe) vers une",
            "clé USB ou un disque externe.",
            "👉 Idéal pour migrer vers un nouveau PC ou sécuriser vos données.",
            "",
            "🚀 ÉTAPES D'UTILISATION",
            "",
            "1️⃣  DESTINATION : Choisissez un dossier avec 'Parcourir' ou",
            "      branchez une clé USB (détection automatique).",
            "",
            "2️⃣  DOSSIERS    : Cochez les dossiers à sauvegarder.",
            "",
            "3️⃣  NAVIGATEURS : Cochez les favoris/mots de passe à extraire",
            "      des navigateurs installés (repérés par [OK]).",
            "",
            "4️⃣  ANALYSER    : Calcule la taille totale et vérifie l'espace",
            "      disponible sur votre support de destination.",
            "",
            "5️⃣  DÉMARRER    : Lance la copie. Un rapport PDF détaillé sera",
            "      généré directement dans le dossier de destination.",
            "",
            "🛠️ FONCTIONNALITÉS AVANCÉES",
            "",
            "• Mode Simulation   : Calcule et génère le rapport PDF (mention",
            "                       SIMULATION) sans copier aucun fichier.",
            "• Contrôle Intégrité: Vérification SHA-256 après copie. Affiche",
            "                       [HASH FAIL] dans le journal en cas d'erreur.",
            "• Reprise sur Erreur: Si un fichier est verrouillé, l'application",
            "                       tente 3 essais (attente de 5s entre chaque).",
            "• Sauvegarde Auto.  : Votre configuration (sélections et dossier",
            "                       cible) est mémorisée pour le prochain lancement.",
            "",
            "📋 JOURNAL DE BORD",
            "",
            "Toutes les actions sont consignées en temps réel dans le fichier",
            "'migration.log' à la racine de votre destination.",
            "En cas d'arrêt imprévu, l'historique reste préservé.",
        ])
        
        txt.insert("1.0", HELP)
        txt.configure(state="disabled")
        
        # 🎯 SÉCURITÉ ANTI-DEFILEMENT ARRIÈRE-PLAN
        def _bloquer_scroll_parent(event):
            txt._textbox.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        txt.bind("<MouseWheel>", _bloquer_scroll_parent)
        win.bind("<MouseWheel>", _bloquer_scroll_parent)
        
        txt.focus_set()
    # ─────────────────────────────────────────────────────────────────────────
    def _on_close(self):
        """Fermeture propre : stoppe les threads, évite TclError."""
        self._save_state()   # sauvegarder l'état avant fermeture
        self.cancel_requested = True
        # Laisser 150ms aux threads daemon pour se terminer proprement
        # avant que Tkinter détruise les widgets (évite TclError dans after())
        try:
            self.after(150, self._force_destroy)
        except Exception:
            self._force_destroy()

    def _force_destroy(self):
        try:
            self.destroy()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    def _detect_user_folders(self):
        # type: () -> dict
        home = Path.home()
        od = None
        if (home / "OneDrive").exists():
            od = home / "OneDrive"
        else:
            try:
                for item in home.iterdir():
                    if item.is_dir() and item.name.lower().startswith("onedrive"):
                        od = item
                        break
            except PermissionError:
                pass

        def _r(names, fb):
            if od:
                for n in names:
                    c = od / n
                    if c.exists():
                        return c
            return home / fb

        result = {}
        for key, names, fb in self.FOLDER_DEFS:
            result[key] = _r(names, fb)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    #  Thread-safe UI helper
    # ─────────────────────────────────────────────────────────────────────────

    def _safe_cfg(self, widget, **kwargs):
        """Configure widget de façon thread-safe et silencieuse."""
        def _do():
            try:
                if widget is not None:
                    widget.configure(**kwargs)
            except Exception:
                pass
        self.after(0, _do)

    # ─────────────────────────────────────────────────────────────────────────
    #  Bascule thème — SANS reconstruire les widgets
    # ─────────────────────────────────────────────────────────────────────────

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.C = dict(PALETTE_LIGHT if self.theme == "light" else PALETTE_DARK)
        ctk.set_appearance_mode(self.theme)
        self._apply_theme_to_widgets()
        emoji = "🌟 ➔ 🌙" if self.theme == "light" else "🌙 ➔ 🌟"
        try:
            self._widgets["theme_btn"].configure(text=emoji)
        except Exception:
            pass
        self.log("Theme bascule : {}".format("Clair" if self.theme == "light" else "Sombre"))

    def _apply_theme_to_widgets(self):
        """Reconfigure uniquement les couleurs des widgets existants."""
        C = self.C

        # widgets simples enregistrés dans self._widgets
        cfg_map = {
            "outer":        {"fg_color": C["BG"]},
            "inner":        {"fg_color": C["BG"]},
            "scrollbar":    {"fg_color": C["CARD"],
                             "button_color": C["ACCENT"],
                             "button_hover_color": C["ACCENT2"]},
            "header":       {"fg_color": C["HEADER_BG"]},
            "accent_band":  {"fg_color": C["ACCENT"]},
            "top_row":      {"fg_color": C["HEADER_BG"]},
            "theme_btn":    {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                             "border_color": C["BORDER"], "text_color": C["MUTED"]},
            "logo_frame":   {"fg_color": C["HEADER_BG"]},
            "subtitle_lbl": {"text_color": C["MUTED"]},
            "usb_bar":      {"fg_color": C["CARD2"]},
            "usb_label":    {"text_color": C["MUTED"]},
            "usb_refresh":  {"fg_color": C["CARD"], "hover_color": C["BORDER"],
                             "border_color": C["BORDER"], "text_color": C["MUTED"]},
            "dest_card":    {"fg_color": C["CARD"], "border_color": C["BORDER"]},
            "dest_hdr_f":   {"fg_color": C["CARD"]},
            "dest_lbl":     {"text_color": C["TEXT"]},
            "dest_row":     {"fg_color": C["CARD"]},
            "dest_entry":   {"fg_color": C["CARD2"], "border_color": C["BORDER"],
                             "text_color": C["TEXT"]},
            "browse_btn":   {"fg_color": C["ACCENT"], "hover_color": C["ACCENT2"]},
            "disk_card":    {"fg_color": C["CARD"], "border_color": C["BORDER"]},
            "disk_inner":   {"fg_color": C["CARD"]},
            "disk_title":   {"text_color": C["TEXT"]},
            "disk_label":   {"text_color": C["MUTED"]},
            "tabview":      {"fg_color": C["CARD"],
                             "segmented_button_fg_color": C["CARD2"],
                             "segmented_button_selected_color": C["ACCENT"],
                             "segmented_button_selected_hover_color": C["ACCENT2"],
                             "segmented_button_unselected_color": C["CARD2"],
                             "segmented_button_unselected_hover_color": C["BORDER"],
                             "text_color": C["TEXT"],
                             "border_color": C["BORDER"]},
            "actions_card": {"fg_color": C["CARD"], "border_color": C["BORDER"]},
            "btn_row":      {"fg_color": C["CARD"]},
            "analyze_btn":  {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                             "border_color": C["ACCENT"], "text_color": C["ACCENT"]},
            "start_btn":    {"fg_color": C["ACCENT"], "hover_color": C["ACCENT2"]},
            "cancel_btn":   {"fg_color": C["RED"],    "hover_color": C["RED2"]},
            "dryrun_btn":   {"fg_color": C["CARD2"],  "hover_color": C["BORDER"],
                             "border_color": C["WARN"], "text_color": C["WARN"]},
            "pf":           {"fg_color": C["CARD"]},
            "status_label": {"text_color": C["MUTED"]},
            "progress":     {"fg_color": C["CARD2"], "progress_color": C["ACCENT"]},
            "results_card": {"fg_color": C["CARD"], "border_color": C["BORDER"]},
            "results_hdr":  {"fg_color": C["CARD"]},
            "results_title":{"text_color": C["TEXT"]},
            "total_label":  {"text_color": C["ACCENT"]},
            "tree_wrap":    {"fg_color": C["CARD"]},
            "log_card":     {"fg_color": C["CARD"], "border_color": C["BORDER"]},
            "log_hdr":      {"fg_color": C["CARD"]},
            "log_title":    {"text_color": C["TEXT"]},
            "clear_btn":    {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                             "border_color": C["BORDER"], "text_color": C["MUTED"]},
            "logs":         {"fg_color": C["CARD2"], "text_color": C["TEXT"],
                             "border_color": C["BORDER"],
                             "scrollbar_button_color": C["ACCENT"],
                             "scrollbar_button_hover_color": C["ACCENT2"]},
            # onglet dossiers
            "folders_hint": {"text_color": C["MUTED"]},
            "folders_grid": {"fg_color": C["CARD"]},
            "sel_all_f":    {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                             "border_color": C["ACCENT"], "text_color": C["ACCENT"]},
            "desel_all_f":  {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                             "border_color": C["MUTED"], "text_color": C["MUTED"]},
            # onglet navigateurs
            "browsers_hint":{"text_color": C["MUTED"]},
            "nav_grid":     {"fg_color": C["CARD"]},
            "nav_h0":       {"text_color": C["MUTED"]},
            "nav_h1":       {"text_color": C["TEAL"]},   # ⭐ Favoris
            "nav_h2":       {"text_color": C["ORANGE"]},
            "bm_all_btn":   {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                             "border_color": C["TEAL"], "text_color": C["TEAL"]},
            "pw_all_btn":   {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                             "border_color": C["ORANGE"], "text_color": C["ORANGE"]},
            "bm_none_btn":      {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                                 "border_color": C["MUTED"], "text_color": C["MUTED"]},
            "toggle_all_browsers": {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                                 "border_color": C["ACCENT"], "text_color": C["ACCENT"]},
            "help_btn":            {"fg_color": C["CARD2"], "hover_color": C["BORDER"],
                                 "border_color": C["BORDER"], "text_color": C["MUTED"]},
        }

        for key, kw in cfg_map.items():
            w = self._widgets.get(key)
            if w is None:
                continue
            try:
                w.configure(**kw)
            except Exception:
                pass

        # Canvas fond
        try:
            self._widgets["canvas"].configure(bg=C["BG"])
        except Exception:
            pass
        try:
            self.configure(fg_color=C["BG"])
        except Exception:
            pass

        # Checkboxes dossiers
        for cb in self.folder_checkboxes.values():
            try:
                cb.configure(fg_color=C["ACCENT"], hover_color=C["ACCENT2"],
                             text_color=C["TEXT"], border_color=C["BORDER"])
            except Exception:
                pass

        # Cellules dossiers
        for key in list(self._widgets.keys()):
            if key.startswith("folder_cell_"):
                try:
                    self._widgets[key].configure(fg_color=C["CARD2"], border_color=C["BORDER"])
                except Exception:
                    pass
            if key.startswith("folder_inner_"):
                try:
                    self._widgets[key].configure(fg_color=C["CARD2"])
                except Exception:
                    pass

        # Checkboxes navigateurs
        browsers = get_browser_paths()
        for bname, cbf in self.browser_bookmark_cbs.items():
            inst = browsers.get(bname, {}).get("base", Path("__x__")).exists()
            tc = C["TEXT"] if inst else C["MUTED"]
            try:
                cbf.configure(fg_color=C["TEAL"], hover_color=C["ACCENT2"],
                              text_color=tc, border_color=C["BORDER"])
            except Exception:
                pass
        for bname, cbp in self.browser_password_cbs.items():
            inst = browsers.get(bname, {}).get("base", Path("__x__")).exists()
            tc = C["TEXT"] if inst else C["MUTED"]
            try:
                cbp.configure(fg_color=C["ORANGE"], hover_color=C["ACCENT2"],
                              text_color=tc, border_color=C["BORDER"])
            except Exception:
                pass

        # Cellules navigateurs : frames + labels — tout reconfigure pour le theme
        browsers = get_browser_paths()
        for bname, binfo in browsers.items():
            inst = binfo.get("base", Path("__x__")).exists()
            cbg  = C["CARD2"] if inst else C["BG"]
            cbo  = C["BORDER"] if inst else C["CARD2"]
            txt  = C["TEXT"]   if inst else C["MUTED"]
            for prefix, has_border in (
                ("nav_cell_",  True),
                ("nav_inner_", False),
                ("nav_fav_",   True),
                ("nav_pwd_",   True),
            ):
                widget = self._widgets.get(prefix + bname)
                if widget is None:
                    continue
                try:
                    if has_border:
                        widget.configure(fg_color=cbg, border_color=cbo)
                    else:
                        widget.configure(fg_color=cbg)
                except Exception:
                    pass
            for lk in ("nav_lbl_abbr_", "nav_lbl_name_"):
                lbl = self._widgets.get(lk + bname)
                if lbl:
                    try:
                        lbl.configure(text_color=txt)
                    except Exception:
                        pass
            for cb_dict in (self.browser_bookmark_cbs, self.browser_password_cbs):
                cb = cb_dict.get(bname)
                if cb is not None and inst:
                    try:
                        cb.configure(text_color=txt, border_color=C["BORDER"])
                    except Exception:
                        pass

        # Treeview ttk
        try:
            style = ttk.Style()
            style.configure("IASTRAL.Treeview",
                background=C["CARD2"], foreground=C["TEXT"],
                fieldbackground=C["CARD2"], bordercolor=C["BORDER"],
                rowheight=28, font=("Segoe UI", 12))
            style.configure("IASTRAL.Treeview.Heading",
                background=C["BORDER"], foreground=C["MUTED"],
                font=("Segoe UI", 11, "bold"), relief="flat")
            style.map("IASTRAL.Treeview",
                background=[("selected", C["ACCENT"])],
                foreground=[("selected", "#ffffff")])
            style.configure("IASTRAL.Vertical.TScrollbar",
                background=C["CARD"], troughcolor=C["CARD2"], arrowcolor=C["MUTED"])
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    #  CONSTRUCTION UI (une seule fois)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        C = self.C
        self.configure(fg_color=C["BG"])
        w = self._widgets

        # ── Conteneur scrollable ──────────────────────────────────────────
        outer = ctk.CTkFrame(self, fg_color=C["BG"])
        outer.pack(fill="both", expand=True)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        w["outer"] = outer

        canvas = tk.Canvas(outer, highlightthickness=0, bg=C["BG"])
        canvas.grid(row=0, column=0, sticky="nsew")
        w["canvas"] = canvas

        scrollbar = ctk.CTkScrollbar(
            outer, orientation="vertical", command=canvas.yview,
            fg_color=C["CARD"], button_color=C["ACCENT"],
            button_hover_color=C["ACCENT2"])
        scrollbar.grid(row=0, column=1, sticky="ns")
        w["scrollbar"] = scrollbar
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = ctk.CTkFrame(canvas, fg_color=C["BG"])
        w["inner"] = inner
        cwin = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(cwin, width=e.width))
        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _mw(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _mw)
        canvas.bind_all("<Button-4>",   _mw)
        canvas.bind_all("<Button-5>",   _mw)

        # ── En-tête ───────────────────────────────────────────────────────
        header = ctk.CTkFrame(inner, fg_color=C["HEADER_BG"], corner_radius=0)
        header.pack(fill="x")
        w["header"] = header

        ab = ctk.CTkFrame(header, height=3, fg_color=C["ACCENT"], corner_radius=0)
        ab.pack(fill="x")
        w["accent_band"] = ab

        top_row = ctk.CTkFrame(header, fg_color=C["HEADER_BG"])
        top_row.pack(fill="x", padx=16, pady=(10, 0))
        w["top_row"] = top_row

        theme_emoji = "🌟 ➔ 🌙" if self.theme == "light" else "🌙 ➔ 🌟"
        theme_btn = ctk.CTkButton(
            top_row, text=theme_emoji, width=44, height=32,
            font=("Segoe UI", 16),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["BORDER"],
            text_color=C["MUTED"], corner_radius=8,
            command=self.toggle_theme)
        theme_btn.pack(side="right", padx=(4,16), pady=10)
        w["theme_btn"] = theme_btn
        help_btn = ctk.CTkButton(
            top_row, text="!?", width=44, height=32,
            font=("Segoe UI", 16),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["BORDER"],
            text_color=C["MUTED"], corner_radius=8,
            command=self._show_help)
        help_btn.pack(side="right", padx=(0,4), pady=10)
        w["help_btn"] = help_btn

        logo_frame = ctk.CTkFrame(header, fg_color=C["HEADER_BG"])
        logo_frame.pack(fill="x", pady=(10, 4))
        w["logo_frame"] = logo_frame

        if self.logo_path:
            try:
                _img = ctk.CTkImage(
                    light_image=Image.open(str(self.logo_path)),
                    dark_image=Image.open(str(self.logo_path)),
                    size=(240, 60))
                ctk.CTkLabel(logo_frame, text="", image=_img).pack(anchor="center")
                self._logo_img = _img   # garde la référence
            except Exception:
                ctk.CTkLabel(logo_frame, text="IASTRAL",
                    font=("Segoe UI", 26, "bold"),
                    text_color=C["ACCENT"]).pack(anchor="center")
        else:
            ctk.CTkLabel(logo_frame, text="IASTRAL",
                font=("Segoe UI", 26, "bold"),
                text_color=C["ACCENT"]).pack(anchor="center")

        sub = ctk.CTkLabel(
            header, text="Sauvegarde & Migration de donnees Windows",
            font=("Segoe UI", 13), text_color=C["MUTED"])
        sub.pack(anchor="center", pady=(0, 12))
        w["subtitle_lbl"] = sub

        # ── Bandeau USB ───────────────────────────────────────────────────
        usb_bar = ctk.CTkFrame(inner, fg_color=C["CARD2"], corner_radius=0)
        usb_bar.pack(fill="x")
        w["usb_bar"] = usb_bar

        usb_lbl = ctk.CTkLabel(
            usb_bar, text="Recherche de lecteurs amovibles...",
            font=("Segoe UI", 11), text_color=C["MUTED"])
        usb_lbl.pack(side="left", padx=16, pady=7)
        w["usb_label"] = usb_lbl

        usb_ref = ctk.CTkButton(
            usb_bar, text="Rafraichir", width=110, height=28,
            font=("Segoe UI", 11),
            fg_color=C["CARD"], hover_color=C["BORDER"],
            border_width=1, border_color=C["BORDER"],
            text_color=C["MUTED"], corner_radius=6,
            command=lambda: threading.Thread(
                target=self._auto_detect_usb, daemon=True).start())
        usb_ref.pack(side="right", padx=16, pady=7)
        w["usb_refresh"] = usb_ref

        # ── Destination ───────────────────────────────────────────────────
        dest_card = ctk.CTkFrame(
            inner, fg_color=C["CARD"], corner_radius=14,
            border_width=1, border_color=C["BORDER"])
        dest_card.pack(fill="x", padx=24, pady=(14, 0))
        w["dest_card"] = dest_card

        dh = ctk.CTkFrame(dest_card, fg_color=C["CARD"])
        dh.pack(fill="x", padx=16, pady=(14, 0))
        w["dest_hdr_f"] = dh
        dest_lbl = ctk.CTkLabel(
            dh, text="Dossier de destination",
            font=("Segoe UI", 14, "bold"), text_color=C["TEXT"])
        dest_lbl.pack(side="left")
        w["dest_lbl"] = dest_lbl

        dr = ctk.CTkFrame(dest_card, fg_color=C["CARD"])
        dr.pack(fill="x", padx=16, pady=(8, 16))
        w["dest_row"] = dr

        dest_entry = ctk.CTkEntry(
            dr, textvariable=self.destination, height=40,
            font=("Segoe UI", 13),
            fg_color=C["CARD2"], border_color=C["BORDER"],
            text_color=C["TEXT"],
            placeholder_text="Selectionner un dossier de destination...",
            corner_radius=10)
        dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        w["dest_entry"] = dest_entry

        browse_btn = ctk.CTkButton(
            dr, text="Parcourir", width=130, height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=C["ACCENT"], hover_color=C["ACCENT2"],
            corner_radius=10, command=self.select_folder)
        browse_btn.pack(side="right")
        w["browse_btn"] = browse_btn

        # ── Espace disque ─────────────────────────────────────────────────
        disk_card = ctk.CTkFrame(
            inner, fg_color=C["CARD"], corner_radius=14,
            border_width=1, border_color=C["BORDER"])
        disk_card.pack(fill="x", padx=24, pady=(10, 0))
        w["disk_card"] = disk_card

        di = ctk.CTkFrame(disk_card, fg_color=C["CARD"])
        di.pack(fill="x", padx=16, pady=10)
        w["disk_inner"] = di

        disk_title = ctk.CTkLabel(
            di, text="Espace disque",
            font=("Segoe UI", 13, "bold"), text_color=C["TEXT"])
        disk_title.pack(side="left")
        w["disk_title"] = disk_title

        disk_lbl = ctk.CTkLabel(
            di, text="Selectionnez d'abord une destination.",
            font=("Segoe UI", 12), text_color=C["MUTED"])
        disk_lbl.pack(side="right")
        w["disk_label"] = disk_lbl

        self.destination.trace_add(
            "write", lambda *_: self.after(0, self._update_disk_info))

        # ── Onglets ───────────────────────────────────────────────────────
        tabview = ctk.CTkTabview(
            inner, fg_color=C["CARD"],
            segmented_button_fg_color=C["CARD2"],
            segmented_button_selected_color=C["ACCENT"],
            segmented_button_selected_hover_color=C["ACCENT2"],
            segmented_button_unselected_color=C["CARD2"],
            segmented_button_unselected_hover_color=C["BORDER"],
            text_color=C["TEXT"], corner_radius=14,
            border_width=1, border_color=C["BORDER"])
        tabview.pack(fill="x", padx=24, pady=(14, 0))
        w["tabview"] = tabview

        tab_f = tabview.add("📁  Dossiers")
        tab_b = tabview.add("🌐  Navigateurs")
        self._build_tab_folders(tab_f)
        self._build_tab_browsers(tab_b)

        # ── Actions ───────────────────────────────────────────────────────
        actions_card = ctk.CTkFrame(
            inner, fg_color=C["CARD"], corner_radius=14,
            border_width=1, border_color=C["BORDER"])
        actions_card.pack(fill="x", padx=24, pady=(14, 0))
        w["actions_card"] = actions_card

        btn_row = ctk.CTkFrame(actions_card, fg_color=C["CARD"])
        btn_row.pack(fill="x", padx=16, pady=(16, 8))
        w["btn_row"] = btn_row

        analyze_btn = ctk.CTkButton(
            btn_row, text="🔍  ANALYSER", width=160, height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["ACCENT"],
            text_color=C["ACCENT"], corner_radius=10,
            command=self.start_analysis)
        analyze_btn.pack(side="left", padx=(0, 10))
        w["analyze_btn"] = analyze_btn

        start_btn = ctk.CTkButton(
            btn_row, text="▶  DEMARRER", width=160, height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color=C["ACCENT"], hover_color=C["ACCENT2"],
            corner_radius=10, command=self.start_migration)
        start_btn.pack(side="left", padx=(0, 10))
        w["start_btn"] = start_btn

        cancel_btn = ctk.CTkButton(
            btn_row, text="✕  ANNULER", width=160, height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color=C["RED"], hover_color=C["RED2"],
            corner_radius=10, command=self.cancel_task)
        cancel_btn.pack(side="left", padx=(0, 10))
        w["cancel_btn"] = cancel_btn

        dryrun_btn = ctk.CTkButton(
            btn_row, text="🧪  SIMULATION", width=160, height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["WARN"],
            text_color=C["WARN"], corner_radius=10,
            command=self.start_dry_run)
        dryrun_btn.pack(side="left")
        w["dryrun_btn"] = dryrun_btn

        pf = ctk.CTkFrame(actions_card, fg_color=C["CARD"])
        pf.pack(fill="x", padx=16, pady=(4, 0))
        w["pf"] = pf

        status_lbl = ctk.CTkLabel(
            pf, text="Pret",
            font=("Segoe UI", 12), text_color=C["MUTED"])
        status_lbl.pack(anchor="w", pady=(0, 4))
        w["status_label"] = status_lbl

        progress = ctk.CTkProgressBar(
            actions_card, height=8, corner_radius=4,
            fg_color=C["CARD2"], progress_color=C["ACCENT"])
        progress.pack(fill="x", padx=16, pady=(0, 12))
        progress.set(0)
        w["progress"] = progress

        # ── Résultats ─────────────────────────────────────────────────────
        results_card = ctk.CTkFrame(
            inner, fg_color=C["CARD"], corner_radius=14,
            border_width=1, border_color=C["BORDER"])
        results_card.pack(fill="x", padx=24, pady=(14, 0))
        w["results_card"] = results_card

        rh = ctk.CTkFrame(results_card, fg_color=C["CARD"])
        rh.pack(fill="x", padx=16, pady=(14, 8))
        w["results_hdr"] = rh

        rtitle = ctk.CTkLabel(
            rh, text="Resultats d'analyse",
            font=("Segoe UI", 14, "bold"), text_color=C["TEXT"])
        rtitle.pack(side="left")
        w["results_title"] = rtitle

        total_lbl = ctk.CTkLabel(
            rh, text="Total : 0 fichier | 0 Mo",
            font=("Segoe UI", 12), text_color=C["ACCENT"])
        total_lbl.pack(side="right")
        w["total_label"] = total_lbl

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("IASTRAL.Treeview",
            background=C["CARD2"], foreground=C["TEXT"],
            fieldbackground=C["CARD2"], bordercolor=C["BORDER"],
            rowheight=28, font=("Segoe UI", 12))
        style.configure("IASTRAL.Treeview.Heading",
            background=C["BORDER"], foreground=C["MUTED"],
            font=("Segoe UI", 11, "bold"), relief="flat")
        style.map("IASTRAL.Treeview",
            background=[("selected", C["ACCENT"])],
            foreground=[("selected", "#ffffff")])
        style.configure("IASTRAL.Vertical.TScrollbar",
            background=C["CARD"], troughcolor=C["CARD2"], arrowcolor=C["MUTED"])

        tw = ctk.CTkFrame(results_card, fg_color=C["CARD"])
        tw.pack(fill="x", padx=16, pady=(0, 16))
        w["tree_wrap"] = tw

        tree = ttk.Treeview(
            tw, columns=("Dossier", "Fichiers", "Taille"),
            show="headings", height=7, style="IASTRAL.Treeview")
        tree.heading("Dossier",  text="  Dossier")
        tree.heading("Fichiers", text="Fichiers")
        tree.heading("Taille",   text="Taille")
        tree.column("Dossier",  minwidth=200, anchor="w",      stretch=True)
        tree.column("Fichiers", minwidth=100, width=160, anchor="center", stretch=True)
        tree.column("Taille",   minwidth=100, width=160, anchor="center", stretch=True)

        tsb = ttk.Scrollbar(
            tw, orient="vertical", command=tree.yview,
            style="IASTRAL.Vertical.TScrollbar")
        tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        tree.pack(fill="x", expand=True)
        w["tree"] = tree

        # ── Journal ───────────────────────────────────────────────────────
        log_card = ctk.CTkFrame(
            inner, fg_color=C["CARD"], corner_radius=14,
            border_width=1, border_color=C["BORDER"])
        log_card.pack(fill="both", expand=True, padx=24, pady=(14, 24))
        w["log_card"] = log_card

        lh = ctk.CTkFrame(log_card, fg_color=C["CARD"])
        lh.pack(fill="x", padx=16, pady=(14, 6))
        w["log_hdr"] = lh

        log_title = ctk.CTkLabel(
            lh, text="Journal d'activite",
            font=("Segoe UI", 14, "bold"), text_color=C["TEXT"])
        log_title.pack(side="left")
        w["log_title"] = log_title

        clear_btn = ctk.CTkButton(
            lh, text="Vider", width=80, height=28,
            font=("Segoe UI", 11),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["BORDER"],
            text_color=C["MUTED"], corner_radius=6,
            command=self._clear_log)
        clear_btn.pack(side="right")
        w["clear_btn"] = clear_btn

        logs = ctk.CTkTextbox(
            log_card, height=200, font=("Consolas", 12),
            fg_color=C["CARD2"], text_color=C["TEXT"],
            border_color=C["BORDER"], border_width=1, corner_radius=10,
            scrollbar_button_color=C["ACCENT"],
            scrollbar_button_hover_color=C["ACCENT2"])
        logs.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        w["logs"] = logs

    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab_folders(self, parent):
        C = self.C
        w = self._widgets

        hint = ctk.CTkLabel(
            parent,
            text="Selectionnez les dossiers Windows a inclure dans la sauvegarde.",
            font=("Segoe UI", 12), text_color=C["MUTED"])
        hint.pack(anchor="w", padx=8, pady=(8, 4))
        w["folders_hint"] = hint

        sel_row = ctk.CTkFrame(parent, fg_color="transparent")
        sel_row.pack(anchor="w", padx=8, pady=(0, 8))

        sel_all = ctk.CTkButton(
            sel_row, text="Tout selectionner", width=160, height=30,
            font=("Segoe UI", 11),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["ACCENT"],
            text_color=C["ACCENT"], corner_radius=8,
            command=self._select_all_folders)
        sel_all.pack(side="left", padx=(0, 8))
        w["sel_all_f"] = sel_all

        desel_all = ctk.CTkButton(
            sel_row, text="Tout deselectionner", width=160, height=30,
            font=("Segoe UI", 11),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["MUTED"],
            text_color=C["MUTED"], corner_radius=8,
            command=self._deselect_all_folders)
        desel_all.pack(side="left")
        w["desel_all_f"] = desel_all

        fg = ctk.CTkFrame(parent, fg_color=C["CARD"])
        fg.pack(fill="x", padx=8, pady=(0, 12))
        fg.grid_columnconfigure(0, weight=1)
        fg.grid_columnconfigure(1, weight=1)
        w["folders_grid"] = fg

        for idx, (key, _names, _fb) in enumerate(self.FOLDER_DEFS):
            r, col = idx // 2, idx % 2
            cell = ctk.CTkFrame(
                fg, fg_color=C["CARD2"], corner_radius=10,
                border_width=1, border_color=C["BORDER"])
            cell.grid(row=r, column=col, sticky="ew", padx=5, pady=5)
            w["folder_cell_" + key] = cell

            ci = ctk.CTkFrame(cell, fg_color=C["CARD2"])
            ci.pack(fill="x", padx=12, pady=10)
            w["folder_inner_" + key] = ci

            cb = ctk.CTkCheckBox(
                ci, text=self.FOLDER_LABELS.get(key, key),
                font=("Segoe UI", 13, "bold"), text_color=C["TEXT"],
                fg_color=C["ACCENT"], hover_color=C["ACCENT2"],
                checkmark_color="#ffffff",
                border_color=C["BORDER"], corner_radius=6)
            cb.select()
            cb.pack(side="left")
            self.folder_checkboxes[key] = cb

    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab_browsers(self, parent):
        C = self.C
        w = self._widgets

        hint = ctk.CTkLabel(
            parent,
            text="Chaque navigateur detecte automatiquement tous ses profils. "
                 "Cochez ce que vous souhaitez sauvegarder.",
            font=("Segoe UI", 12), text_color=C["MUTED"], wraplength=900)
        hint.pack(anchor="w", padx=8, pady=(8, 8))
        w["browsers_hint"] = hint

        sel_row = ctk.CTkFrame(parent, fg_color="transparent")
        sel_row.pack(anchor="w", padx=8, pady=(0, 8))

        bm_all = ctk.CTkButton(
            sel_row, text="Tous favoris", width=140, height=30,
            font=("Segoe UI", 11),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["TEAL"],
            text_color=C["TEAL"], corner_radius=8,
            command=self._select_all_bookmarks)
        bm_all.pack(side="left", padx=(0, 8))
        w["bm_all_btn"] = bm_all

        pw_all = ctk.CTkButton(
            sel_row, text="Tous mots de passe", width=160, height=30,
            font=("Segoe UI", 11),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["ORANGE"],
            text_color=C["ORANGE"], corner_radius=8,
            command=self._select_all_passwords)
        pw_all.pack(side="left", padx=(0, 8))
        w["pw_all_btn"] = pw_all

        bm_none = ctk.CTkButton(
            sel_row, text="Tout decocher", width=130, height=30,
            font=("Segoe UI", 11),
            fg_color=C["CARD2"], hover_color=C["BORDER"],
            border_width=1, border_color=C["MUTED"],
            text_color=C["MUTED"], corner_radius=8,
            command=self._deselect_all_browsers)
        bm_none.pack(side="left")
        w["bm_none_btn"] = bm_none



        browsers = get_browser_paths()

        ng = ctk.CTkFrame(parent, fg_color=C["CARD"])
        ng.pack(fill="both", expand=True, padx=8, pady=(0, 12))
        ng.grid_columnconfigure(0, weight=0, minsize=170)
        ng.grid_columnconfigure(1, weight=1)
        ng.grid_columnconfigure(2, weight=1)
        w["nav_grid"] = ng

        h0 = ctk.CTkLabel(ng, text="Navigateur",
            font=("Segoe UI", 12, "bold"), text_color=C["MUTED"])
        h0.grid(row=0, column=0, sticky="w", padx=(6, 0), pady=(0, 6))
        w["nav_h0"] = h0

        h1 = ctk.CTkLabel(ng, text="⭐  Favoris",
            font=("Segoe UI", 12, "bold"), text_color=C["TEAL"])
        h1.grid(row=0, column=1, sticky="w", padx=6, pady=(0, 6))
        w["nav_h1"] = h1

        h2 = ctk.CTkLabel(ng, text="🔑  Mots de passe",
            font=("Segoe UI", 12, "bold"), text_color=C["ORANGE"])
        h2.grid(row=0, column=2, sticky="w", padx=6, pady=(0, 6))
        w["nav_h2"] = h2

        for ri, (bname, binfo) in enumerate(browsers.items(), start=1):
            installed   = binfo["base"].exists()
            txt_col     = C["TEXT"]   if installed else C["MUTED"]
            cell_bg     = C["CARD2"]  if installed else C["BG"]
            cell_border = C["BORDER"] if installed else C["CARD2"]

            nc = ctk.CTkFrame(ng, fg_color=cell_bg, corner_radius=8,
                border_width=1, border_color=cell_border)
            nc.grid(row=ri, column=0, sticky="ew", padx=(0, 4), pady=3)
            w["nav_cell_" + bname] = nc
            nci = ctk.CTkFrame(nc, fg_color=cell_bg)
            nci.pack(fill="x", padx=10, pady=7)
            w["nav_inner_" + bname] = nci
            _la = ctk.CTkLabel(nci, text=bname[:2].upper(),
                font=("Segoe UI", 11), width=24, text_color=txt_col)
            _la.pack(side="left", padx=(0, 8))
            w["nav_lbl_abbr_" + bname] = _la
            _ln = ctk.CTkLabel(nci, text=bname,
                font=("Segoe UI", 12, "bold"), text_color=txt_col)
            _ln.pack(side="left")
            w["nav_lbl_name_" + bname] = _ln
            if installed:
                _lok = ctk.CTkLabel(nci, text="[OK]",
                    font=("Segoe UI", 8), text_color=C["SUCCESS"])
                _lok.pack(side="right", padx=(4, 0))
                w["nav_lbl_ok_" + bname] = _lok

            fc2 = ctk.CTkFrame(ng, fg_color=cell_bg, corner_radius=8,
                border_width=1, border_color=cell_border)
            fc2.grid(row=ri, column=1, sticky="ew", padx=4, pady=3)
            w["nav_fav_" + bname] = fc2
            cbf = ctk.CTkCheckBox(
                fc2, text="Sauvegarder les favoris",
                font=("Segoe UI", 12), text_color=txt_col,
                fg_color=C["TEAL"], hover_color=C["ACCENT2"],
                checkmark_color="#ffffff", border_color=C["BORDER"],
                corner_radius=5,
                state="normal" if installed else "disabled")
            cbf.pack(anchor="w", padx=12, pady=8)
            self.browser_bookmark_cbs[bname] = cbf

            pc = ctk.CTkFrame(ng, fg_color=cell_bg, corner_radius=8,
                border_width=1, border_color=cell_border)
            pc.grid(row=ri, column=2, sticky="ew", padx=(4, 0), pady=3)
            w["nav_pwd_" + bname] = pc
            cbp = ctk.CTkCheckBox(
                pc, text="Sauvegarder les mots de passe",
                font=("Segoe UI", 12), text_color=txt_col,
                fg_color=C["ORANGE"], hover_color=C["ACCENT2"],
                checkmark_color="#ffffff", border_color=C["BORDER"],
                corner_radius=5,
                state="normal" if installed else "disabled")
            cbp.pack(anchor="w", padx=12, pady=8)
            self.browser_password_cbs[bname] = cbp

    # ─────────────────────────────────────────────────────────────────────────
    #  Sélection / désélection
    # ─────────────────────────────────────────────────────────────────────────

    def _select_all_folders(self):
        for cb in self.folder_checkboxes.values():
            try:
                cb.select()
            except Exception:
                pass

    def _deselect_all_folders(self):
        for cb in self.folder_checkboxes.values():
            try:
                cb.deselect()
            except Exception:
                pass

    def _select_all_bookmarks(self):
        for cb in self.browser_bookmark_cbs.values():
            try:
                if cb.cget("state") != "disabled":
                    cb.select()
            except Exception:
                pass

    def _select_all_passwords(self):
        for cb in self.browser_password_cbs.values():
            try:
                if cb.cget("state") != "disabled":
                    cb.select()
            except Exception:
                pass

    def _deselect_all_browsers(self):
        all_cbs = (list(self.browser_bookmark_cbs.values()) +
                   list(self.browser_password_cbs.values()))
        for cb in all_cbs:
            try:
                if cb.cget("state") != "disabled":
                    cb.deselect()
            except Exception:
                pass

    def _toggle_all_browsers(self):
        """Bascule tout cocher / tout decocher (favoris + mots de passe)."""
        any_checked = any(
            cb.get() == 1
            for cbs in (self.browser_bookmark_cbs, self.browser_password_cbs)
            for cb in cbs.values()
        )
        btn = self._widgets.get("toggle_all_browsers")
        if any_checked:
            self._deselect_all_browsers()
            if btn:
                try:
                    btn.configure(text="☑  Tout cocher")
                except Exception:
                    pass
        else:
            self._select_all_bookmarks()
            self._select_all_passwords()
            if btn:
                try:
                    btn.configure(text="☐  Tout decocher")
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────────────────
    #  USB
    # ─────────────────────────────────────────────────────────────────────────

    def _auto_detect_usb(self):
        drives = detect_removable_drives()
        usb_lbl = self._widgets.get("usb_label")
        if usb_lbl is None:
            return
        if not drives:
            self._safe_cfg(usb_lbl, text="Aucun lecteur amovible detecte.")
            return
        d = drives[0]
        self.after(0, lambda: self.destination.set(d["letter"]))
        if len(drives) == 1:
            msg = "USB detecte : {}  ({} libres / {})".format(
                d["label"], format_size(d["free"]), format_size(d["total"]))
        else:
            parts = "  |  ".join(
                "{} ({})".format(x["label"], format_size(x["free"]))
                for x in drives)
            msg = "{} lecteurs detectes : {}".format(len(drives), parts)
        self._safe_cfg(usb_lbl, text=msg)
        self.log(msg)

    # ─────────────────────────────────────────────────────────────────────────
    #  Helpers UI
    # ─────────────────────────────────────────────────────────────────────────

    def select_folder(self):
        """Ouvre le selecteur en pointant sur le dossier actuel si deja rempli."""
        current = self.destination.get()
        # initialdir = dossier actuel s'il existe, sinon racine
        init_dir = current if current and Path(current).exists() else "/"
        folder = filedialog.askdirectory(initialdir=init_dir, parent=self)
        if folder:
            self.destination.set(folder)

    def _clear_log(self):
        try:
            self._widgets["logs"].delete("1.0", "end")
        except Exception:
            pass
        self._log_lines.clear()
        self._error_lines.clear()

    def log(self, message):
        # type: (str) -> None
        ts   = datetime.now().strftime("%H:%M:%S")
        line = "[{}] {}".format(ts, message)
        self._log_lines.append(line)
        if any(t in message for t in ("[ERREUR]", "[HASH FAIL]", "[ECHEC]")):
            self._error_lines.append(line)
        # Journalisation en temps reel : ecriture immediate si migration active
        # Ainsi, si crash, les logs jusqu'au plantage sont sauvegardes.
        if self._realtime_log_path:
            write_log_file(self._realtime_log_path, message)
        self.after(0, self._log_ui, line)

    def _log_ui(self, line):
        # type: (str) -> None
        try:
            self._widgets["logs"].insert("end", line + "\n")
            self._widgets["logs"].see("end")
        except Exception:
            pass

    def cancel_task(self):
        self.cancel_requested = True
        self.log("Annulation demandee...")
        self._safe_cfg(self._widgets.get("status_label"),
                       text="Annulation en cours...")

    def _update_disk_info(self):
        dest = self.destination.get()
        disk_lbl = self._widgets.get("disk_label")
        if disk_lbl is None:
            return
        if not dest:
            self._safe_cfg(disk_lbl,
                text="Selectionnez d'abord une destination.",
                text_color=self.C["MUTED"])
            return
        try:
            _, _, free = get_disk_usage(Path(dest))
            ok    = free >= self.total_size if self.total_size else True
            color = self.C["SUCCESS"] if ok else self.C["RED"]
            sym   = "[OK]" if ok else "[!]"
            self._safe_cfg(disk_lbl,
                text="Requis : {}  |  Disponible : {}  {}".format(
                    format_size(self.total_size), format_size(free), sym),
                text_color=color)
        except Exception as e:
            self._safe_cfg(disk_lbl,
                text="Impossible de verifier : {}".format(e),
                text_color=self.C["WARN"])

    # ─────────────────────────────────────────────────────────────────────────
    #  Analyse
    # ─────────────────────────────────────────────────────────────────────────

    def start_analysis(self):
        self.cancel_requested = False
        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _run_analysis(self):
        tree = self._widgets.get("tree")
        if tree is None:
            return
        self.after(0, lambda: tree.delete(*tree.get_children()))
        self.total_files = 0
        self.total_size  = 0
        self._folder_stats.clear()

        selected = [n for n, cb in self.folder_checkboxes.items() if cb.get() == 1]
        if not selected:
            self.log("Aucun dossier selectionne.")
            return

        self.log("Analyse demarree...")
        self._safe_cfg(self._widgets.get("status_label"), text="Analyse en cours...")
        count = len(selected)

        for idx, folder_name in enumerate(selected):
            if self.cancel_requested:
                self._safe_cfg(self._widgets.get("status_label"), text="Analyse annulee")
                return
            path = self.folders[folder_name]
            self.log("Analyse de {}...".format(folder_name))
            fc, sz = scan_folder(path, cancel_check=lambda: self.cancel_requested)
            self.total_files += fc
            self.total_size  += sz
            self._folder_stats[folder_name] = (fc, sz)
            row = (folder_name, "{:,}".format(fc), format_size(sz))
            self.after(0, lambda v=row: tree.insert("", "end", values=v))
            p = (idx + 1) / count
            self.after(0, lambda v=p: self._widgets["progress"].set(v))

        self.after(0, self._update_disk_info)
        self.after(0, lambda: self._widgets["total_label"].configure(
            text="Total : {:,} fichiers | {}".format(
                self.total_files, format_size(self.total_size))))
        self._safe_cfg(self._widgets.get("status_label"), text="Analyse terminee")
        self.log("Analyse terminee.")

    # ─────────────────────────────────────────────────────────────────────────
    #  Migration
    # ─────────────────────────────────────────────────────────────────────────

    def start_migration(self):
        if not self.destination.get():
            self.log("Veuillez selectionner une destination.")
            return
        # Avertissement si destination = racine du lecteur système (C:\)
        dest = self.destination.get().strip()
        is_system_root = (
            os.name == "nt" and
            len(dest) == 2 and dest[1] == ":" and dest[0].upper() == "C"
        )
        if is_system_root:
            try:
                confirm = messagebox.askyesno(
                    "Attention - Destination risquee",
                    "Vous avez selectionne C: comme destination."
                    " Ecrire sur C: peut creer des conflits Windows."
                    " Voulez-vous continuer malgre tout ?",
                    icon="warning", parent=self)
            except Exception:
                confirm = True
            if not confirm:
                self.log("Migration annulee par l'utilisateur.")
                return
        # Lancer l'analyse automatiquement si elle n'a pas été faite
        if self.total_files == 0:
            self.log("Analyse non lancee — analyse automatique avant migration...")
            # On bloque le démarrage et on enchaîne analyse puis migration
            self.dry_run_mode     = False
            self.cancel_requested = False
            threading.Thread(target=self._run_analysis_then_migrate, daemon=True).start()
            return
        self.dry_run_mode     = False
        self.cancel_requested = False
        threading.Thread(target=self._run_migration, daemon=True).start()

    def start_dry_run(self):
        if not self.destination.get():
            self.log("Veuillez selectionner une destination.")
            return
        self.dry_run_mode     = True
        self.cancel_requested = False
        threading.Thread(target=self._run_migration, daemon=True).start()

    def _run_analysis_then_migrate(self):
        """Lance l'analyse puis enchaine automatiquement sur la migration."""
        self._run_analysis()
        if not self.cancel_requested and self.total_files > 0:
            self._run_migration()

    def _create_migration_folder(self):
        # type: () -> Path
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        mf = Path(self.destination.get()) / ("Migration_" + ts)
        (mf / "Logs").mkdir(parents=True, exist_ok=True)
        (mf / "Rapport").mkdir(exist_ok=True)
        return mf

    def _run_migration(self):
        # Remise à zéro complète de l'UI entre deux migrations consécutives
        progress = self._widgets.get("progress")
        if progress:
            self.after(0, lambda: progress.set(0))
        tree = self._widgets.get("tree")
        if tree:
            self.after(0, lambda: tree.delete(*tree.get_children()))
        self.after(0, lambda: self._widgets["total_label"].configure(
            text="Total : 0 fichier | 0 Mo") if "total_label" in self._widgets else None)
        self.copied_files  = 0
        self.skipped_files = 0
        self._error_lines.clear()

        status = "Simulation en cours..." if self.dry_run_mode else "Migration en cours..."
        self._safe_cfg(self._widgets.get("status_label"), text=status)
        if self.dry_run_mode:
            self.log("[SIMULATION] Aucun fichier ne sera copie.")

        mf        = self._create_migration_folder()
        log_file  = mf / "Logs"    / "migration.log"
        rep_json  = mf / "Rapport" / "migration_report.json"
        rep_pdf   = mf / "Rapport" / "migration_report.pdf"

        self.log("Dossier de migration : {}".format(mf))
        # Activer la journalisation en temps reel pour ce fichier
        self._realtime_log_path = log_file
        write_log_file(log_file, "Debut migration")

        selected = [n for n, cb in self.folder_checkboxes.items() if cb.get() == 1]

        if not self.dry_run_mode and self.total_size > 0:
            ok, free = check_space(self.total_size, Path(self.destination.get()))
            if not ok:
                msg = ("Espace insuffisant !  "
                       "Requis : {}  |  Disponible : {}".format(
                           format_size(self.total_size), format_size(free)))
                self.log(msg)
                write_log_file(log_file, msg)
                self._safe_cfg(self._widgets.get("status_label"),
                               text="Espace insuffisant !")
                return

        for folder_name in selected:
            if self.cancel_requested:
                break
            src  = self.folders[folder_name]
            dst  = mf / folder_name
            self.log("Copie de {}".format(folder_name))
            write_log_file(log_file, "Copie {}".format(folder_name))
            self._copy_folder(src, dst, log_file)

        if not self.cancel_requested:
            self.log("Copie des donnees navigateurs...")
            self._copy_browser_data(mf, log_file)

        src_paths = ", ".join(
            str(self.folders[n]) for n in selected if n in self.folders)
        self._generate_json_report(rep_json)

        if HAS_FPDF:
            # Navigateurs effectivement coches pour cette migration
            browsers_backup = []
            for bname in get_browser_paths().keys():
                fav_cb = self.browser_bookmark_cbs.get(bname)
                pwd_cb = self.browser_password_cbs.get(bname)
                fav_sel = bool(fav_cb and fav_cb.get() == 1)
                pwd_sel = bool(pwd_cb and pwd_cb.get() == 1)
                if fav_sel or pwd_sel:
                    browsers_backup.append((bname, fav_sel, pwd_sel))

            ok_pdf = generate_pdf_report(
                rep_pdf, self.logo_path,
                {
                    "date":             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source":           src_paths or "-",
                    "destination":      self.destination.get(),
                    "dry_run":          self.dry_run_mode,
                    "verify":           self.verify_hashes,
                    "files_detected":   self.total_files,
                    "files_copied":     self.copied_files,
                    "files_skipped":    self.skipped_files,
                    "total_size_human": format_size(self.total_size),
                },
                self._log_lines, self._error_lines,
                folder_stats=self._folder_stats,
                selected_folders=selected,
                browsers_backup=browsers_backup)
            self.log(
                "Rapport PDF genere : {}".format(rep_pdf) if ok_pdf
                else "Erreur lors de la generation du rapport PDF.")
        else:
            self.log("fpdf2 non installe - rapport PDF ignore (pip install fpdf2).")

        write_log_file(log_file, "Fin migration")

        if self.cancel_requested:
            end = "Simulation annulee" if self.dry_run_mode else "Migration annulee"
            self._safe_cfg(self._widgets.get("status_label"), text=end)
            self.log(end + ".")
        else:
            if progress:
                self.after(0, lambda: progress.set(1))
            end = "Simulation terminee" if self.dry_run_mode else "Migration terminee"
            self._safe_cfg(self._widgets.get("status_label"), text=end)
            self.log("{}. {} copie(s), {} ignore(s), {}.".format(
                end, self.copied_files, self.skipped_files,
                format_size(self.total_size)))
            self._realtime_log_path = None   # arreter le log temps-reel
            # Notification de fin — messagebox thread-safe via after()
            self.after(0, self._notify_done)

    # ─────────────────────────────────────────────────────────────────────────
    def _notify_done(self):
        """Affiche une boite de dialogue de fin de migration (thread-safe via after)."""
        mode  = "SIMULATION" if self.dry_run_mode else "Migration"
        skips = self.skipped_files
        title = "{} terminee".format(mode)
        msg   = (
            "{} terminee avec succes !\n\n"
            "   Fichiers copies  : {:,}\n"
            "   Fichiers ignores : {:,}\n"
            "   Taille totale    : {}"
        ).format(
            mode,
            self.copied_files,
            skips,
            format_size(self.total_size)
        )
        if skips > 0:
            msg += "\n\n{} fichier(s) n'ont pas pu etre copies.".format(skips)
        try:
            if skips > 0:
                messagebox.showwarning(title, msg, parent=self)
            else:
                messagebox.showinfo(title, msg, parent=self)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    def _copy_folder(self, source, destination, log_path):
        # type: (Path, Path, Path) -> bool
        if not source.exists():
            return False
        if self.dry_run_mode:
            self.log("[SIMULATION] Copierait : {}".format(source))
            return True
        destination.mkdir(parents=True, exist_ok=True)
        for root, _dirs, files in os.walk(str(source)):
            if self.cancel_requested:
                return False
            rel      = os.path.relpath(root, str(source))
            target_d = destination / rel
            target_d.mkdir(parents=True, exist_ok=True)
            for ffile in files:
                if self.cancel_requested:
                    return False
                src_f = Path(root) / ffile
                dst_f = target_d   / ffile
                ok = copy_with_retry(src_f, dst_f,
                    log_cb=self.log, verify=self.verify_hashes)
                if ok:
                    self.copied_files += 1
                else:
                    self.skipped_files += 1
                    write_log_file(log_path, "[ECHEC] {}".format(src_f))
                if self.total_files > 0:
                    pval = self.copied_files / self.total_files
                    progress = self._widgets.get("progress")
                    if progress:
                        self.after(0, lambda v=pval: progress.set(v))
                self.after(0, lambda f=ffile: self._safe_cfg(
                    self._widgets.get("status_label"),
                    text="Copie : {}  -  {} / {} fichiers".format(
                        f, self.copied_files, self.total_files)))
        return True

    # ─────────────────────────────────────────────────────────────────────────
    def _copy_browser_data(self, migration_folder, log_path):
        # type: (Path, Path) -> None
        browsers = get_browser_paths()

        def _cp(src, dest_base, bname, lbl):
            if self.dry_run_mode:
                self.log("[SIMULATION] {} {} -> {}".format(lbl, bname, src.name))
                return
            if src.is_dir():
                try:
                    shutil.copytree(str(src), str(dest_base / src.name))
                    self.copied_files += 1
                    write_log_file(log_path, "[{}] {} : {}".format(lbl, bname, src))
                except Exception as e:
                    self.log("[ERREUR {}] {}/{} : {}".format(lbl, bname, src.name, e))
            else:
                ok = copy_with_retry(src, dest_base / src.name,
                    log_cb=self.log, verify=self.verify_hashes)
                if ok:
                    self.copied_files += 1
                    write_log_file(log_path, "[{}] {} : {}".format(lbl, bname, src))
                else:
                    self.skipped_files += 1
            if self.total_files > 0:
                pval = min(self.copied_files / max(self.total_files, 1), 1.0)
                progress = self._widgets.get("progress")
                if progress:
                    self.after(0, lambda v=pval: progress.set(v))

        def _profile_subdir(src_path, base_path):
            """Retourne le sous-dossier de profil relatif (ex: 'Default', 'Profile 1').
            Permet de séparer les profils multiples dans la destination."""
            try:
                rel = src_path.relative_to(base_path)
                parts = rel.parts
                # Pour Chromium : parts[0] est 'Default' ou 'Profile X'
                # Pour Firefox  : parts[0] est 'xxxxxxxx.default-release'
                if len(parts) >= 1:
                    return parts[0]
            except (ValueError, IndexError):
                pass
            return "Default"

        for bname, cb in self.browser_bookmark_cbs.items():
            if cb.get() != 1 or self.cancel_requested:
                continue
            binfo = browsers[bname]
            files = collect_browser_files(bname, binfo, "bookmarks")
            if not files:
                self.log("[Favoris] {} : aucun fichier trouve".format(bname))
                continue
            for src_f in files:
                # Dossier cible séparé par profil pour éviter les écrasements
                profile = _profile_subdir(src_f, binfo["base"])
                d = migration_folder / "Navigateurs" / bname / "Favoris" / profile
                d.mkdir(parents=True, exist_ok=True)
                _cp(src_f, d, bname, "Favoris")

        for bname, cb in self.browser_password_cbs.items():
            if cb.get() != 1 or self.cancel_requested:
                continue
            binfo = browsers[bname]
            files = collect_browser_files(bname, binfo, "passwords")
            if not files:
                self.log("[MDP] {} : aucun fichier trouve".format(bname))
                continue
            for src_f in files:
                profile = _profile_subdir(src_f, binfo["base"])
                d = migration_folder / "Navigateurs" / bname / "MotsDePasse" / profile
                d.mkdir(parents=True, exist_ok=True)
                _cp(src_f, d, bname, "MDP")

    # ─────────────────────────────────────────────────────────────────────────
    def _generate_json_report(self, report_path):
        # type: (Path) -> None
        report = {
            "date":             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dry_run":          self.dry_run_mode,
            "verify_hashes":    self.verify_hashes,
            "destination":      self.destination.get(),
            "files_detected":   self.total_files,
            "files_copied":     self.copied_files,
            "files_skipped":    self.skipped_files,
            "total_size_bytes": self.total_size,
            "total_size_human": format_size(self.total_size),
            "errors":           self._error_lines,
        }
        try:
            with open(str(report_path), "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
        except OSError as e:
            self.log("Erreur rapport JSON : {}".format(e))

# =============================================================================
#  CONFIGURATION CTk — NIVEAU MODULE
# =============================================================================

# Configuration CTk — niveau module (avant toute instanciation)
_CTK_THEME = _auto_theme()
ctk.set_appearance_mode(_CTK_THEME)
ctk.set_default_color_theme("green")

if __name__ == "__main__":
    app = IASTRAL()
    app.mainloop()