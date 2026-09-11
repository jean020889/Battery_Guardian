
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Battery Guardian v2.2.4
=======================
Cuida la salud de la batería de tu portátil Linux.

NOVEDADES v2.2.4:
- NUEVO: detecta si el navegador está en uso y NO apaga el equipo.
  * Ventana activa es un navegador (Firefox, Chrome, Brave...).
  * Cualquier ventana de navegador a pantalla completa.
  * Título de ventana contiene servicio de vídeo (YouTube, Netflix...).
- Nueva opción configurable: "Ignorar apagado si el navegador está en uso".
- Estado del navegador visible en la GUI.

NOVEDADES v2.2.3:
- FIX CRÍTICO: el contador de apagado ahora dispara el apagado al llegar a 0.
- FIX: botón "Apagar YA" ahora funciona correctamente.
- Nuevo flag 'confirmed' separado de 'cancelled' en el diálogo.

NOVEDADES v2.2.2:
- Fix del error 'latin-1' codec en el título del icono de bandeja.
- Verificación de sudoers al arrancar.

NOVEDADES v2.2.1:
- Auto-apagado usa 'sudo poweroff --force --force' como método principal.

Autor: Proyecto Battery Guardian
Licencia: MIT
"""

import os
import re
import sys
import json
import time
import shutil
import logging
import threading
import subprocess
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


# =========================================================
#  CONSTANTES
# =========================================================
APP_NAME = "Battery Guardian"
APP_VERSION = "2.2.4"
SYSTEMD_SERVICE = "battery-guardian.service"
SUDOERS_FILE = "/etc/sudoers.d/battery-guardian"
POWEROFF_PATH = "/usr/sbin/poweroff"

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "battery_guardian")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_FILE = os.path.join(CONFIG_DIR, "battery_guardian.log")

DEFAULT_CONFIG = {
    "enabled": True,
    "max_charge": 80,
    "min_charge": 15,
    "check_interval": 20,
    "sound_enabled": True,
    "sound_repeat_ms": 2500,
    "fullscreen_alert": True,
    "close_to_tray": True,
    "start_hidden": False,
    "zoom": 0.8,
    "auto_shutdown_enabled": False,
    "auto_shutdown_minutes": 10,
    "auto_shutdown_warning_seconds": 60,
    "auto_shutdown_check_interval": 15,
    "ignore_browser": True,
}

ZOOM_MIN = 0.8
ZOOM_MAX = 2.5
ZOOM_STEP = 0.1
MIN_FONT_SIZE = 11

SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/ubuntu/stereo/bell.ogg",
    "/usr/share/sounds/alsa/Front_Center.wav",
]

# Navegadores conocidos (comparación case-insensitive, por substring)
BROWSER_CLASSES = [
    "firefox", "firefox-esr", "google-chrome", "chrome", "chromium",
    "chromium-browser", "brave-browser", "brave", "microsoft-edge",
    "msedge", "opera", "vivaldi-stable", "vivaldi", "epiphany",
    "midori", "falkon", "qutebrowser", "waterfox", "palemoon",
    "librewolf", "tor-browser", "zen",
]

# Palabras clave en el título de ventana que indican vídeo/streaming
VIDEO_KEYWORDS = [
    "youtube", "netflix", "twitch", "vimeo", "dailymotion",
    "prime video", "hbo", "disney+", "disney plus", "spotify",
    "deezer", "soundcloud", "bandcamp", "crunchyroll",
    "hbomax", "paramount+", "peacock", "apple tv",
]

COLOR_BG = "#f5f7fa"
COLOR_CARD = "#ffffff"
COLOR_TEXT = "#1f2937"
COLOR_MUTED = "#6b7280"
COLOR_PRIMARY = "#2563eb"
COLOR_SUCCESS = "#16a34a"
COLOR_WARN = "#f59e0b"
COLOR_DANGER = "#dc2626"
COLOR_BORDER = "#e5e7eb"


# =========================================================
#  LOGGING
# =========================================================
def setup_logging():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


log = logging.getLogger(APP_NAME)


# =========================================================
#  CONFIGURACIÓN
# =========================================================
def load_config() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception as e:
            log.error(f"Error leyendo config: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Error guardando config: {e}")


# =========================================================
#  SYSTEMD
# =========================================================
def is_running_under_systemd() -> bool:
    return bool(os.environ.get("INVOCATION_ID"))


def notify_systemd_stop():
    if not is_running_under_systemd():
        return
    try:
        subprocess.Popen(
            ["systemctl", "--user", "stop", SYSTEMD_SERVICE],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# =========================================================
#  SUDOERS
# =========================================================
def check_sudoers_configured() -> bool:
    if not os.path.exists(SUDOERS_FILE):
        return False
    try:
        result = subprocess.run(
            ["sudo", "-n", POWEROFF_PATH, "--help"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# =========================================================
#  BATERÍA
# =========================================================
def find_battery_device():
    try:
        out = subprocess.check_output(
            ["upower", "-e"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            low = line.lower()
            if "battery" in low or "/bat" in low:
                return line.strip()
    except Exception as e:
        log.error(f"upower -e error: {e}")
    return None


def _parse_upower_output(text: str) -> dict:
    data = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key:
            data[key] = value
    return data


def _to_float(value_str):
    if value_str is None:
        return None
    m = re.search(r"-?\d+[.,]?\d*", str(value_str))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def _to_int(value_str):
    if value_str is None:
        return None
    m = re.search(r"-?\d+", str(value_str))
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def get_battery_full_info() -> dict:
    info = {
        "device": None, "state": None, "percentage": None,
        "energy": None, "energy_full": None, "energy_full_design": None,
        "energy_rate": None, "capacity": None, "charge_cycles": None,
        "voltage": None, "time_to_empty": None, "time_to_full": None,
        "temperature": None,
    }
    device = find_battery_device()
    if not device:
        return info
    info["device"] = device
    try:
        out = subprocess.check_output(
            ["upower", "-i", device], text=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        log.error(f"upower -i error: {e}")
        return info
    raw = _parse_upower_output(out)
    info["state"] = raw.get("state")
    info["percentage"] = _to_int(raw.get("percentage"))
    info["energy"] = _to_float(raw.get("energy"))
    info["energy_full"] = _to_float(raw.get("energy-full"))
    info["energy_full_design"] = _to_float(raw.get("energy-full-design"))
    info["energy_rate"] = _to_float(raw.get("energy-rate"))
    info["capacity"] = _to_float(raw.get("capacity"))
    info["charge_cycles"] = _to_int(raw.get("charge-cycles"))
    info["voltage"] = _to_float(raw.get("voltage"))
    info["temperature"] = _to_float(raw.get("temperature"))
    info["time_to_empty"] = raw.get("time to empty")
    info["time_to_full"] = raw.get("time to full")
    if info["capacity"] is None and info["energy_full"] and info["energy_full_design"]:
        info["capacity"] = round(
            info["energy_full"] / info["energy_full_design"] * 100, 2)
    return info


def get_battery():
    info = get_battery_full_info()
    return info["state"], info["percentage"]


# =========================================================
#  SONIDO
# =========================================================
def play_sound():
    for path in SOUND_CANDIDATES:
        if os.path.exists(path):
            try:
                if path.endswith(".wav"):
                    subprocess.Popen(["aplay", "-q", path],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["paplay", path],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                return
            except Exception as e:
                log.warning(f"No se pudo reproducir {path}: {e}")


# =========================================================
#  UTILIDADES X11 / VENTANAS
# =========================================================
def _cmd_exists(name):
    return shutil.which(name) is not None


def _x11_available() -> bool:
    return bool(os.environ.get("DISPLAY"))


def get_active_window_id():
    if not _x11_available() or not _cmd_exists("xdotool"):
        return None
    try:
        wid = subprocess.check_output(
            ["xdotool", "getactivewindow"],
            text=True, timeout=3, stderr=subprocess.DEVNULL,
        ).strip()
        return wid or None
    except Exception:
        return None


def get_window_class(wid):
    if not wid or not _x11_available() or not _cmd_exists("xdotool"):
        return None
    try:
        return subprocess.check_output(
            ["xdotool", "getwindowclassname", wid],
            text=True, timeout=3, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def get_window_title(wid):
    if not wid or not _x11_available() or not _cmd_exists("xdotool"):
        return None
    try:
        return subprocess.check_output(
            ["xdotool", "getwindowname", wid],
            text=True, timeout=3, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def is_browser_class(wm_class) -> bool:
    if not wm_class:
        return False
    wm_low = wm_class.lower()
    for b in BROWSER_CLASSES:
        if b in wm_low:
            return True
    return False


def is_window_fullscreen(wid) -> bool:
    if not wid or not _x11_available() or not _cmd_exists("xprop"):
        return False
    try:
        out = subprocess.check_output(
            ["xprop", "-id", wid, "_NET_WM_STATE"],
            text=True, timeout=3, stderr=subprocess.DEVNULL,
        )
        return "FULLSCREEN" in out.upper()
    except Exception:
        return False


def get_all_visible_windows():
    """Devuelve lista de (wid, wm_class, title) de ventanas visibles (X11)."""
    if not _x11_available() or not _cmd_exists("xdotool"):
        return []
    try:
        out = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--name", ".*"],
            text=True, timeout=4, stderr=subprocess.DEVNULL,
        )
        wids = [w.strip() for w in out.splitlines() if w.strip()]
    except Exception:
        return []

    windows = []
    for wid in wids:
        wm_class = get_window_class(wid)
        title = get_window_title(wid)
        if wm_class or title:
            windows.append((wid, wm_class or "", title or ""))
    return windows


def get_browser_status():
    """
    Devuelve un dict con el estado del navegador:
      {
        "in_use":        bool,
        "reason":        str,   # motivo por el que se considera en uso
        "active_class":  str,
        "active_title":  str,
      }
    """
    result = {
        "in_use": False,
        "reason": "",
        "active_class": "",
        "active_title": "",
    }

    if not _x11_available() or not _cmd_exists("xdotool"):
        result["reason"] = "xdotool no disponible"
        return result

    # 1) Ventana activa
    wid = get_active_window_id()
    if wid:
        wm_class = get_window_class(wid) or ""
        title = get_window_title(wid) or ""
        result["active_class"] = wm_class
        result["active_title"] = title

        if is_browser_class(wm_class):
            result["in_use"] = True
            result["reason"] = f"Ventana activa es navegador ({wm_class})"
            return result

    # 2) Cualquier ventana de navegador
    for w, wm_class, title in get_all_visible_windows():
        if not is_browser_class(wm_class):
            continue
        # a) Pantalla completa → vídeo probable
        if is_window_fullscreen(w):
            result["in_use"] = True
            result["reason"] = f"Navegador a pantalla completa ({wm_class})"
            return result
        # b) Título con servicio de vídeo
        title_low = title.lower()
        for kw in VIDEO_KEYWORDS:
            if kw in title_low:
                result["in_use"] = True
                result["reason"] = f"Título contiene '{kw}': {title[:60]}"
                return result

    return result


# =========================================================
#  DETECCIÓN DE INACTIVIDAD Y MULTIMEDIA
# =========================================================
def get_idle_seconds():
    if _cmd_exists("xprintidle"):
        try:
            out = subprocess.check_output(
                ["xprintidle"], text=True, timeout=3,
                stderr=subprocess.DEVNULL)
            return int(out.strip()) / 1000.0
        except Exception:
            pass
    try:
        out = subprocess.check_output(
            ["dbus-send", "--print-reply",
             "--dest=org.gnome.Mutter.IdleMonitor",
             "/org/gnome/Mutter/IdleMonitor/Core",
             "org.gnome.Mutter.IdleMonitor.GetIdletime"],
            text=True, timeout=3, stderr=subprocess.DEVNULL)
        m = re.search(r"uint64\s+(\d+)", out)
        if m:
            return int(m.group(1)) / 1000.0
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            ["dbus-send", "--print-reply", "--dest=org.xfce.ScreenSaver",
             "/org/xfce/ScreenSaver", "org.xfce.ScreenSaver.GetActiveTime"],
            text=True, timeout=3, stderr=subprocess.DEVNULL)
        m = re.search(r"uint32\s+(\d+)", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return -1


def is_multimedia_playing():
    if _cmd_exists("pactl"):
        try:
            out = subprocess.check_output(
                ["pactl", "list", "sink-inputs"],
                text=True, timeout=3, stderr=subprocess.DEVNULL)
            running = sum(1 for line in out.splitlines()
                          if "State: RUNNING" in line)
            if running > 0:
                return True
        except Exception:
            pass
    if _cmd_exists("playerctl"):
        try:
            out = subprocess.check_output(
                ["playerctl", "-a", "status"],
                text=True, timeout=3, stderr=subprocess.DEVNULL)
            if "Playing" in out:
                return True
        except Exception:
            pass
    return False


# =========================================================
#  ESTILOS MODERNOS
# =========================================================
def apply_modern_styles(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=COLOR_BG)

    style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT,
                    fieldbackground=COLOR_CARD)
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Card.TFrame", background=COLOR_CARD,
                    relief="flat", borderwidth=1)
    style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                    font=("DejaVu Sans", 11))
    style.configure("Card.TLabel", background=COLOR_CARD,
                    foreground=COLOR_TEXT, font=("DejaVu Sans", 11))
    style.configure("Title.TLabel", background=COLOR_BG,
                    foreground=COLOR_TEXT, font=("DejaVu Sans", 20, "bold"))
    style.configure("Subtitle.TLabel", background=COLOR_BG,
                    foreground=COLOR_MUTED, font=("DejaVu Sans", 10, "italic"))
    style.configure("Section.TLabel", background=COLOR_BG,
                    foreground=COLOR_PRIMARY, font=("DejaVu Sans", 13, "bold"))
    style.configure("Muted.TLabel", background=COLOR_CARD,
                    foreground=COLOR_MUTED, font=("DejaVu Sans", 10))
    style.configure("Info.TLabel", background=COLOR_CARD,
                    foreground=COLOR_TEXT, font=("DejaVu Sans", 11))
    style.configure("Warn.TLabel", background=COLOR_CARD,
                    foreground=COLOR_DANGER, font=("DejaVu Sans", 10, "bold"))
    style.configure("Ok.TLabel", background=COLOR_CARD,
                    foreground=COLOR_SUCCESS, font=("DejaVu Sans", 10, "bold"))

    style.configure("TButton", font=("DejaVu Sans", 11), padding=8,
                    relief="flat", borderwidth=0)
    style.map("TButton",
              background=[("active", "#dbeafe"), ("!active", COLOR_CARD)],
              foreground=[("active", COLOR_PRIMARY), ("!active", COLOR_TEXT)])

    style.configure("Primary.TButton", font=("DejaVu Sans", 11, "bold"),
                    padding=10, relief="flat", background=COLOR_PRIMARY,
                    foreground="white", borderwidth=0)
    style.map("Primary.TButton",
              background=[("active", "#1d4ed8"), ("!active", COLOR_PRIMARY)],
              foreground=[("active", "white"), ("!active", "white")])

    style.configure("Danger.TButton", font=("DejaVu Sans", 11, "bold"),
                    padding=10, relief="flat", background=COLOR_DANGER,
                    foreground="white", borderwidth=0)
    style.map("Danger.TButton",
              background=[("active", "#b91c1c"), ("!active", COLOR_DANGER)],
              foreground=[("active", "white"), ("!active", "white")])

    style.configure("Card.TLabelframe", background=COLOR_CARD,
                    foreground=COLOR_TEXT, borderwidth=1, relief="solid",
                    bordercolor=COLOR_BORDER, padding=12)
    style.configure("Card.TLabelframe.Label", background=COLOR_BG,
                    foreground=COLOR_PRIMARY,
                    font=("DejaVu Sans", 12, "bold"))

    style.configure("Card.TCheckbutton", background=COLOR_CARD,
                    foreground=COLOR_TEXT, font=("DejaVu Sans", 11))
    style.map("Card.TCheckbutton", background=[("active", COLOR_CARD)],
              foreground=[("active", COLOR_TEXT)])

    style.configure("TCheckbutton", background=COLOR_BG,
                    foreground=COLOR_TEXT, font=("DejaVu Sans", 11))
    style.map("TCheckbutton", background=[("active", COLOR_BG)],
              foreground=[("active", COLOR_TEXT)])

    style.configure("TSeparator", background=COLOR_BORDER)
    style.configure("TSpinbox", fieldbackground=COLOR_CARD,
                    background=COLOR_CARD, foreground=COLOR_TEXT,
                    arrowcolor=COLOR_TEXT, bordercolor=COLOR_BORDER,
                    font=("DejaVu Sans", 11))
    return style


# =========================================================
#  DIÁLOGO DE CUENTA ATRÁS
# =========================================================
class ShutdownCountdownDialog:

    def __init__(self, parent, seconds, minutes_idle, zoom_mgr=None):
        self.cancelled = False
        self.confirmed = False
        self.remaining = seconds
        self.minutes_idle = minutes_idle
        self.zoom_mgr = zoom_mgr

        def fs(base):
            if zoom_mgr:
                return max(MIN_FONT_SIZE, zoom_mgr.scaled(base))
            return max(MIN_FONT_SIZE, base)

        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - Apagado automático")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self.win.resizable(False, False)
        self.win.configure(bg=COLOR_CARD)

        w, h = 780, 520
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        try:
            self.win.grab_set()
        except Exception:
            pass

        header = tk.Frame(self.win, bg=COLOR_DANGER, height=90)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="⚠   APAGADO AUTOMÁTICO   ⚠",
                 font=("DejaVu Sans", fs(24), "bold"),
                 fg="white", bg=COLOR_DANGER).pack(expand=True)

        body = tk.Frame(self.win, bg=COLOR_CARD, padx=40, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body,
                 text=(f"El equipo lleva {self.minutes_idle:.1f} minutos inactivo\n"
                       f"(sin teclado, ratón, multimedia ni navegador en uso)."),
                 font=("DejaVu Sans", fs(14)),
                 fg=COLOR_TEXT, bg=COLOR_CARD,
                 justify="center").pack(pady=(0, 26))

        count_frame = tk.Frame(body, bg=COLOR_CARD)
        count_frame.pack(pady=6)

        tk.Label(count_frame, text="El equipo se apagará en",
                 font=("DejaVu Sans", fs(15)),
                 fg=COLOR_MUTED, bg=COLOR_CARD).pack()

        self.lbl_count = tk.Label(count_frame,
                                  text=f"{self.remaining}",
                                  font=("DejaVu Sans", fs(72), "bold"),
                                  fg=COLOR_DANGER, bg=COLOR_CARD)
        self.lbl_count.pack()

        tk.Label(count_frame, text="segundos",
                 font=("DejaVu Sans", fs(16)),
                 fg=COLOR_MUTED, bg=COLOR_CARD).pack()

        tk.Label(body,
                 text="Pulsa  CANCELAR  si quieres seguir usando el equipo.",
                 font=("DejaVu Sans", fs(13), "italic"),
                 fg=COLOR_MUTED, bg=COLOR_CARD,
                 wraplength=700, justify="center").pack(pady=(26, 20))

        btn_frame = tk.Frame(body, bg=COLOR_CARD)
        btn_frame.pack()

        cancel_btn = tk.Button(btn_frame,
            text="✕   CANCELAR apagado",
            font=("DejaVu Sans", fs(15), "bold"),
            bg=COLOR_SUCCESS, fg="white",
            activebackground="#15803d", activeforeground="white",
            relief="flat", padx=30, pady=16, borderwidth=0,
            cursor="hand2", command=self._cancel)
        cancel_btn.grid(row=0, column=0, padx=10)

        now_btn = tk.Button(btn_frame,
            text="⏻   Apagar YA",
            font=("DejaVu Sans", fs(14), "bold"),
            bg="#6b7280", fg="white",
            activebackground="#4b5563", activeforeground="white",
            relief="flat", padx=24, pady=16, borderwidth=0,
            cursor="hand2", command=self._confirm_now)
        now_btn.grid(row=0, column=1, padx=10)

        self.win.bind("<Escape>", lambda e: self._cancel())
        self.win.bind("<Return>", lambda e: self._cancel())

        self._tick()

    def _tick(self):
        if self.cancelled or self.confirmed:
            return
        if self.remaining <= 0:
            self._confirm_now()
            return
        try:
            self.lbl_count.config(text=f"{self.remaining}")
        except tk.TclError:
            return
        self.remaining -= 1
        self.win.after(1000, self._tick)

    def _cancel(self):
        self.cancelled = True
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    def _confirm_now(self):
        self.confirmed = True
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


# =========================================================
#  GESTOR DE AUTO-APAGADO
# =========================================================
class AutoShutdownManager:

    def __init__(self, app):
        self.app = app
        self._stop = threading.Event()
        self._thread = None
        self._dialog_active = False
        self._warning_until = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="autoshutdown")
        self._thread.start()
        log.info("AutoShutdownManager iniciado")

    def stop(self):
        self._stop.set()
        log.info("AutoShutdownManager detenido")

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._check()
            except Exception as e:
                log.error(f"Error en AutoShutdown: {e}")
            interval = max(5, int(self.app.config.get(
                "auto_shutdown_check_interval", 15)))
            self._stop.wait(interval)

    def _check(self):
        cfg = self.app.config
        if not cfg.get("auto_shutdown_enabled", False):
            return
        if self._dialog_active:
            return
        if time.time() < self._warning_until:
            return

        # 1) ¿Multimedia reproduciéndose? (audio/vídeo)
        if is_multimedia_playing():
            log.info("AutoShutdown: multimedia activa, no se apaga")
            return

        # 2) ¿Navegador en uso?
        if cfg.get("ignore_browser", True):
            browser = get_browser_status()
            if browser.get("in_use"):
                log.info(f"AutoShutdown: navegador en uso -> "
                         f"{browser['reason']}, no se apaga")
                return

        # 3) ¿Cuánto tiempo inactivo?
        idle = get_idle_seconds()
        if idle < 0:
            return

        threshold_min = float(cfg.get("auto_shutdown_minutes", 10))
        threshold_s = threshold_min * 60
        if idle < threshold_s:
            return

        warn_s = int(cfg.get("auto_shutdown_warning_seconds", 60))
        log.warning(f"AutoShutdown: idle={idle:.0f}s >= {threshold_s:.0f}s -> "
                    f"cuenta atras {warn_s}s")
        self._dialog_active = True
        self.app.root.after(0, lambda: self._run_dialog(idle, warn_s))

    def _run_dialog(self, idle_s, warn_s):
        try:
            dlg = ShutdownCountdownDialog(
                self.app.root, warn_s, idle_s / 60.0, self.app.zoom_mgr)
            self.app.root.wait_window(dlg.win)

            if dlg.confirmed:
                log.warning("AutoShutdown: confirmado -> apagando el equipo")
                self._do_shutdown()
            elif dlg.cancelled:
                self._warning_until = time.time() + 60
                log.info("AutoShutdown cancelado por el usuario")
            else:
                log.warning("AutoShutdown: dialogo cerrado sin decision -> apagando")
                self._do_shutdown()
        except Exception as e:
            log.error(f"Error en dialogo de apagado: {e}")
        finally:
            self._dialog_active = False

    def _do_shutdown(self):
        methods = [
            ["sudo", "-n", "/usr/sbin/poweroff", "--force", "--force"],
            ["sudo", "-n", "/sbin/poweroff", "--force", "--force"],
            ["sudo", "-n", "poweroff", "--force", "--force"],
            ["pkexec", "poweroff", "--force", "--force"],
            ["sudo", "-n", "systemctl", "poweroff", "--force", "--force"],
            ["systemctl", "poweroff", "--force", "--force"],
            ["sudo", "-n", "shutdown", "-h", "now"],
            ["shutdown", "-h", "now"],
        ]
        for i, cmd in enumerate(methods, 1):
            try:
                log.warning(f"AutoShutdown: intentando metodo {i}: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=10, text=True)
                if result.returncode == 0:
                    log.warning(f"AutoShutdown: apagado iniciado con {' '.join(cmd)}")
                    return
                else:
                    err = result.stderr.strip() if result.stderr else "(sin stderr)"
                    log.warning(f"AutoShutdown: metodo {i} fallo "
                                f"(rc={result.returncode}): {err}")
            except FileNotFoundError:
                log.warning(f"AutoShutdown: comando no encontrado: {cmd[0]}")
                continue
            except subprocess.TimeoutExpired:
                log.warning(f"AutoShutdown: timeout con {' '.join(cmd)}")
                continue
            except Exception as e:
                log.warning(f"AutoShutdown: error con {' '.join(cmd)}: {e}")
                continue
        log.error("AutoShutdown: NINGUN metodo de apagado funciono.")
        log.error(f"AutoShutdown: configura sudoers con: {SUDOERS_FILE}")


# =========================================================
#  GESTOR DE ZOOM
# =========================================================
class ZoomManager:
    def __init__(self, root, initial_zoom=0.8):
        self.root = root
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, float(initial_zoom)))
        self._base_fonts = {}
        self._listeners = []
        self._register_default_fonts()

    def _register_default_fonts(self):
        for name, default in (("TkDefaultFont", 11),
                              ("TkTextFont", 11),
                              ("TkFixedFont", 11)):
            try:
                self._base_fonts[name] = tkfont.nametofont(name).actual("size")
            except Exception:
                self._base_fonts[name] = default

    def register_font(self, name, base_size):
        self._base_fonts[name] = base_size

    def scaled(self, base_size):
        return max(MIN_FONT_SIZE, int(round(base_size * self.zoom)))

    def apply(self):
        for name, base in self._base_fonts.items():
            try:
                tkfont.nametofont(name).configure(size=self.scaled(base))
            except Exception:
                pass
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass

    def add_listener(self, cb):
        self._listeners.append(cb)

    def set_zoom(self, value):
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, round(value, 2)))
        self.apply()

    def zoom_in(self):
        self.set_zoom(self.zoom + ZOOM_STEP)

    def zoom_out(self):
        self.set_zoom(self.zoom - ZOOM_STEP)

    def zoom_reset(self):
        self.set_zoom(1.0)

    def percent(self):
        return int(round(self.zoom * 100))


# =========================================================
#  ICONO DE LA BANDEJA
# =========================================================
def make_tray_image(level=None, charging=False, alert=False):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    border_color = "#FF5252" if alert else "#FFFFFF"
    draw.rectangle([4, 14, 52, 50], outline=border_color, width=3,
                   fill=(25, 25, 25, 255))
    draw.rectangle([52, 24, 58, 40], fill=border_color)
    if level is not None:
        inner_x0, inner_x1 = 8, 48
        inner_w = inner_x1 - inner_x0
        if charging:
            color = "#2196F3"
        elif level <= 20:
            color = "#F44336"
        elif level <= 40:
            color = "#FF9800"
        else:
            color = "#4CAF50"
        w = int(inner_w * max(0, min(100, level)) / 100)
        if w > 0:
            draw.rectangle([inner_x0, 18, inner_x0 + w, 46], fill=color)
        if charging:
            draw.polygon(
                [(32, 20), (26, 34), (31, 34), (28, 44), (38, 30),
                 (33, 30), (36, 20)],
                fill="#FFF176", outline="#FFF176")
    return img


# =========================================================
#  VENTANA DE ALERTA BLOQUEANTE
# =========================================================
class AlertWindow:

    def __init__(self, parent, config, alert_type, on_resolved, zoom_mgr=None):
        self.config = config
        self.alert_type = alert_type
        self.on_resolved = on_resolved
        self.zoom_mgr = zoom_mgr
        self._running = True

        def fs(base):
            if zoom_mgr:
                return max(MIN_FONT_SIZE, zoom_mgr.scaled(base))
            return max(MIN_FONT_SIZE, base)

        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - ALERTA")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)

        if config.get("fullscreen_alert", True):
            try:
                self.win.attributes("-fullscreen", True)
            except Exception:
                self.win.geometry("900x600")
        else:
            self.win.geometry("900x600")
            self.win.update_idletasks()
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            self.win.geometry(f"900x600+{(sw - 900) // 2}+{(sh - 600) // 2}")

        bg = "#8B0000" if alert_type == "disconnect" else "#B8860B"
        self.win.configure(bg=bg)
        try:
            self.win.grab_set()
        except Exception:
            pass

        frame = tk.Frame(self.win, bg=bg)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        if alert_type == "disconnect":
            title = "DESCONECTA EL CARGADOR"
            msg = (f"La batería ha alcanzado el {config['max_charge']}%.\n\n"
                   "Desconecta el cargador para cuidar la batería.")
        else:
            title = "CONECTA EL CARGADOR"
            msg = (f"La batería ha bajado al {config['min_charge']}%.\n\n"
                   "Conecta el cargador para evitar un apagado inesperado.")

        self.lbl_title = tk.Label(frame, text=f"⚠  {title}  ⚠",
                                  font=("DejaVu Sans", fs(40), "bold"),
                                  fg="white", bg=bg)
        self.lbl_title.pack(pady=30)
        self.lbl_msg = tk.Label(frame, text=msg,
                                font=("DejaVu Sans", fs(24)),
                                fg="white", bg=bg, justify="center")
        self.lbl_msg.pack(pady=20)
        self.status_label = tk.Label(frame, text="",
                                     font=("DejaVu Sans", fs(16)),
                                     fg="#FFFFCC", bg=bg, justify="center")
        self.status_label.pack(pady=20)
        self.lbl_hint = tk.Label(frame,
            text="Esta ventana se cerrará automáticamente al realizar la acción.",
            font=("DejaVu Sans", fs(14), "italic"),
            fg="#EEEEEE", bg=bg)
        self.lbl_hint.pack(pady=10)

        if zoom_mgr:
            zoom_mgr.add_listener(self._refresh_fonts)

        self._sound_loop()
        self._check_loop()
        log.info(f"Alerta mostrada: {alert_type}")

    def _refresh_fonts(self):
        if not self.win.winfo_exists():
            return
        z = self.zoom_mgr
        try:
            if z:
                self.lbl_title.config(font=("DejaVu Sans", z.scaled(40), "bold"))
                self.lbl_msg.config(font=("DejaVu Sans", z.scaled(24)))
                self.status_label.config(font=("DejaVu Sans", z.scaled(16)))
                self.lbl_hint.config(font=("DejaVu Sans", z.scaled(14), "italic"))
        except tk.TclError:
            pass

    def _sound_loop(self):
        if not self._running or not self.win.winfo_exists():
            return
        if self.config.get("sound_enabled", True):
            play_sound()
        self.win.after(self.config.get("sound_repeat_ms", 2500),
                       self._sound_loop)

    def _check_loop(self):
        if not self._running or not self.win.winfo_exists():
            return
        state, level = get_battery()
        resolved = False
        if self.alert_type == "disconnect":
            if state == "discharging":
                resolved = True
        else:
            if state in ("charging", "fully-charged"):
                resolved = True
        if resolved:
            self._close()
            return
        state_txt = state if state else "desconocido"
        level_txt = f"{level}%" if level is not None else "N/D"
        try:
            self.status_label.config(
                text=f"Estado actual: {state_txt}   |   Nivel: {level_txt}")
        except tk.TclError:
            return
        self.win.after(2000, self._check_loop)

    def _close(self):
        if not self._running:
            return
        self._running = False
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        log.info(f"Alerta resuelta: {self.alert_type}")
        if self.on_resolved:
            self.on_resolved()


# =========================================================
#  VENTANA DE INFORMACIÓN
# =========================================================
class InfoWindow:

    def __init__(self, parent, zoom_mgr=None):
        self.zoom_mgr = zoom_mgr
        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - Información de la batería")
        self.win.geometry("760x680")
        self.win.minsize(560, 460)
        self.win.configure(bg=COLOR_BG)

        def fs(base):
            if zoom_mgr:
                return max(MIN_FONT_SIZE, zoom_mgr.scaled(base))
            return max(MIN_FONT_SIZE, base)

        main = ttk.Frame(self.win, padding=18)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 10))

        self.lbl_title = ttk.Label(header, text="📊  Información detallada",
                                   style="Section.TLabel")
        self.lbl_title.pack(side="left")

        zbtns = ttk.Frame(header)
        zbtns.pack(side="right")
        self.lbl_zoom = ttk.Label(zbtns, text="100%")
        self.lbl_zoom.pack(side="right", padx=4)
        ttk.Button(zbtns, text="A+", width=4,
                   command=self._zoom_in).pack(side="right", padx=1)
        ttk.Button(zbtns, text="A−", width=4,
                   command=self._zoom_out).pack(side="right", padx=1)
        ttk.Button(zbtns, text="↺", width=3,
                   command=self._zoom_reset).pack(side="right", padx=1)

        self.text = tk.Text(main, wrap="word",
                            font=("DejaVu Sans Mono", fs(12)),
                            height=24, bg="#0f172a", fg="#e5e7eb",
                            insertbackground="white", relief="flat",
                            padx=14, pady=12)
        self.text.pack(fill="both", expand=True)

        btns = ttk.Frame(main)
        btns.pack(pady=10)
        ttk.Button(btns, text="🔄  Actualizar",
                   command=self.refresh).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="❌  Cerrar",
                   command=self.win.destroy).grid(row=0, column=1, padx=4)

        if zoom_mgr:
            zoom_mgr.add_listener(self._refresh_fonts)
            self.win.bind("<Control-plus>", lambda e: self._zoom_in())
            self.win.bind("<Control-equal>", lambda e: self._zoom_in())
            self.win.bind("<Control-minus>", lambda e: self._zoom_out())
            self.win.bind("<Control-0>", lambda e: self._zoom_reset())

        self._update_zoom_label()
        self.refresh()

    def _fs(self, base):
        return self.zoom_mgr.scaled(base) if self.zoom_mgr else base

    def _zoom_in(self):
        if self.zoom_mgr:
            self.zoom_mgr.zoom_in()
            self._update_zoom_label()

    def _zoom_out(self):
        if self.zoom_mgr:
            self.zoom_mgr.zoom_out()
            self._update_zoom_label()

    def _zoom_reset(self):
        if self.zoom_mgr:
            self.zoom_mgr.zoom_reset()
            self._update_zoom_label()

    def _update_zoom_label(self):
        if self.zoom_mgr:
            self.lbl_zoom.config(text=f"{self.zoom_mgr.percent()}%")

    def _refresh_fonts(self):
        if not self.win.winfo_exists():
            return
        try:
            self.text.config(font=("DejaVu Sans Mono", self._fs(12)))
            self._update_zoom_label()
        except tk.TclError:
            pass

    def refresh(self):
        info = get_battery_full_info()
        idle = get_idle_seconds()
        media = is_multimedia_playing()
        sudoers_ok = check_sudoers_configured()
        browser = get_browser_status()
        text = self._format_info(info, idle, media, sudoers_ok, browser)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.config(state="disabled")

    @staticmethod
    def _format_info(info, idle_s, media, sudoers_ok, browser) -> str:
        def fnum(v, unidad="", decimales=2):
            if v is None:
                return "No disponible"
            return f"{v:.{decimales}f} {unidad}".strip()

        def fstr(v):
            return v if v else "No disponible"

        estado_map = {
            "charging": "🔌 Cargando",
            "discharging": "🔋 Descargando",
            "fully-charged": "✅ Completamente cargada",
            "pending-charge": "⏳ Pendiente de carga",
            "pending-discharge": "⏳ Pendiente de descarga",
            "unknown": "❓ Desconocido",
        }

        lines = []
        lines.append("═" * 62)
        lines.append("  ESTADO ACTUAL")
        lines.append("═" * 62)
        lines.append(f"  Estado:             {estado_map.get(info['state'], fstr(info['state']))}")
        lines.append(f"  Nivel de carga:     {fnum(info['percentage'], '%', 0)}")
        lines.append(f"  Energía actual:     {fnum(info['energy'], 'Wh')}")
        lines.append(f"  Potencia (rate):    {fnum(info['energy_rate'], 'W')}")
        lines.append(f"  Voltaje:            {fnum(info['voltage'], 'V')}")
        lines.append(f"  Temperatura:        {fnum(info['temperature'], '°C', 1)}")
        lines.append(f"  Tiempo restante:    {fstr(info['time_to_empty'])}")
        lines.append(f"  Tiempo a completa:  {fstr(info['time_to_full'])}")
        lines.append("")

        lines.append("═" * 62)
        lines.append("  SALUD DE LA BATERÍA")
        lines.append("═" * 62)
        lines.append(f"  energy-full:        {fnum(info['energy_full'], 'Wh')}")
        lines.append(f"  energy-full-design: {fnum(info['energy_full_design'], 'Wh')}")
        lines.append(f"  capacity (salud):   {fnum(info['capacity'], '%')}")
        cycles = info['charge_cycles']
        lines.append(f"  charge-cycles:      "
                     f"{cycles if cycles is not None else 'No reportado por el hardware'}")
        lines.append("")

        cap = info.get("capacity")
        if cap is not None:
            if cap >= 90:
                salud = "🟢 Excelente"
            elif cap >= 80:
                salud = "🟡 Buena"
            elif cap >= 60:
                salud = "🟠 Aceptable (considera reemplazar pronto)"
            elif cap >= 40:
                salud = "🔴 Degradada (reemplazo recomendado)"
            else:
                salud = "⛔ Muy degradada (reemplazo urgente)"
            lines.append(f"  Diagnóstico:        {salud}")
            lines.append("")

        lines.append("═" * 62)
        lines.append("  INACTIVIDAD Y MULTIMEDIA")
        lines.append("═" * 62)
        if idle_s < 0:
            lines.append("  Tiempo inactivo:    No disponible (falta xprintidle)")
        else:
            mins = int(idle_s // 60)
            secs = int(idle_s % 60)
            lines.append(f"  Tiempo inactivo:    {mins} min {secs} s")
        lines.append(f"  Multimedia activa:  {'🎵 SÍ' if media else '🔇 No'}")
        lines.append("")

        lines.append("═" * 62)
        lines.append("  NAVEGADOR")
        lines.append("═" * 62)
        if not _cmd_exists("xdotool"):
            lines.append("  Estado:             ⚠ xdotool NO instalado")
            lines.append("      Instálalo con: sudo apt install xdotool x11-utils")
        else:
            if browser.get("in_use"):
                lines.append(f"  En uso:             🌐 SÍ")
                lines.append(f"  Motivo:             {browser.get('reason', '')}")
            else:
                lines.append(f"  En uso:             ❌ No")
            if browser.get("active_class"):
                lines.append(f"  Ventana activa:     {browser['active_class']}")
            if browser.get("active_title"):
                t = browser['active_title'][:50]
                lines.append(f"  Título activo:      {t}")
        lines.append("")

        lines.append("═" * 62)
        lines.append("  AUTO-APAGADO")
        lines.append("═" * 62)
        if sudoers_ok:
            lines.append("  Sudoers:            ✅ configurado (poweroff OK)")
        else:
            lines.append("  Sudoers:            ❌ NO configurado")
            lines.append(f"      Ejecuta:  sudo bash -c 'echo \"$USER ALL=(ALL) "
                         f"NOPASSWD: {POWEROFF_PATH}\" > {SUDOERS_FILE}'")
        lines.append("")

        lines.append("═" * 62)
        lines.append("  DISPOSITIVO")
        lines.append("═" * 62)
        lines.append(f"  {info['device'] or 'No detectado'}")
        lines.append("")
        return "\n".join(lines)


# =========================================================
#  BANDEJA DEL SISTEMA
# =========================================================
class TrayIcon:

    def __init__(self, app):
        self.app = app
        self.icon = None
        self._thread = None
        self._last_image_key = None
        if not TRAY_AVAILABLE:
            log.warning("pystray/Pillow no disponibles: no habrá icono de bandeja.")
            return
        try:
            self._create_icon()
        except Exception as e:
            log.error(f"Error creando icono de bandeja: {e}")
            self.icon = None

    def _create_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar ventana", self._on_show, default=True),
            pystray.MenuItem("Ocultar ventana", self._on_hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Activar / desactivar monitoreo",
                             self._on_toggle,
                             checked=lambda item: self.app.config["enabled"]),
            pystray.MenuItem("Ver informe de batería", self._on_info),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zoom +", self._on_zoom_in),
            pystray.MenuItem("Zoom -", self._on_zoom_out),
            pystray.MenuItem("Zoom 100%", self._on_zoom_reset),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Auto-apagado",
                             self._on_toggle_shutdown,
                             checked=lambda item: self.app.config.get(
                                 "auto_shutdown_enabled", False)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._on_quit),
        )
        self.icon = pystray.Icon(
            name="battery_guardian",
            icon=make_tray_image(level=None),
            title=APP_NAME, menu=menu)

    def _on_show(self, icon=None, item=None): self.app.root.after(0, self.app.show_window)
    def _on_hide(self, icon=None, item=None): self.app.root.after(0, self.app.hide_window)
    def _on_toggle(self, icon=None, item=None): self.app.root.after(0, self.app.toggle_enabled)
    def _on_toggle_shutdown(self, icon=None, item=None): self.app.root.after(0, self.app.toggle_auto_shutdown)
    def _on_info(self, icon=None, item=None): self.app.root.after(0, self.app.open_info_window)
    def _on_zoom_in(self, icon=None, item=None): self.app.root.after(0, self.app.zoom_in)
    def _on_zoom_out(self, icon=None, item=None): self.app.root.after(0, self.app.zoom_out)
    def _on_zoom_reset(self, icon=None, item=None): self.app.root.after(0, self.app.zoom_reset)
    def _on_quit(self, icon=None, item=None): self.app.root.after(0, self.app.ask_quit)

    def start(self):
        if self.icon is None:
            return
        self._thread = threading.Thread(target=self.icon.run, daemon=True,
                                        name="tray-icon")
        self._thread.start()
        log.info("Icono de bandeja iniciado")

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass

    def update(self, level, charging, alert=False):
        if self.icon is None:
            return
        key = (level, charging, alert)
        if key == self._last_image_key:
            return
        self._last_image_key = key
        try:
            self.icon.icon = make_tray_image(level=level, charging=charging,
                                             alert=alert)
            state_txt = "cargando" if charging else "descargando"
            level_txt = f"{level}%" if level is not None else "-"
            self.icon.title = f"{APP_NAME} - {level_txt} ({state_txt})"
        except Exception as e:
            log.error(f"Error actualizando icono de bandeja: {e}")


# =========================================================
#  APLICACIÓN PRINCIPAL
# =========================================================
class BatteryGuardianApp:

    def __init__(self, root, start_hidden=False):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("660x1120")
        self.root.minsize(600, 760)
        self.root.resizable(True, True)
        self.config = load_config()
        self.alert_active = False
        self.alert_window = None
        self.info_window = None
        self._paused_until = 0
        self._force_quit = False
        self._start_hidden = start_hidden

        apply_modern_styles(self.root)
        self.zoom_mgr = ZoomManager(self.root, self.config.get("zoom", 0.8))

        self._build_ui()
        self.zoom_mgr.apply()
        self.zoom_mgr.add_listener(self._update_zoom_label)

        self._setup_tray()
        self._bind_zoom_keys()
        self._schedule_check(1000)

        self.auto_shutdown = AutoShutdownManager(self)
        self.auto_shutdown.start()

        self._check_sudoers_on_startup()

        if start_hidden:
            self.root.after(500, self.hide_window)

    def _check_sudoers_on_startup(self):
        if self.config.get("auto_shutdown_enabled", False):
            if not check_sudoers_configured():
                log.warning("Auto-apagado activado pero sudoers NO configurado")
                self.root.after(1500, lambda: messagebox.showwarning(
                    APP_NAME,
                    "El auto-apagado está ACTIVADO pero el archivo sudoers\n"
                    "NO está configurado. El equipo NO se apagará.\n\n"
                    "Soluciónalo ejecutando:\n\n"
                    "  sudo bash -c 'echo \"$USER ALL=(ALL) NOPASSWD: "
                    "/usr/sbin/poweroff\" > /etc/sudoers.d/battery-guardian'\n"
                    "  sudo chmod 0440 /etc/sudoers.d/battery-guardian\n\n"
                    "O reinstala con ./install.sh"))

    def _setup_tray(self):
        self.tray = TrayIcon(self)
        self.tray.start()

    def _bind_zoom_keys(self):
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())
        self.root.bind("<Control-MouseWheel>", self._on_wheel)
        self.root.bind("<Control-Button-4>", lambda e: self.zoom_in())
        self.root.bind("<Control-Button-5>", lambda e: self.zoom_out())

    def _on_wheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        self.zoom_mgr.zoom_in()
        self._persist_zoom()

    def zoom_out(self):
        self.zoom_mgr.zoom_out()
        self._persist_zoom()

    def zoom_reset(self):
        self.zoom_mgr.zoom_reset()
        self._persist_zoom()

    def _persist_zoom(self):
        self.config["zoom"] = self.zoom_mgr.zoom
        save_config(self.config)

    def _update_zoom_label(self):
        try:
            self.lbl_zoom.config(text=f"{self.zoom_mgr.percent()}%")
        except Exception:
            pass

    def _build_ui(self):
        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0, bg=COLOR_BG)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas, padding=20)

        self.scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        main = self.scroll_frame

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 4))

        self.lbl_app = ttk.Label(header, text=f"🔋  {APP_NAME}",
                                 style="Title.TLabel")
        self.lbl_app.pack(side="left")

        zbtns = ttk.Frame(header)
        zbtns.pack(side="right")
        self.lbl_zoom = ttk.Label(zbtns, text=f"{self.zoom_mgr.percent()}%",
                                  font=("DejaVu Sans", 11, "bold"))
        self.lbl_zoom.pack(side="right", padx=6)
        ttk.Button(zbtns, text="A+", width=4,
                   command=self.zoom_in).pack(side="right", padx=1)
        ttk.Button(zbtns, text="A−", width=4,
                   command=self.zoom_out).pack(side="right", padx=1)
        ttk.Button(zbtns, text="↺", width=3,
                   command=self.zoom_reset).pack(side="right", padx=1)

        self.lbl_sub = ttk.Label(main,
            text=f"Versión {APP_VERSION}   ·   Cuida la salud de tu batería",
            style="Subtitle.TLabel")
        self.lbl_sub.pack(pady=(0, 14))

        # --------- Tarjeta 1: Control ---------
        card1 = ttk.LabelFrame(main, text="  Control de monitoreo  ",
                               style="Card.TLabelframe")
        card1.pack(fill="x", pady=8)

        self.enabled_var = tk.BooleanVar(value=self.config["enabled"])
        ttk.Checkbutton(card1, text="Activar monitoreo de batería",
                        variable=self.enabled_var,
                        style="Card.TCheckbutton",
                        command=self._on_toggle_check).pack(anchor="w", pady=2)

        self.sound_var = tk.BooleanVar(value=self.config["sound_enabled"])
        ttk.Checkbutton(card1, text="Activar pitido de alerta",
                        variable=self.sound_var,
                        style="Card.TCheckbutton",
                        command=self._save).pack(anchor="w", pady=2)

        self.fullscreen_var = tk.BooleanVar(value=self.config["fullscreen_alert"])
        ttk.Checkbutton(card1, text="Alerta a pantalla completa",
                        variable=self.fullscreen_var,
                        style="Card.TCheckbutton",
                        command=self._save).pack(anchor="w", pady=2)

        # --------- Tarjeta 2: Límites ---------
        card2 = ttk.LabelFrame(main, text="  Límites de carga  ",
                               style="Card.TLabelframe")
        card2.pack(fill="x", pady=8)

        f_max = ttk.Frame(card2, style="Card.TFrame")
        f_max.pack(fill="x", pady=6)
        ttk.Label(f_max, text="Máximo de carga (%):",
                  style="Card.TLabel").pack(side="left")
        self.max_var = tk.IntVar(value=self.config["max_charge"])
        sp_max = ttk.Spinbox(f_max, from_=50, to=100,
                             textvariable=self.max_var, width=6,
                             justify="center")
        sp_max.pack(side="right")
        sp_max.bind("<FocusOut>", lambda e: self._save())
        sp_max.bind("<Return>", lambda e: self._save())

        f_min = ttk.Frame(card2, style="Card.TFrame")
        f_min.pack(fill="x", pady=6)
        ttk.Label(f_min, text="Mínimo de carga (%):",
                  style="Card.TLabel").pack(side="left")
        self.min_var = tk.IntVar(value=self.config["min_charge"])
        sp_min = ttk.Spinbox(f_min, from_=0, to=50,
                             textvariable=self.min_var, width=6,
                             justify="center")
        sp_min.pack(side="right")
        sp_min.bind("<FocusOut>", lambda e: self._save())
        sp_min.bind("<Return>", lambda e: self._save())

        # --------- Tarjeta 3: Auto-apagado ---------
        card3 = ttk.LabelFrame(main, text="  Auto-apagado por inactividad  ",
                               style="Card.TLabelframe")
        card3.pack(fill="x", pady=8)

        self.shutdown_var = tk.BooleanVar(
            value=self.config["auto_shutdown_enabled"])
        ttk.Checkbutton(card3,
                        text="Activar auto-apagado cuando el PC esté inactivo",
                        variable=self.shutdown_var,
                        style="Card.TCheckbutton",
                        command=self._on_toggle_shutdown_check
                        ).pack(anchor="w", pady=4)

        f1 = ttk.Frame(card3, style="Card.TFrame")
        f1.pack(fill="x", pady=6)
        ttk.Label(f1, text="Apagar tras (minutos inactivo):",
                  style="Card.TLabel").pack(side="left")
        self.shutdown_min_var = tk.IntVar(
            value=self.config["auto_shutdown_minutes"])
        sp1 = ttk.Spinbox(f1, from_=1, to=240,
                          textvariable=self.shutdown_min_var,
                          width=6, justify="center")
        sp1.pack(side="right")
        sp1.bind("<FocusOut>", lambda e: self._save())
        sp1.bind("<Return>", lambda e: self._save())

        f2 = ttk.Frame(card3, style="Card.TFrame")
        f2.pack(fill="x", pady=6)
        ttk.Label(f2, text="Aviso previo (segundos):",
                  style="Card.TLabel").pack(side="left")
        self.shutdown_warn_var = tk.IntVar(
            value=self.config["auto_shutdown_warning_seconds"])
        sp2 = ttk.Spinbox(f2, from_=0, to=600,
                          textvariable=self.shutdown_warn_var,
                          width=6, justify="center")
        sp2.pack(side="right")
        sp2.bind("<FocusOut>", lambda e: self._save())
        sp2.bind("<Return>", lambda e: self._save())

        # NUEVA opción: ignorar si el navegador está en uso
        self.ignore_browser_var = tk.BooleanVar(
            value=self.config.get("ignore_browser", True))
        ttk.Checkbutton(card3,
                        text="NO apagar mientras el navegador esté en uso",
                        variable=self.ignore_browser_var,
                        style="Card.TCheckbutton",
                        command=self._on_toggle_ignore_browser).pack(
                            anchor="w", pady=(10, 4))

        self.lbl_idle = ttk.Label(card3, text="Inactividad: —",
                                  style="Muted.TLabel")
        self.lbl_idle.pack(anchor="w", pady=(8, 2))

        self.lbl_media = ttk.Label(card3, text="Multimedia: —",
                                   style="Muted.TLabel")
        self.lbl_media.pack(anchor="w", pady=2)

        self.lbl_browser = ttk.Label(card3, text="Navegador: —",
                                     style="Muted.TLabel")
        self.lbl_browser.pack(anchor="w", pady=2)

        self.lbl_sudoers = ttk.Label(card3, text="Sudoers: —",
                                     style="Muted.TLabel")
        self.lbl_sudoers.pack(anchor="w", pady=2)

        ttk.Label(card3,
                  text=("💡 No apaga si hay multimedia reproduciéndose\n"
                        "   o si el navegador está en uso (vídeo/streaming).\n"
                        "   Requiere 'xdotool' instalado para detectar el navegador."),
                  style="Muted.TLabel",
                  justify="left").pack(anchor="w", pady=(8, 4))

        ttk.Button(card3, text="🧪  Probar aviso de apagado",
                   command=self._test_shutdown_warning
                   ).pack(anchor="w", pady=(6, 2))

        # --------- Tarjeta 4: Info batería ---------
        card4 = ttk.LabelFrame(main, text="  Información de la batería  ",
                               style="Card.TLabelframe")
        card4.pack(fill="x", pady=8)

        self.lbl_state = ttk.Label(card4, text="Estado: —", style="Info.TLabel")
        self.lbl_state.pack(anchor="w", pady=1)
        self.lbl_level = ttk.Label(card4, text="Nivel: —", style="Info.TLabel")
        self.lbl_level.pack(anchor="w", pady=1)
        self.lbl_energy_full = ttk.Label(card4, text="energy-full: —",
                                         style="Info.TLabel")
        self.lbl_energy_full.pack(anchor="w", pady=1)
        self.lbl_capacity = ttk.Label(card4, text="capacity (salud): —",
                                      style="Info.TLabel")
        self.lbl_capacity.pack(anchor="w", pady=1)
        self.lbl_cycles = ttk.Label(card4, text="charge-cycles: —",
                                    style="Info.TLabel")
        self.lbl_cycles.pack(anchor="w", pady=1)

        btns = ttk.Frame(main)
        btns.pack(pady=16)

        ttk.Button(btns, text="💾  Guardar", style="Primary.TButton",
                   command=self._save, width=16
                   ).grid(row=0, column=0, padx=5, pady=4)
        ttk.Button(btns, text="📊  Ver informe completo",
                   command=self.open_info_window, width=24
                   ).grid(row=0, column=1, padx=5, pady=4)
        ttk.Button(btns, text="🧪  Probar alerta batería",
                   command=self._test_alert, width=22
                   ).grid(row=1, column=0, padx=5, pady=4)
        ttk.Button(btns, text="Ocultar en bandeja",
                   command=self.hide_window, width=20
                   ).grid(row=1, column=1, padx=5, pady=4)

        ttk.Label(main,
                  text="💡 Zoom: Ctrl + rueda del ratón  ·  Ctrl + / −  ·  botones A−/A+/↺",
                  style="Subtitle.TLabel").pack(pady=(4, 14))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close_x)

    def show_window(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception as e:
            log.error(f"Error mostrando ventana: {e}")

    def hide_window(self):
        try:
            self.root.withdraw()
        except Exception as e:
            log.error(f"Error ocultando ventana: {e}")

    def toggle_enabled(self):
        self.config["enabled"] = not self.config["enabled"]
        self.enabled_var.set(self.config["enabled"])
        save_config(self.config)

    def toggle_auto_shutdown(self):
        self.config["auto_shutdown_enabled"] = \
            not self.config.get("auto_shutdown_enabled", False)
        self.shutdown_var.set(self.config["auto_shutdown_enabled"])
        save_config(self.config)

    def open_info_window(self):
        if self.info_window is not None and self.info_window.win.winfo_exists():
            self.info_window.refresh()
            self.info_window.win.lift()
            return
        self.info_window = InfoWindow(self.root, self.zoom_mgr)

    def ask_quit(self):
        try:
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass
        if messagebox.askyesno(
            APP_NAME,
            "¿Salir de Battery Guardian?\n\n"
            "Dejará de vigilar la batería hasta que lo vuelvas a abrir\n"
            "o reinicies el equipo."
        ):
            self.quit_app()

    def quit_app(self):
        self._force_quit = True
        log.info("Cerrando Battery Guardian")
        try:
            if self.auto_shutdown:
                self.auto_shutdown.stop()
        except Exception:
            pass
        notify_systemd_stop()
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def _on_toggle_check(self):
        self.config["enabled"] = self.enabled_var.get()
        save_config(self.config)

    def _on_toggle_shutdown_check(self):
        self.config["auto_shutdown_enabled"] = self.shutdown_var.get()
        save_config(self.config)

    def _on_toggle_ignore_browser(self):
        self.config["ignore_browser"] = self.ignore_browser_var.get()
        save_config(self.config)
        log.info(f"ignore_browser = {self.config['ignore_browser']}")

    def _test_shutdown_warning(self):
        dlg = ShutdownCountdownDialog(self.root, 15, 10.0, self.zoom_mgr)
        self.root.wait_window(dlg.win)
        if dlg.confirmed:
            messagebox.showinfo(APP_NAME,
                "Prueba finalizada.\n\n"
                "En condiciones reales, aquí se apagaría el equipo.")
        else:
            messagebox.showinfo(APP_NAME,
                "Prueba cancelada.\n\n"
                "En condiciones reales, no se apagaría el equipo.")

    def _save(self):
        try:
            maxv = int(self.max_var.get())
            minv = int(self.min_var.get())
            shut_min = int(self.shutdown_min_var.get())
            shut_warn = int(self.shutdown_warn_var.get())
        except Exception:
            messagebox.showerror("Error", "Introduce números válidos.")
            return
        if minv >= maxv:
            messagebox.showerror("Error",
                                 "El mínimo debe ser menor que el máximo.")
            return
        if shut_min < 1:
            messagebox.showerror("Error",
                                 "El tiempo de apagado debe ser ≥ 1 minuto.")
            return

        self.config["max_charge"] = maxv
        self.config["min_charge"] = minv
        self.config["enabled"] = self.enabled_var.get()
        self.config["sound_enabled"] = self.sound_var.get()
        self.config["fullscreen_alert"] = self.fullscreen_var.get()
        self.config["zoom"] = self.zoom_mgr.zoom
        self.config["auto_shutdown_enabled"] = self.shutdown_var.get()
        self.config["auto_shutdown_minutes"] = shut_min
        self.config["auto_shutdown_warning_seconds"] = shut_warn
        self.config["ignore_browser"] = self.ignore_browser_var.get()
        save_config(self.config)

    def _test_alert(self):
        if self.alert_active:
            return
        self._save()
        self._show_alert("disconnect")

    def _on_close_x(self):
        self.hide_window()
        if not getattr(self, "_tray_hint_shown", False):
            self._tray_hint_shown = True
            try:
                subprocess.Popen(
                    ["notify-send", "-i", "battery", APP_NAME,
                     "El programa sigue activo en la bandeja del sistema."],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _schedule_check(self, delay_ms):
        self.root.after(delay_ms, self._check_battery)

    def _check_battery(self):
        info = get_battery_full_info()
        state = info["state"]
        level = info["percentage"]
        charging = state in ("charging", "fully-charged")

        if state is None or level is None:
            self.lbl_state.config(text="Estado: ⚠ No se detectó batería")
            self.lbl_level.config(text="Nivel: —")
            self.lbl_energy_full.config(text="energy-full: —")
            self.lbl_capacity.config(text="capacity (salud): —")
            self.lbl_cycles.config(text="charge-cycles: —")
        else:
            estado_map = {
                "charging": "🔌 Cargando",
                "discharging": "🔋 Descargando",
                "fully-charged": "✅ Completamente cargada",
                "pending-charge": "⏳ Pendiente de carga",
                "pending-discharge": "⏳ Pendiente de descarga",
                "unknown": "❓ Desconocido",
            }
            self.lbl_state.config(text=f"Estado: {estado_map.get(state, state)}")
            self.lbl_level.config(text=f"Nivel: {level}%")
            if info["energy_full"] is not None:
                self.lbl_energy_full.config(
                    text=f"energy-full: {info['energy_full']:.2f} Wh")
            else:
                self.lbl_energy_full.config(text="energy-full: No disponible")
            if info["capacity"] is not None:
                self.lbl_capacity.config(
                    text=f"capacity (salud): {info['capacity']:.2f} %")
            else:
                self.lbl_capacity.config(text="capacity (salud): No disponible")
            if info["charge_cycles"] is not None:
                self.lbl_cycles.config(
                    text=f"charge-cycles: {info['charge_cycles']}")
            else:
                self.lbl_cycles.config(
                    text="charge-cycles: No reportado por el hardware")

        idle = get_idle_seconds()
        if idle >= 0:
            m = int(idle // 60)
            s = int(idle % 60)
            self.lbl_idle.config(text=f"Inactividad: {m} min {s} s")
        else:
            self.lbl_idle.config(
                text="Inactividad: no disponible (instala xprintidle)")

        media = is_multimedia_playing()
        self.lbl_media.config(
            text=f"Multimedia: {'🎵 reproduciéndose' if media else '🔇 silencio'}")

        # Navegador
        browser = get_browser_status()
        if not _cmd_exists("xdotool"):
            self.lbl_browser.config(
                text="Navegador: ⚠ xdotool no instalado", style="Warn.TLabel")
        elif browser.get("in_use"):
            self.lbl_browser.config(
                text=f"Navegador: 🌐 EN USO ({browser['reason'][:50]})",
                style="Ok.TLabel")
        else:
            self.lbl_browser.config(
                text="Navegador: ❌ no detectado en uso", style="Muted.TLabel")

        # Sudoers
        sudoers_ok = check_sudoers_configured()
        if sudoers_ok:
            self.lbl_sudoers.config(
                text="Sudoers: ✅ configurado (auto-apagado listo)",
                style="Ok.TLabel")
        else:
            self.lbl_sudoers.config(
                text="Sudoers: ❌ NO configurado (auto-apagado NO funcionará)",
                style="Warn.TLabel")

        if self.tray:
            self.tray.update(level=level, charging=charging,
                             alert=self.alert_active)

        now = time.time()
        if (self.config["enabled"]
                and not self.alert_active
                and state is not None
                and level is not None
                and now >= self._paused_until):
            if state in ("charging", "fully-charged") and \
               level >= self.config["max_charge"]:
                self._show_alert("disconnect")
            elif state == "discharging" and \
                 level <= self.config["min_charge"]:
                self._show_alert("connect")

        self._schedule_check(self.config["check_interval"] * 1000)

    def _show_alert(self, alert_type):
        self.alert_active = True
        try:
            self.root.deiconify()
        except Exception:
            pass
        self.alert_window = AlertWindow(
            self.root, self.config, alert_type,
            self._alert_resolved, self.zoom_mgr)

    def _alert_resolved(self):
        self.alert_active = False
        self.alert_window = None
        self._paused_until = time.time() + 5


# =========================================================
#  MODO CLI
# =========================================================
def print_info_cli():
    info = get_battery_full_info()
    idle = get_idle_seconds()
    media = is_multimedia_playing()
    sudoers_ok = check_sudoers_configured()
    browser = get_browser_status()
    print("=" * 60)
    print(f"  {APP_NAME} v{APP_VERSION} - Informe de batería")
    print("=" * 60)
    print(f"  Dispositivo:        {info['device']}")
    print(f"  Estado:             {info['state']}")
    print(f"  Nivel:              {info['percentage']}%")
    print(f"  Energía actual:     {info['energy']} Wh")
    print(f"  energy-full:        {info['energy_full']} Wh")
    print(f"  energy-full-design: {info['energy_full_design']} Wh")
    print(f"  capacity (salud):   {info['capacity']}%")
    print(f"  charge-cycles:      {info['charge_cycles']}")
    print(f"  Voltaje:            {info['voltage']} V")
    print(f"  Temperatura:        {info['temperature']} °C")
    print("-" * 60)
    if idle >= 0:
        print(f"  Inactividad:        {int(idle // 60)} min {int(idle % 60)} s")
    else:
        print(f"  Inactividad:        no disponible")
    print(f"  Multimedia activa:  {'SÍ' if media else 'No'}")
    print(f"  Navegador en uso:   {'SÍ' if browser.get('in_use') else 'No'}")
    if browser.get("in_use"):
        print(f"      Motivo:         {browser.get('reason', '')}")
    print(f"  Sudoers:            {'✓ OK' if sudoers_ok else '✗ NO CONFIGURADO'}")
    print("=" * 60)


# =========================================================
#  MAIN
# =========================================================
def main():
    setup_logging()

    if "--info" in sys.argv:
        print_info_cli()
        return

    start_hidden = "--hidden" in sys.argv

    log.info(f"Iniciando {APP_NAME} v{APP_VERSION} "
             f"(hidden={start_hidden}, systemd={is_running_under_systemd()})")

    try:
        root = tk.Tk()
    except tk.TclError as e:
        print(f"Error: no se pudo iniciar la interfaz gráfica ({e})")
        sys.exit(1)

    app = BatteryGuardianApp(root, start_hidden=start_hidden)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if app.auto_shutdown:
                app.auto_shutdown.stop()
        except Exception:
            pass
        try:
            if app.tray:
                app.tray.stop()
        except Exception:
            pass
    log.info(f"{APP_NAME} finalizado")


if __name__ == "__main__":
    main()
