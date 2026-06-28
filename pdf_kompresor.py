"""
PDF Kompresor — kompresja ciężkich PDF-ów (skany / plakaty / dużo zdjęć).

Silnik: PyMuPDF (rewrite_images) — recompresuje TYLKO obrazy, zostawiając
tekst i grafikę wektorową nietknięte (dlatego napisy i linie są zawsze ostre).

Dwa sposoby uruchomienia z tego samego kodu:
  * jako skrypt  -> biblioteka PyMuPDF leży w dołączonym folderze "libs",
  * jako .exe    -> PyInstaller wbudowuje PyMuPDF i Pythona w plik wykonywalny.

Licencja: AGPL-3.0 (bo używa PyMuPDF / MuPDF, Artifex Software). Patrz LICENSE.
"""

import os
import sys
import queue
import shutil
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

VERSION = "1.0"
FROZEN = getattr(sys, "frozen", False)
APP_DIR = (os.path.dirname(sys.executable) if FROZEN
           else os.path.dirname(os.path.abspath(__file__)))


def resource_path(name):
    """Ścieżka do zasobu (działa też w .exe z PyInstaller)."""
    base = getattr(sys, "_MEIPASS", APP_DIR)
    return os.path.join(base, name)


# Dołączona biblioteka PyMuPDF (folder "libs" obok skryptu) — tylko w trybie skryptu.
if not FROZEN:
    _LIBS = os.path.join(APP_DIR, "libs")
    if os.path.isdir(_LIBS) and _LIBS not in sys.path:
        sys.path.insert(0, _LIBS)

try:
    import pymupdf as fitz
except Exception:
    try:
        import fitz  # starsza nazwa
    except Exception:
        fitz = None

# ---------------------------------------------------------------------------
# Wygląd
# ---------------------------------------------------------------------------
BG       = "#16181d"
CARD     = "#1f232b"
FG       = "#e7e9ee"
MUTED    = "#9aa1ad"
ACCENT   = "#ff6a3d"
ACCENT_H = "#ff8159"
OK       = "#3ddc84"
ERR      = "#ff5d5d"
BORDER   = "#2c313b"

# Presety jakości -> (docelowe DPI, jakość JPEG 0-100) + opis.
# Obrazy powyżej (DPI + margines) są zmniejszane do "dpi" i przekodowane;
# mniejsze zostają nietknięte. Tekst/wektory zawsze pozostają ostre.
PRESETS = [
    ("super",   "Super (1:1)",  300, 95, "Druk-perfekt, do 300 DPI. Prawie bez strat."),
    ("wysoka",  "Wysoka",       300, 90, "Jakość do druku, 300 DPI. Zalecane."),
    ("srednia", "Średnia",      200, 85, "Na ekran / duże dokumenty, 200 DPI. Mocno mniejszy."),
    ("niska",   "Niska (mały)", 120, 72, "Maksymalna kompresja, 120 DPI. Najmniejszy."),
]

DPI_MARGIN = 12  # rewrite_images wymaga: dpi_target < dpi_threshold


def mb(num_bytes):
    return num_bytes / (1024 * 1024)


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"


def quality_for_dpi(dpi):
    """DPI -> sensowna jakość JPEG (tryb docelowego rozmiaru)."""
    q = 50 + (dpi - 60) / (300 - 60) * (95 - 50)
    return int(max(38, min(95, round(q))))


# ---------------------------------------------------------------------------
# Silnik kompresji (PyMuPDF)
# ---------------------------------------------------------------------------
def compress(src, dst, dpi, quality, gray=False):
    """Recompresuje obrazy w PDF. Zwraca rozmiar wynikowego pliku w bajtach."""
    doc = fitz.open(src)
    try:
        if doc.needs_pass:
            raise RuntimeError("PDF jest zabezpieczony hasłem — odblokuj go najpierw.")
        if not doc.is_pdf:
            raise RuntimeError("To nie jest plik PDF.")
        doc.rewrite_images(
            dpi_threshold=dpi + DPI_MARGIN,
            dpi_target=dpi,
            quality=quality,
            set_to_gray=gray,
        )
        try:
            doc.subset_fonts()
        except Exception:
            pass
        doc.save(dst, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()
    return os.path.getsize(dst)


# ---------------------------------------------------------------------------
# Aplikacja
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.src = None
        self.q = queue.Queue()
        self.busy = False
        self.last_output = None

        self.mode = tk.StringVar(value="jakosc")
        self.preset = tk.StringVar(value="wysoka")
        self.target_mb = tk.StringVar(value="20")
        self.gray = tk.BooleanVar(value=False)

        self._build_ui()
        self._poll_queue()
        if fitz is None:
            self.status.config(
                text="Brak silnika PyMuPDF. Uruchom przez plik .exe albo zostaw "
                     "folder „libs” obok skryptu.", fg=ERR)

    # --- UI ---------------------------------------------------------------
    def _build_ui(self):
        r = self.root
        r.title(f"PDF Kompresor {VERSION}")
        r.configure(bg=BG)
        r.geometry("620x700")
        r.minsize(560, 650)
        try:
            ico = resource_path("icon.ico")
            if os.path.exists(ico):
                r.iconbitmap(ico)
        except Exception:
            pass

        style = ttk.Style(r)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TProgressbar", troughcolor=CARD, background=ACCENT,
                        bordercolor=CARD, thickness=14)

        wrap = tk.Frame(r, bg=BG)
        wrap.pack(fill="both", expand=True, padx=22, pady=20)

        tk.Label(wrap, text="PDF Kompresor", bg=BG, fg=FG,
                 font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(wrap, text="Zmniejsz ciężki PDF — maks. jakość, zdjęcia i tekst bez strat.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 16))

        # --- karta: plik ---
        filecard = self._card(wrap)
        self.file_lbl = tk.Label(filecard, text="Nie wybrano pliku",
                                 bg=CARD, fg=MUTED, font=("Segoe UI", 10),
                                 anchor="w", justify="left", wraplength=420)
        self.file_lbl.pack(side="left", fill="x", expand=True, padx=(14, 10), pady=14)
        self._btn(filecard, "Wybierz PDF", self.pick_file, primary=False).pack(
            side="right", padx=(0, 12), pady=12)

        # --- karta: tryb ---
        modecard = self._card(wrap, pady=(12, 0))
        inner = tk.Frame(modecard, bg=CARD)
        inner.pack(fill="x", padx=14, pady=14)

        self._radio(inner, "Wybierz jakość", "jakosc").pack(anchor="w")
        self.preset_box = tk.Frame(inner, bg=CARD)
        self.preset_box.pack(fill="x", padx=24, pady=(4, 10))
        for key, label, _dpi, _q, desc in PRESETS:
            row = tk.Frame(self.preset_box, bg=CARD)
            row.pack(fill="x", anchor="w", pady=2)
            tk.Radiobutton(row, text=label, value=key, variable=self.preset,
                           bg=CARD, fg=FG, selectcolor=CARD, activebackground=CARD,
                           activeforeground=FG, font=("Segoe UI Semibold", 10),
                           highlightthickness=0, bd=0, anchor="w",
                           command=lambda: self.mode.set("jakosc")).pack(side="left")
            tk.Label(row, text="  " + desc, bg=CARD, fg=MUTED,
                     font=("Segoe UI", 9)).pack(side="left")

        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=(2, 8))

        self._radio(inner, "Docelowy rozmiar pliku", "rozmiar").pack(anchor="w")
        trow = tk.Frame(inner, bg=CARD)
        trow.pack(fill="x", padx=24, pady=(6, 2))
        tk.Label(trow, text="Maks. rozmiar:", bg=CARD, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        ent = tk.Entry(trow, textvariable=self.target_mb, width=7, justify="center",
                       bg=BG, fg=FG, insertbackground=FG, relief="flat",
                       font=("Segoe UI", 11), highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ACCENT)
        ent.pack(side="left", padx=8, ipady=3)
        ent.bind("<FocusIn>", lambda e: self.mode.set("rozmiar"))
        tk.Label(trow, text="MB", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(inner, text="Skrypt sam dobierze DPI, by zmieścić plik w limicie "
                 "przy najlepszej jakości.", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(4, 0))

        # --- opcja: skala szarości ---
        tk.Checkbutton(wrap, text="Konwertuj do skali szarości (jeszcze mniejszy plik)",
                       variable=self.gray, bg=BG, fg=MUTED, selectcolor=CARD,
                       activebackground=BG, activeforeground=FG, anchor="w",
                       font=("Segoe UI", 9), highlightthickness=0, bd=0).pack(
            anchor="w", pady=(12, 0))

        # --- akcja ---
        self.go_btn = self._btn(wrap, "Kompresuj", self.start, primary=True)
        self.go_btn.pack(fill="x", pady=(12, 10), ipady=6)

        self.bar = ttk.Progressbar(wrap, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=(2, 6))
        self.status = tk.Label(wrap, text="", bg=BG, fg=MUTED, font=("Segoe UI", 10),
                               anchor="w", justify="left", wraplength=540)
        self.status.pack(fill="x")

        self.open_btn = self._btn(wrap, "Otwórz folder z plikiem",
                                  self.open_folder, primary=False)
        # pokazywany dopiero po sukcesie

        tk.Label(wrap, text=f"v{VERSION} · silnik PyMuPDF (AGPL-3.0)", bg=BG, fg=BORDER,
                 font=("Segoe UI", 8)).pack(side="bottom", anchor="e", pady=(8, 0))

    def _card(self, parent, pady=(0, 0)):
        f = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        f.pack(fill="x", pady=pady)
        return f

    def _radio(self, parent, text, value):
        return tk.Radiobutton(parent, text=text, value=value, variable=self.mode,
                              bg=CARD, fg=FG, selectcolor=CARD, activebackground=CARD,
                              activeforeground=ACCENT, font=("Segoe UI Semibold", 11),
                              highlightthickness=0, bd=0, anchor="w")

    def _btn(self, parent, text, cmd, primary):
        bg = ACCENT if primary else "#2a2f39"
        fg = "#1a1208" if primary else FG
        hov = ACCENT_H if primary else "#343b47"
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, bd=0,
                      relief="flat", activebackground=hov, activeforeground=fg,
                      font=("Segoe UI Semibold", 11), cursor="hand2",
                      padx=16, pady=6)
        b.bind("<Enter>", lambda e: b.config(bg=hov) if str(b["state"]) != "disabled" else None)
        b.bind("<Leave>", lambda e: b.config(bg=bg) if str(b["state"]) != "disabled" else None)
        return b

    # --- akcje ------------------------------------------------------------
    def pick_file(self):
        path = filedialog.askopenfilename(
            title="Wybierz plik PDF",
            filetypes=[("Pliki PDF", "*.pdf"), ("Wszystkie pliki", "*.*")])
        if path:
            self.src = path
            size = mb(os.path.getsize(path))
            self.file_lbl.config(
                text=f"{os.path.basename(path)}\n{size:.1f} MB", fg=FG)
            self.open_btn.pack_forget()
            self.status.config(text="", fg=MUTED)
            self.bar["value"] = 0

    def start(self):
        if self.busy:
            return
        if fitz is None:
            messagebox.showerror("Brak silnika",
                                 "Nie znaleziono PyMuPDF. Uruchom przez plik .exe "
                                 "albo zostaw folder „libs” obok skryptu.")
            return
        if not self.src:
            messagebox.showwarning("Brak pliku", "Najpierw wybierz plik PDF.")
            return
        target = None
        if self.mode.get() == "rozmiar":
            try:
                target = float(self.target_mb.get().replace(",", "."))
                if target <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Błędny rozmiar",
                                       "Podaj docelowy rozmiar w MB (np. 20).")
                return

        self.busy = True
        self.go_btn.config(state="disabled", text="Pracuję...")
        self.open_btn.pack_forget()
        self.bar.config(mode="indeterminate")
        self.bar.start(14)
        self.status.config(text="Przygotowanie...", fg=MUTED)

        t = threading.Thread(target=self._work, args=(target,), daemon=True)
        t.start()

    def _work(self, target):
        try:
            src = self.src
            base, _ = os.path.splitext(src)
            orig = os.path.getsize(src)
            gray = self.gray.get()

            if target is None:
                key = self.preset.get()
                _k, label, dpi, q, _d = next(p for p in PRESETS if p[0] == key)
                dst = unique_path(f"{base}_skompresowany.pdf")
                self.q.put(("status",
                            f"Kompresja obrazów ({label})... to może chwilę potrwać.", MUTED))
                compress(src, dst, dpi, q, gray)
                self._finish(orig, dst)
            else:
                self._work_target(src, base, orig, target, gray)
        except Exception as e:
            self.q.put(("error", str(e)))

    def _work_target(self, src, base, orig, target_mb, gray):
        """Binary search po DPI -> najwyższa jakość mieszcząca się w limicie."""
        target_bytes = target_mb * 1024 * 1024
        tmpdir = tempfile.mkdtemp(prefix="pdfkompresor_")
        lo, hi = 60, 300
        best = None
        smallest = None
        attempt = 0
        max_attempts = 6
        try:
            while lo <= hi and attempt < max_attempts:
                attempt += 1
                dpi = (lo + hi) // 2
                q = quality_for_dpi(dpi)
                tmp = os.path.join(tmpdir, f"try_{dpi}.pdf")
                self.q.put(("status",
                            f"Próba {attempt}: DPI {dpi} (jakość {q})...", MUTED))
                size = compress(src, tmp, dpi, q, gray)
                self.q.put(("status",
                            f"Próba {attempt}: DPI {dpi} -> {mb(size):.1f} MB", MUTED))
                if smallest is None or size < smallest[2]:
                    smallest = (dpi, tmp, size)
                if size <= target_bytes:
                    if best is None or dpi > best[0]:
                        best = (dpi, tmp, size)
                    lo = dpi + 1
                else:
                    hi = dpi - 1

            chosen = best or smallest
            dst = unique_path(f"{base}_max{int(target_mb)}MB.pdf")
            shutil.copyfile(chosen[1], dst)
            note = None
            if best is None:
                note = (f"Nie udało się zejść do {target_mb:.0f} MB nawet przy "
                        f"DPI 60 — zapisano najmniejszy możliwy wynik.")
            self._finish(orig, dst, note=note)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _finish(self, orig, dst, note=None):
        new = os.path.getsize(dst)
        saved = (1 - new / orig) * 100 if orig else 0
        self.last_output = dst
        if new >= orig:
            msg = (f"Gotowe, ale plik nie zmalał ({mb(orig):.1f} MB -> {mb(new):.1f} MB).\n"
                   f"Ten PDF ma mało obrazów do kompresji albo są już małe.\n"
                   f"{os.path.basename(dst)}")
        else:
            msg = (f"Gotowe!  {mb(orig):.1f} MB  ->  {mb(new):.1f} MB"
                   f"   (oszczędność {saved:.0f}%)\n{os.path.basename(dst)}")
        if note:
            msg += "\n" + note
        self.q.put(("done", msg))

    # --- komunikacja wątek -> UI -----------------------------------------
    def _poll_queue(self):
        try:
            while True:
                kind, *payload = self.q.get_nowait()
                if kind == "status":
                    text, color = payload
                    self.status.config(text=text, fg=color)
                elif kind == "done":
                    self.bar.stop()
                    self.bar.config(mode="determinate")
                    self.bar["value"] = 100
                    self.status.config(text=payload[0], fg=OK)
                    self._reset_btn()
                    self.open_btn.pack(fill="x", pady=(4, 0), ipady=4)
                elif kind == "error":
                    self.bar.stop()
                    self.bar.config(mode="determinate")
                    self.bar["value"] = 0
                    self.status.config(text="Błąd: " + payload[0], fg=ERR)
                    self._reset_btn()
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _reset_btn(self):
        self.busy = False
        self.go_btn.config(state="normal", text="Kompresuj", bg=ACCENT)

    def open_folder(self):
        if self.last_output and os.path.exists(self.last_output):
            subprocess.run(["explorer", "/select,",
                            os.path.normpath(self.last_output)])


def _selftest(args):
    """Nieinteraktywny test silnika. Uzycie: --selftest [wejscie.pdf wyjscie.pdf]
    Wynik zapisywany do %TEMP%\\pdfk_selftest.txt."""
    import time
    res = os.path.join(tempfile.gettempdir(), "pdfk_selftest.txt")
    out = [f"version={VERSION}", f"frozen={FROZEN}", f"fitz_ok={fitz is not None}"]
    try:
        if fitz is not None:
            out.append("pymupdf=" + str(fitz.VersionBind))
        if len(args) >= 2:
            t = time.time()
            sz = compress(args[0], args[1], 300, 90)
            out.append(f"compress_ok=1 size={sz} secs={time.time()-t:.1f}")
        out.append("OK")
    except Exception as e:
        out.append("ERROR=" + repr(e))
    with open(res, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def main():
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        _selftest(sys.argv[i + 1:])
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
