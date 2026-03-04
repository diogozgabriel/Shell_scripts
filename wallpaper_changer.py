#!/usr/bin/env python3
"""
Wallpaper Changer - Troca automática de wallpapers para múltiplos monitores.
Usa swww para definir wallpapers por monitor no Hyprland.
"""

import json
import random
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

WALLPAPER_DIR = "/home/diogo/Imagens/wallpapers"
MONITORS = ["DP-4", "DP-3", "DP-2", "HDMI-A-1"]
INTERVAL_MINUTES = 23
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}
WALLHAVEN_API = "https://wallhaven.cc/api/v1"


def get_wallpaper_files(directory):
    """Retorna lista de arquivos de imagem no diretório."""
    path = Path(directory)
    if not path.is_dir():
        return []
    return sorted(
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def ensure_swww_running():
    """Garante que o daemon swww está rodando."""
    result = subprocess.run(
        ["swww", "query"], capture_output=True, text=True
    )
    if result.returncode != 0:
        subprocess.run(["swww-daemon"], start_new_session=True)
        time.sleep(1)


def apply_wallpapers(monitor_wallpapers):
    """Aplica wallpapers usando swww."""
    ensure_swww_running()
    for monitor, wallpaper in monitor_wallpapers.items():
        subprocess.run(
            ["swww", "img", "-o", monitor, "--transition-type", "fade",
             "--transition-duration", "2", str(wallpaper)],
            check=True,
        )


def search_wallhaven(query="", categories="111", purity="100", sorting="toplist",
                      top_range="1M", atleast="1920x1080", page=1):
    """Busca wallpapers no Wallhaven e retorna lista de URLs de download."""
    params = (
        f"?q={query}&categories={categories}&purity={purity}"
        f"&sorting={sorting}&topRange={top_range}&atleast={atleast}&page={page}"
    )
    url = f"{WALLHAVEN_API}/search{params}"
    req = Request(url, headers={"User-Agent": "WallpaperChanger/1.0"})
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data.get("data", [])


def download_wallpaper(wp_data, dest_dir):
    """Baixa um wallpaper e salva no diretório de destino. Retorna o caminho."""
    img_url = wp_data["path"]
    filename = img_url.split("/")[-1]
    dest = Path(dest_dir) / filename
    if dest.exists():
        return dest
    req = Request(img_url, headers={"User-Agent": "WallpaperChanger/1.0"})
    with urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    return dest


class WallpaperChangerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Wallpaper Changer")
        self.root.resizable(False, False)

        self.wallpaper_dir = tk.StringVar(value=WALLPAPER_DIR)
        self.interval_min = tk.IntVar(value=INTERVAL_MINUTES)
        self.running = False
        self.timer_thread = None
        self.seconds_left = 0
        self.current_wallpapers = {}
        self.monitor_labels = {}

        self.search_query = tk.StringVar()
        self.download_count = tk.IntVar(value=10)

        self._build_ui()
        self._update_file_count()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- Diretório ---
        frm_dir = ttk.LabelFrame(self.root, text="Diretório de Wallpapers")
        frm_dir.pack(fill="x", **pad)
        ttk.Entry(frm_dir, textvariable=self.wallpaper_dir, width=50).pack(
            side="left", fill="x", expand=True, **pad
        )
        self.lbl_count = ttk.Label(frm_dir, text="")
        self.lbl_count.pack(side="right", **pad)

        # --- Intervalo ---
        frm_interval = ttk.LabelFrame(self.root, text="Intervalo (minutos)")
        frm_interval.pack(fill="x", **pad)
        ttk.Spinbox(
            frm_interval, from_=1, to=1440, textvariable=self.interval_min, width=6
        ).pack(side="left", **pad)
        self.lbl_timer = ttk.Label(frm_interval, text="Parado", width=20)
        self.lbl_timer.pack(side="right", **pad)

        # --- Monitores ---
        frm_monitors = ttk.LabelFrame(self.root, text="Monitores")
        frm_monitors.pack(fill="x", **pad)
        for mon in MONITORS:
            row = ttk.Frame(frm_monitors)
            row.pack(fill="x", **pad)
            ttk.Label(row, text=mon, width=12, font=("monospace", 10, "bold")).pack(
                side="left"
            )
            lbl = ttk.Label(row, text="—", width=45, anchor="w")
            lbl.pack(side="left", padx=(4, 0))
            self.monitor_labels[mon] = lbl

        # --- Botões ---
        frm_btn = ttk.Frame(self.root)
        frm_btn.pack(fill="x", **pad)

        self.btn_change = ttk.Button(
            frm_btn, text="Trocar Agora", command=self._change_now
        )
        self.btn_change.pack(side="left", **pad)

        self.btn_toggle = ttk.Button(
            frm_btn, text="Iniciar Auto", command=self._toggle_auto
        )
        self.btn_toggle.pack(side="left", **pad)

        ttk.Button(frm_btn, text="Sair", command=self._quit).pack(side="right", **pad)

        # --- Download Wallhaven ---
        frm_dl = ttk.LabelFrame(self.root, text="Baixar do Wallhaven")
        frm_dl.pack(fill="x", **pad)

        row1 = ttk.Frame(frm_dl)
        row1.pack(fill="x", **pad)
        ttk.Label(row1, text="Busca:").pack(side="left")
        ttk.Entry(row1, textvariable=self.search_query, width=30).pack(
            side="left", fill="x", expand=True, padx=(4, 8)
        )
        ttk.Label(row1, text="Qtd:").pack(side="left")
        ttk.Spinbox(row1, from_=1, to=100, textvariable=self.download_count, width=5).pack(
            side="left", padx=(4, 0)
        )

        row2 = ttk.Frame(frm_dl)
        row2.pack(fill="x", **pad)
        self.btn_download = ttk.Button(
            row2, text="Baixar Wallpapers", command=self._start_download
        )
        self.btn_download.pack(side="left")
        self.lbl_dl_status = ttk.Label(row2, text="")
        self.lbl_dl_status.pack(side="left", padx=(8, 0))

    def _update_file_count(self):
        files = get_wallpaper_files(self.wallpaper_dir.get())
        self.lbl_count.config(text=f"{len(files)} imagens encontradas")

    def _pick_wallpapers(self):
        """Escolhe wallpapers aleatórios sem repetição para cada monitor."""
        files = get_wallpaper_files(self.wallpaper_dir.get())
        if len(files) < len(MONITORS):
            messagebox.showerror(
                "Erro",
                f"São necessárias pelo menos {len(MONITORS)} imagens.\n"
                f"Encontradas: {len(files)}",
            )
            return None
        chosen = random.sample(files, len(MONITORS))
        return dict(zip(MONITORS, chosen))

    def _apply_and_display(self, mapping):
        """Aplica wallpapers e atualiza a interface."""
        try:
            apply_wallpapers(mapping)
        except FileNotFoundError:
            messagebox.showerror(
                "Erro",
                "swww não encontrado. Instale com: paru -S swww",
            )
            self._stop_auto()
            return False
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Erro", f"Falha ao aplicar wallpaper:\n{e}")
            self._stop_auto()
            return False

        self.current_wallpapers = mapping
        for mon, wp in mapping.items():
            self.monitor_labels[mon].config(text=wp.name)
        self._update_file_count()
        return True

    def _change_now(self):
        mapping = self._pick_wallpapers()
        if mapping:
            self._apply_and_display(mapping)
            if self.running:
                self.seconds_left = self.interval_min.get() * 60

    def _toggle_auto(self):
        if self.running:
            self._stop_auto()
        else:
            self._start_auto()

    def _start_auto(self):
        mapping = self._pick_wallpapers()
        if not mapping:
            return
        if not self._apply_and_display(mapping):
            return

        self.running = True
        self.seconds_left = self.interval_min.get() * 60
        self.btn_toggle.config(text="Parar Auto")
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        self._tick_ui()

    def _stop_auto(self):
        self.running = False
        self.btn_toggle.config(text="Iniciar Auto")
        self.lbl_timer.config(text="Parado")

    def _timer_loop(self):
        """Thread que decrementa o contador e troca wallpapers."""
        while self.running:
            time.sleep(1)
            if not self.running:
                break
            self.seconds_left -= 1
            if self.seconds_left <= 0:
                mapping = self._pick_wallpapers()
                if mapping:
                    self.root.after(0, self._apply_and_display, mapping)
                self.seconds_left = self.interval_min.get() * 60

    def _tick_ui(self):
        """Atualiza o label do timer na thread principal."""
        if not self.running:
            return
        mins, secs = divmod(self.seconds_left, 60)
        self.lbl_timer.config(text=f"Próxima troca: {mins:02d}:{secs:02d}")
        self.root.after(1000, self._tick_ui)

    def _start_download(self):
        """Inicia download em thread separada."""
        self.btn_download.config(state="disabled")
        self.lbl_dl_status.config(text="Buscando...")
        threading.Thread(target=self._download_thread, daemon=True).start()

    def _download_thread(self):
        """Baixa wallpapers do Wallhaven."""
        query = self.search_query.get()
        total = self.download_count.get()
        dest = self.wallpaper_dir.get()
        Path(dest).mkdir(parents=True, exist_ok=True)

        downloaded = 0
        page = 1
        try:
            while downloaded < total:
                results = search_wallhaven(query=query, page=page)
                if not results:
                    break
                for wp in results:
                    if downloaded >= total:
                        break
                    try:
                        download_wallpaper(wp, dest)
                        downloaded += 1
                        self.root.after(
                            0, self.lbl_dl_status.config,
                            {"text": f"Baixando {downloaded}/{total}..."}
                        )
                    except (URLError, OSError):
                        continue
                page += 1
        except (URLError, OSError) as e:
            self.root.after(
                0, lambda: messagebox.showerror("Erro", f"Falha no download:\n{e}")
            )

        self.root.after(0, self._download_done, downloaded)

    def _download_done(self, count):
        self.btn_download.config(state="normal")
        self.lbl_dl_status.config(text=f"{count} baixados!")
        self._update_file_count()

    def _quit(self):
        self.running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    WallpaperChangerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
