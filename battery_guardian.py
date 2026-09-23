
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Battery Guardian v2.2.10
========================
Cuida la salud de la batería de tu portátil Linux.

NOVEDADES v2.2.10:
- Al cerrar una alerta (batería o apagado), la ventana principal
  NO se abre. El programa permanece oculto en la bandeja del sistema.
- Se recuerda si la ventana principal estaba oculta antes de mostrar
  una alerta, para restaurar exactamente ese estado al cerrarla.
- Se mantiene TODA la funcionalidad anterior sin eliminar nada.

NOVEDADES v2.2.9:
- Apagado: usa 'systemctl poweroff' como PRIMER método.
- Manejo robusto de errores: registra cualquier fallo al arrancar.
- Nuevo modo '--debug' para ver errores en la terminal.
- Sistema de excepthook global que escribe traceback al log.

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
import traceback
import threading
import subprocess
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError as _e:
    TRAY_AVAILABLE = False
    _TRAY_IMPORT_ERROR = str(_e)


# =========================================================
# CONSTANTES
# =========================================================
APP_NAME = "Battery Guardian"
APP_VERSION = "2.2.10"
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
    "min_charge": 20,
    "check_interval": 20,
    "sound_enabled": True,
    "sound_repeat_ms": 2500,
    "fullscreen_alert": True,
    "close_to_tray": True,
    "start_hidden": False,
    "zoom": 1.0,
    "auto_shutdown_enabled": False,
    "auto_shutdown_minutes": 10,
    "auto_shutdown_warning_seconds": 20,
    "auto_shutdown_check_interval": 15,
    "ignore_browser_mode": "any",
    "alert_snooze_minutes": 5,
}

ZOOM_MIN = 0.8
ZOOM_MAX = 2.5
ZOOM_STEP = 0.1
MIN_FONT_SIZE = 9

SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/ubuntu/stereo/bell.ogg",
    "/usr/share/sounds/alsa/Front_Center.wav",
]

BROWSER_CLASSES = [
    "firefox", "firefox-esr", "google-chrome", "chrome", "chromium",
    "chromium-browser", "brave-browser", "brave", "microsoft-edge",
    "msedge", "opera", "vivaldi-stable", "vivaldi", "epiphany",
    "midori", "falkon", "qutebrowser", "waterfox", "palemoon",
    "librewolf", "tor-browser", "zen", "nyxt", "surf",
]

VIDEO_KEYWORDS = [
    "youtube", "netflix", "twitch", "vimeo", "dailymotion",
    "prime video", "hbo", "disney+", "disney plus", "spotify",
    "deezer", "soundcloud", "bandcamp", "crunchyroll",
    "hbomax", "paramount+", "peacock", "apple tv", "canal+",
    "rtve", "atresplayer", "movistar+", "filmin",
]

MEDIA_PLAYER_PROCESSES = [
    "vlc", "mpv", "mplayer", "smplayer", "totem", "parole",
    "celluloid", "rhythmbox", "spotify", "audacious", "clementine",
    "banshee", "deadbeef", "mpd", "cmus", "moc", "kodi",
    "plex", "plexmediaplayer", "elisa", "strawberry", "quodlibet",
    "gnome-mplayer", "dragon", "kaffeine", "noatun", "xine", "ffplay",
]

MEDIA_PLAYER_CLASSES = [
    "vlc", "mpv", "mplayer", "smplayer", "totem", "parole",
    "celluloid", "rhythmbox", "spotify", "audacious", "clementine",
    "banshee", "deadbeef", "kodi", "plexmediaplayer",
    "elisa", "strawberry", "quodlibet", "gnome-mplayer",
    "kaffeine", "xine", "ffplay",
]

# Paleta moderna
COLOR_BG = "#0f172a"
COLOR_PANEL = "#1e293b"
COLOR_CARD = "#1e293b"
COLOR_TEXT = "#f8fafc"
COLOR_MUTED = "#94a3b8"
COLOR_PRIMARY = "#3b82f6"
COLOR_SUCCESS = "#22c55e"
COLOR_WARN = "#eab308"
COLOR_DANGER = "#ef4444"
COLOR_BORDER = "#334155"
COLOR_BTN_OFF = "#475569"
COLOR_BTN_ON = "#22c55e"


# =========================================================
# LOGGING
# =========================================================
def setup_logging() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


log = logging.getLogger(APP_NAME)


def install_excepthooks():
    """Registra hooks para capturar cualquier excepción no controlada."""
    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            log.error(f"EXCEPCIÓN NO CONTROLADA:\n{msg}")
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    def _thread_excepthook(args):
        try:
            msg = "".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback))
            log.error(f"EXCEPCIÓN EN HILO '{args.thread.name if args.thread else '?'}':\n{msg}")
        except Exception:
            pass

    try:
        threading.excepthook = _thread_excepthook
    except Exception:
        pass


# =========================================================
# CONFIGURACIÓN
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
# SYSTEMD Y SUDOERS
# =========================================================
def is_running_under_systemd() -> bool:
    return bool(os.environ.get("INVOCATION_ID"))


def notify_systemd_stop() -> None:
    if not is_running_under_systemd():
        return
    try:
        subprocess.Popen(
            ["systemctl", "--user", "stop", SYSTEMD_SERVICE],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def check_sudoers_configured() -> bool:
    if not os.path.exists(SUDOERS_FILE):
        return False
    try:
        result = subprocess.run(
            ["sudo", "-n", POWEROFF_PATH, "--help"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5)
        return result.returncode == 0
    except Exception:
        return False


# =========================================================
# BATERÍA
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
# SONIDO
# =========================================================
def play_sound() -> None:
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
# UTILIDADES X11
# =========================================================
def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _x11_available() -> bool:
    return bool(os.environ.get("DISPLAY"))


def get_active_window_id():
    if not _x11_available() or not _cmd_exists("xdotool"):
        return None
    try:
        wid = subprocess.check_output(
            ["xdotool", "getactivewindow"],
            text=True, timeout=3, stderr=subprocess.DEVNULL).strip()
        return wid or None
    except Exception:
        return None


def get_window_class(wid):
    if not wid or not _x11_available() or not _cmd_exists("xdotool"):
        return None
    try:
        return subprocess.check_output(
            ["xdotool", "getwindowclassname", wid],
            text=True, timeout=3, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def get_window_title(wid):
    if not wid or not _x11_available() or not _cmd_exists("xdotool"):
        return None
    try:
        return subprocess.check_output(
            ["xdotool", "getwindowname", wid],
            text=True, timeout=3, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def is_browser_class(wm_class: str) -> bool:
    if not wm_class:
        return False
    wm_low = wm_class.lower()
    return any(b in wm_low for b in BROWSER_CLASSES)


def is_media_player_class(wm_class: str) -> bool:
    if not wm_class:
        return False
    wm_low = wm_class.lower()
    return any(m in wm_low for m in MEDIA_PLAYER_CLASSES)


def is_window_fullscreen(wid: str) -> bool:
    if not wid or not _x11_available() or not _cmd_exists("xprop"):
        return False
    try:
        out = subprocess.check_output(
            ["xprop", "-id", wid, "_NET_WM_STATE"],
            text=True, timeout=3, stderr=subprocess.DEVNULL)
        return "FULLSCREEN" in out.upper()
    except Exception:
        return False


def get_all_visible_windows() -> list:
    if not _x11_available() or not _cmd_exists("xdotool"):
        return []
    try:
        out = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--name", ".*"],
            text=True, timeout=4, stderr=subprocess.DEVNULL)
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


def get_vault_config_value(key: str):
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get(key)
    except Exception:
        pass
    return None


def get_browser_status() -> dict:
    result = {"in_use": False, "reason": "", "active_class": "", "active_title": ""}
    mode = get_vault_config_value("ignore_browser_mode") or "any"
    if mode == "off":
        result["reason"] = "Detección de navegador desactivada"
        return result

    if not _x11_available() or not _cmd_exists("xdotool"):
        result["reason"] = "xdotool no disponible"
        return result

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

    browser_windows = []
    for w, wm_class, title in get_all_visible_windows():
        if is_browser_class(wm_class):
            browser_windows.append((w, wm_class, title))

    if not browser_windows:
        return result

    for w, wm_class, title in browser_windows:
        if is_window_fullscreen(w):
            result["in_use"] = True
            result["reason"] = f"Navegador a pantalla completa ({wm_class})"
            return result

    for w, wm_class, title in browser_windows:
        title_low = title.lower()
        for kw in VIDEO_KEYWORDS:
            if kw in title_low:
                result["in_use"] = True
                result["reason"] = f"Título contiene '{kw}': {title[:60]}"
                return result

    if is_multimedia_playing():
        result["in_use"] = True
        result["reason"] = "Navegador abierto + multimedia reproduciéndose"
        return result

    if mode == "any":
        _, wm_class, _ = browser_windows[0]
        result["in_use"] = True
        result["reason"] = f"Navegador visible ({wm_class})"
        return result

    return result


def get_idle_seconds() -> float:
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
    return -1.0


def is_media_player_running() -> bool:
    try:
        out = subprocess.check_output(
            ["ps", "-eo", "comm"],
            text=True, timeout=3, stderr=subprocess.DEVNULL).lower()
        lines = set(line.strip() for line in out.splitlines())
        for proc in MEDIA_PLAYER_PROCESSES:
            for line in lines:
                if line == proc or line.startswith(proc + " ") or line.startswith(proc + "-"):
                    return True
    except Exception:
        pass
    return False


def is_media_player_window_visible() -> bool:
    if not _x11_available() or not _cmd_exists("xdotool"):
        return False
    try:
        for wid, wm_class, title in get_all_visible_windows():
            if is_media_player_class(wm_class):
                return True
            title_low = (title or "").lower()
            if "vlc" in title_low or "mpv" in title_low:
                return True
    except Exception:
        pass
    return False


def is_multimedia_playing() -> bool:
    if _cmd_exists("pactl"):
        try:
            out = subprocess.check_output(
                ["pactl", "list", "sink-inputs"],
                text=True, timeout=3, stderr=subprocess.DEVNULL)
            if out.lower().count("state: running") > 0:
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

    if is_media_player_running():
        return True

    if is_media_player_window_visible():
        return True

    return False


# =========================================================
# GESTOR DE ZOOM GLOBAL
# =========================================================
class ZoomManager:
    BASE_STYLE_FONTS = {
        "TLabel": ("Sans Serif", 10, "normal"),
        "Card.TLabel": ("Sans Serif", 10, "normal"),
        "Title.TLabel": ("Sans Serif", 18, "bold"),
        "Subtitle.TLabel": ("Sans Serif", 9, "italic"),
        "Section.TLabel": ("Sans Serif", 12, "bold"),
        "Muted.TLabel": ("Sans Serif", 9, "normal"),
        "Info.TLabel": ("Sans Serif", 10, "normal"),
        "Ok.TLabel": ("Sans Serif", 10, "bold"),
        "Warn.TLabel": ("Sans Serif", 10, "bold"),
        "BigVal.TLabel": ("Sans Serif", 22, "bold"),
        "BigOk.TLabel": ("Sans Serif", 22, "bold"),
        "BigWarn.TLabel": ("Sans Serif", 22, "bold"),
        "BigDanger.TLabel": ("Sans Serif", 22, "bold"),
        "TButton": ("Sans Serif", 10, "normal"),
        "Primary.TButton": ("Sans Serif", 10, "bold"),
        "Danger.TButton": ("Sans Serif", 10, "bold"),
        "TCheckbutton": ("Sans Serif", 10, "normal"),
        "Card.TCheckbutton": ("Sans Serif", 10, "normal"),
        "Card.TLabelframe.Label": ("Sans Serif", 11, "bold"),
        "TSpinbox": ("Sans Serif", 10, "normal"),
        "TCombobox": ("Sans Serif", 10, "normal"),
    }

    def __init__(self, root: tk.Tk, style: ttk.Style, initial_zoom: float = 1.0):
        self.root = root
        self.style = style
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, float(initial_zoom)))
        self._widget_fonts = []
        self._listeners = []

    def register_widget(self, widget, family: str, base_size: int,
                        weight: str = "normal") -> None:
        self._widget_fonts.append((widget, family, base_size, weight))
        try:
            widget.config(font=(family, self.scaled(base_size), weight))
        except Exception:
            pass

    def scaled(self, base_size: int) -> int:
        return max(MIN_FONT_SIZE, int(round(base_size * self.zoom)))

    def set_zoom(self, value: float) -> None:
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, round(float(value), 2)))
        self.apply()

    def zoom_in(self):
        self.set_zoom(self.zoom + ZOOM_STEP)

    def zoom_out(self):
        self.set_zoom(self.zoom - ZOOM_STEP)

    def zoom_reset(self):
        self.set_zoom(1.0)

    def percent(self) -> int:
        return int(round(self.zoom * 100))

    def add_listener(self, cb) -> None:
        self._listeners.append(cb)

    def apply(self) -> None:
        for style_name, (family, base, weight) in self.BASE_STYLE_FONTS.items():
            try:
                self.style.configure(style_name,
                                     font=(family, self.scaled(base), weight))
            except Exception:
                pass

        alive = []
        for widget, family, base, weight in self._widget_fonts:
            try:
                widget.config(font=(family, self.scaled(base), weight))
                alive.append((widget, family, base, weight))
            except Exception:
                pass
        self._widget_fonts = alive

        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass


# =========================================================
# ESTILOS MODERNOS
# =========================================================
def apply_modern_styles(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=COLOR_BG)

    style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT,
                    fieldbackground=COLOR_PANEL)
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Card.TFrame", background=COLOR_PANEL, relief="flat")

    style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                    font=("Sans Serif", 10))
    style.configure("Card.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_TEXT, font=("Sans Serif", 10))
    style.configure("Title.TLabel", background=COLOR_BG,
                    foreground=COLOR_TEXT, font=("Sans Serif", 18, "bold"))
    style.configure("Subtitle.TLabel", background=COLOR_BG,
                    foreground=COLOR_MUTED, font=("Sans Serif", 9, "italic"))
    style.configure("Section.TLabel", background=COLOR_BG,
                    foreground=COLOR_PRIMARY, font=("Sans Serif", 12, "bold"))
    style.configure("Muted.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_MUTED, font=("Sans Serif", 9))
    style.configure("Info.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_TEXT, font=("Sans Serif", 10))
    style.configure("Ok.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_SUCCESS, font=("Sans Serif", 10, "bold"))
    style.configure("Warn.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_DANGER, font=("Sans Serif", 10, "bold"))
    style.configure("BigVal.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_TEXT, font=("Sans Serif", 22, "bold"))
    style.configure("BigOk.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_SUCCESS, font=("Sans Serif", 22, "bold"))
    style.configure("BigWarn.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_WARN, font=("Sans Serif", 22, "bold"))
    style.configure("BigDanger.TLabel", background=COLOR_PANEL,
                    foreground=COLOR_DANGER, font=("Sans Serif", 22, "bold"))

    style.configure("TButton", font=("Sans Serif", 10), padding=6, relief="flat")
    style.map("TButton",
              background=[("active", COLOR_BORDER), ("!active", COLOR_PANEL)],
              foreground=[("active", COLOR_TEXT), ("!active", COLOR_TEXT)])

    style.configure("Primary.TButton", font=("Sans Serif", 10, "bold"),
                    padding=8, background=COLOR_PRIMARY, foreground="white")
    style.map("Primary.TButton",
              background=[("active", "#2563eb"), ("!active", COLOR_PRIMARY)],
              foreground=[("active", "white"), ("!active", "white")])

    style.configure("Danger.TButton", font=("Sans Serif", 10, "bold"),
                    padding=8, background=COLOR_DANGER, foreground="white")
    style.map("Danger.TButton",
              background=[("active", "#dc2626"), ("!active", COLOR_DANGER)],
              foreground=[("active", "white"), ("!active", "white")])

    style.configure("Card.TLabelframe", background=COLOR_PANEL,
                    foreground=COLOR_PRIMARY, borderwidth=1, relief="solid",
                    bordercolor=COLOR_BORDER, padding=10)
    style.configure("Card.TLabelframe.Label", background=COLOR_PANEL,
                    foreground=COLOR_PRIMARY, font=("Sans Serif", 11, "bold"))

    style.configure("TCheckbutton", background=COLOR_BG, foreground=COLOR_TEXT,
                    font=("Sans Serif", 10))
    style.map("TCheckbutton", background=[("active", COLOR_BG)])
    style.configure("Card.TCheckbutton", background=COLOR_PANEL,
                    foreground=COLOR_TEXT, font=("Sans Serif", 10))
    style.map("Card.TCheckbutton", background=[("active", COLOR_PANEL)])

    style.configure("TSeparator", background=COLOR_BORDER)
    style.configure("TSpinbox", fieldbackground=COLOR_PANEL,
                    background=COLOR_PANEL, foreground=COLOR_TEXT,
                    arrowcolor=COLOR_TEXT)
    style.configure("TCombobox", fieldbackground=COLOR_PANEL,
                    background=COLOR_PANEL, foreground=COLOR_TEXT,
                    arrowcolor=COLOR_TEXT)
    return style


# =========================================================
# TOGGLE BUTTON
# =========================================================
class ToggleButton(tk.Frame):
    def __init__(self, parent, text: str, variable: tk.BooleanVar,
                 command=None, zoom_mgr: ZoomManager = None,
                 bg=COLOR_PANEL, width=32):
        super().__init__(parent, bg=bg)
        self.variable = variable
        self.text_base = text
        self.command = command
        self.zoom_mgr = zoom_mgr
        self.bg = bg

        self.btn = tk.Button(
            self,
            text=self._label_for_state(),
            font=("Sans Serif", 11, "bold"),
            relief="flat", borderwidth=0,
            cursor="hand2", padx=14, pady=10,
            anchor="w", width=width,
            command=self._on_click,
        )
        self.btn.pack(fill="x")
        self._apply_color()

        if zoom_mgr:
            zoom_mgr.register_widget(self.btn, "Sans Serif", 11, "bold")

    def _label_for_state(self) -> str:
        if self.variable.get():
            return f"  ✓  {self.text_base}"
        return f"  ○  {self.text_base}"

    def _apply_color(self):
        try:
            if self.variable.get():
                self.btn.config(bg=COLOR_BTN_ON, fg="white",
                                activebackground="#16a34a",
                                activeforeground="white")
            else:
                self.btn.config(bg=COLOR_BTN_OFF, fg="white",
                                activebackground=COLOR_BORDER,
                                activeforeground="white")
        except Exception:
            pass

    def _on_click(self):
        self.variable.set(not self.variable.get())
        try:
            self.btn.config(text=self._label_for_state())
        except Exception:
            pass
        self._apply_color()
        if self.command:
            try:
                self.command()
            except Exception as e:
                log.error(f"Error en toggle command: {e}")

    def refresh(self):
        try:
            self.btn.config(text=self._label_for_state())
        except Exception:
            pass
        self._apply_color()


# =========================================================
# ICONO DE LA BANDEJA
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
            draw.polygon([(32, 20), (26, 34), (31, 34), (28, 44), (38, 30),
                          (33, 30), (36, 20)],
                         fill="#FFF176", outline="#FFF176")
    return img


# =========================================================
# VENTANA DE ALERTA
# =========================================================
class AlertWindow:

    def __init__(self, parent, config, alert_type, on_resolved,
                 zoom_mgr=None, on_snooze=None):
        self.config = config
        self.alert_type = alert_type
        self.on_resolved = on_resolved
        self.on_snooze = on_snooze
        self.zoom_mgr = zoom_mgr
        self._running = True
        self._manual_closed = False

        def fs(base):
            if zoom_mgr:
                return max(MIN_FONT_SIZE, zoom_mgr.scaled(base))
            return max(MIN_FONT_SIZE, base)

        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - ALERTA")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", lambda: self._manual_close())

        if config.get("fullscreen_alert", True):
            try:
                self.win.attributes("-fullscreen", True)
            except Exception:
                self.win.geometry("900x700")
        else:
            self.win.geometry("900x700")
            self.win.update_idletasks()
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            self.win.geometry(f"900x700+{(sw - 900) // 2}+{(sh - 700) // 2}")

        bg = "#7f1d1d" if alert_type == "disconnect" else "#78350f"
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
                                  font=("Sans Serif", fs(36), "bold"),
                                  fg="white", bg=bg)
        self.lbl_title.pack(pady=20)

        self.lbl_msg = tk.Label(frame, text=msg,
                                font=("Sans Serif", fs(20)),
                                fg="white", bg=bg, justify="center")
        self.lbl_msg.pack(pady=15)

        self.status_label = tk.Label(frame, text="",
                                     font=("Sans Serif", fs(14)),
                                     fg="#FDE68A", bg=bg, justify="center")
        self.status_label.pack(pady=10)

        btn_frame = tk.Frame(frame, bg=bg)
        btn_frame.pack(pady=20)

        self.btn_close = tk.Button(
            btn_frame,
            text="✓   CERRAR ALERTA (ya lo hice)",
            font=("Sans Serif", fs(18), "bold"),
            bg="#22c55e", fg="white",
            activebackground="#16a34a", activeforeground="white",
            relief="flat", padx=40, pady=18, borderwidth=0,
            cursor="hand2", command=self._manual_close)
        self.btn_close.pack()

        tk.Label(frame,
                 text="(si el aviso no se cierra solo, pulsa el botón verde)",
                 font=("Sans Serif", fs(11), "italic"),
                 fg="#FECACA", bg=bg).pack(pady=8)

        if zoom_mgr:
            zoom_mgr.register_widget(self.lbl_title, "Sans Serif", 36, "bold")
            zoom_mgr.register_widget(self.lbl_msg, "Sans Serif", 20, "normal")
            zoom_mgr.register_widget(self.status_label, "Sans Serif", 14, "normal")
            zoom_mgr.register_widget(self.btn_close, "Sans Serif", 18, "bold")

        self._sound_loop()
        self._check_loop()
        log.info(f"Alerta mostrada: {alert_type}")

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
        if self._manual_closed:
            return

        state, level = get_battery()
        resolved = False
        charging_states = ("charging", "fully-charged", "pending-charge")
        discharging_states = ("discharging", "pending-discharge")

        if self.alert_type == "disconnect":
            if state in discharging_states:
                resolved = True
        else:
            if state in charging_states:
                resolved = True

        if resolved:
            log.info(f"Alerta resuelta automáticamente "
                     f"(state={state}, level={level})")
            self._close()
            return

        state_txt = state if state else "desconocido"
        level_txt = f"{level}%" if level is not None else "N/D"
        try:
            self.status_label.config(
                text=f"Estado actual: {state_txt}   |   Nivel: {level_txt}\n\n"
                     f"Si ya realizaste la acción, pulsa el botón verde.")
        except tk.TclError:
            return
        self.win.after(2000, self._check_loop)

    def _manual_close(self):
        log.info(f"Alerta cerrada MANUALMENTE: {self.alert_type}")
        self._manual_closed = True
        if self.on_snooze:
            try:
                self.on_snooze(self.alert_type)
            except Exception as e:
                log.error(f"Error en on_snooze: {e}")
        self._close()

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
        if self.on_resolved:
            self.on_resolved()


# =========================================================
# DIÁLOGO CUENTA ATRÁS APAGADO
# =========================================================
class ShutdownCountdownDialog:

    def __init__(self, parent, seconds, minutes_idle, zoom_mgr=None):
        self.cancelled = False
        self.confirmed = False
        self.remaining = seconds
        self.minutes_idle = minutes_idle
        self.zoom_mgr = zoom_mgr

        def fs(base):
            return zoom_mgr.scaled(base) if zoom_mgr else max(MIN_FONT_SIZE, base)

        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - Apagado automático")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self.win.resizable(False, False)
        self.win.configure(bg=COLOR_PANEL)

        w, h = 720, 620
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        try:
            self.win.grab_set()
        except Exception:
            pass

        header = tk.Frame(self.win, bg=COLOR_DANGER, height=110)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.lbl_head = tk.Label(header,
                 text="⚠   APAGADO AUTOMÁTICO   ⚠",
                 font=("Sans Serif", fs(22), "bold"),
                 fg="white", bg=COLOR_DANGER)
        self.lbl_head.pack(expand=True)

        body = tk.Frame(self.win, bg=COLOR_PANEL, padx=30, pady=25)
        body.pack(fill="both", expand=True)

        self.lbl_info = tk.Label(
            body,
            text=f"El equipo lleva {self.minutes_idle:.1f} minutos inactivo",
            font=("Sans Serif", fs(14)),
            fg=COLOR_TEXT, bg=COLOR_PANEL)
        self.lbl_info.pack(pady=(0, 10))

        self.lbl_count = tk.Label(body, text=str(self.remaining),
                                  font=("Sans Serif", fs(72), "bold"),
                                  fg=COLOR_DANGER, bg=COLOR_PANEL)
        self.lbl_count.pack()
        self.lbl_secs = tk.Label(body, text="segundos",
                 font=("Sans Serif", fs(14)),
                 fg=COLOR_MUTED, bg=COLOR_PANEL)
        self.lbl_secs.pack(pady=(0, 20))

        self.btn_stop = tk.Button(
            body,
            text="🛑  DETENER APAGADO  🛑",
            font=("Sans Serif", fs(26), "bold"),
            bg="#22c55e", fg="white",
            activebackground="#16a34a", activeforeground="white",
            relief="flat", padx=40, pady=28, borderwidth=0,
            cursor="hand2",
            command=self._cancel,
        )
        self.btn_stop.pack(fill="x", pady=(0, 10))

        self.lbl_hint = tk.Label(
            body,
            text="Pulsa el botón verde para cancelar el apagado",
            font=("Sans Serif", fs(11), "italic"),
            fg=COLOR_MUTED, bg=COLOR_PANEL)
        self.lbl_hint.pack()

        self.btn_now = tk.Button(
            body,
            text="⏻   Apagar YA",
            font=("Sans Serif", fs(11)),
            bg="#475569", fg="white",
            activebackground="#334155", activeforeground="white",
            relief="flat", padx=20, pady=8, borderwidth=0,
            cursor="hand2",
            command=self._confirm_now)
        self.btn_now.pack(pady=(20, 0))

        if zoom_mgr:
            zoom_mgr.register_widget(self.lbl_head, "Sans Serif", 22, "bold")
            zoom_mgr.register_widget(self.lbl_info, "Sans Serif", 14, "normal")
            zoom_mgr.register_widget(self.lbl_count, "Sans Serif", 72, "bold")
            zoom_mgr.register_widget(self.lbl_secs, "Sans Serif", 14, "normal")
            zoom_mgr.register_widget(self.btn_stop, "Sans Serif", 26, "bold")
            zoom_mgr.register_widget(self.lbl_hint, "Sans Serif", 11, "italic")
            zoom_mgr.register_widget(self.btn_now, "Sans Serif", 11, "normal")

        self.win.bind("<Escape>", lambda e: self._cancel())
        self.win.bind("<Return>", lambda e: self._cancel())
        self.win.bind("<space>", lambda e: self._cancel())
        self._tick()

    def _tick(self):
        if self.cancelled or self.confirmed:
            return
        if self.remaining <= 0:
            self._confirm_now()
            return
        try:
            self.lbl_count.config(text=str(self.remaining))
        except tk.TclError:
            return
        self.remaining -= 1
        self.win.after(1000, self._tick)

    def _cancel(self):
        self.cancelled = True
        try:
            self.win.grab_release()
            self.win.destroy()
        except Exception:
            pass

    def _confirm_now(self):
        self.confirmed = True
        try:
            self.win.grab_release()
            self.win.destroy()
        except Exception:
            pass


# =========================================================
# VENTANA DE INFORMACIÓN (PANTALLA COMPLETA)
# =========================================================
class InfoWindow:

    def __init__(self, parent, zoom_mgr=None):
        self.zoom_mgr = zoom_mgr
        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - Informe completo")
        self.win.configure(bg=COLOR_BG)

        try:
            self.win.attributes("-fullscreen", True)
        except Exception:
            self.win.geometry("1400x900")

        self.win.bind("<Escape>", lambda e: self.win.destroy())

        header = tk.Frame(self.win, bg=COLOR_BG, padx=24, pady=16)
        header.pack(fill="x")

        self.lbl_title = tk.Label(header, text="📊  Informe completo de la batería",
                                  font=("Sans Serif", 22, "bold"),
                                  bg=COLOR_BG, fg=COLOR_TEXT)
        self.lbl_title.pack(side="left")

        zbtns = tk.Frame(header, bg=COLOR_BG)
        zbtns.pack(side="right")
        self.lbl_zoom = tk.Label(zbtns,
                                 text=f"{zoom_mgr.percent() if zoom_mgr else 100}%",
                                 font=("Sans Serif", 12, "bold"),
                                 bg=COLOR_BG, fg=COLOR_TEXT)
        self.lbl_zoom.pack(side="right", padx=10)

        def _mk(text, cmd):
            return tk.Button(zbtns, text=text, font=("Sans Serif", 12, "bold"),
                             bg=COLOR_PANEL, fg=COLOR_TEXT,
                             activebackground=COLOR_BORDER,
                             activeforeground=COLOR_TEXT,
                             relief="flat", padx=14, pady=6, cursor="hand2",
                             command=cmd)

        _mk("A+", self._zoom_in).pack(side="right", padx=3)
        _mk("A−", self._zoom_out).pack(side="right", padx=3)
        _mk("↺", self._zoom_reset).pack(side="right", padx=3)

        tk.Button(header, text="✕  Cerrar  (Esc)",
                  font=("Sans Serif", 12, "bold"),
                  bg=COLOR_DANGER, fg="white",
                  activebackground="#b91c1c", activeforeground="white",
                  relief="flat", padx=18, pady=8, cursor="hand2",
                  command=self.win.destroy).pack(side="right", padx=(0, 20))

        tk.Frame(self.win, bg=COLOR_BORDER, height=1).pack(fill="x")

        cols = tk.Frame(self.win, bg=COLOR_BG, padx=20, pady=16)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, uniform="col")
        cols.columnconfigure(1, weight=1, uniform="col")
        cols.columnconfigure(2, weight=1, uniform="col")
        cols.rowconfigure(0, weight=1)

        self.labels = {}

        # Columna 1
        col1 = tk.Frame(cols, bg=COLOR_BG)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self._make_card(col1, "🔋 Estado actual", [
            ("level_big", "—", "big"),
            ("state", "—", "normal"),
            ("energy", "—", "normal"),
            ("rate", "—", "normal"),
            ("voltage", "—", "normal"),
            ("temperature", "—", "normal"),
            ("time_left", "—", "normal"),
            ("time_full", "—", "normal"),
        ])

        self._make_card(col1, "🧠 Salud de la batería", [
            ("energy_full", "—", "normal"),
            ("energy_full_design", "—", "normal"),
            ("capacity", "—", "normal"),
            ("capacity_diag", "—", "normal"),
            ("cycles", "—", "normal"),
        ])

        # Columna 2
        col2 = tk.Frame(cols, bg=COLOR_BG)
        col2.grid(row=0, column=1, sticky="nsew", padx=10)

        self._make_card(col2, "⏱ Inactividad y multimedia", [
            ("idle_time", "—", "normal"),
            ("media_playing", "—", "normal"),
            ("media_process", "—", "normal"),
            ("media_window", "—", "normal"),
            ("browser_in_use", "—", "normal"),
            ("browser_reason", "—", "normal"),
            ("browser_class", "—", "normal"),
        ])

        self._make_card(col2, "⏻ Auto-apagado", [
            ("sudoers", "—", "normal"),
            ("shutdown_enabled", "—", "normal"),
            ("shutdown_minutes", "—", "normal"),
            ("browser_mode", "—", "normal"),
        ])

        # Columna 3
        col3 = tk.Frame(cols, bg=COLOR_BG)
        col3.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        self._make_card(col3, "⚙️ Configuración actual", [
            ("cfg_max", "—", "normal"),
            ("cfg_min", "—", "normal"),
            ("cfg_sound", "—", "normal"),
            ("cfg_fullscreen", "—", "normal"),
            ("cfg_zoom", "—", "normal"),
        ])

        self._make_card(col3, "🖥 Dispositivo", [
            ("device", "—", "normal"),
            ("app_version", f"{APP_NAME} v{APP_VERSION}", "normal"),
        ])

        footer = tk.Frame(self.win, bg=COLOR_BG, padx=20, pady=12)
        footer.pack(fill="x")
        tk.Button(footer, text="🔄  Actualizar datos",
                  font=("Sans Serif", 12, "bold"),
                  bg=COLOR_PRIMARY, fg="white",
                  activebackground="#2563eb", activeforeground="white",
                  relief="flat", padx=20, pady=10, cursor="hand2",
                  command=self.refresh).pack(side="right")

        if zoom_mgr:
            zoom_mgr.register_widget(self.lbl_title, "Sans Serif", 22, "bold")
            zoom_mgr.register_widget(self.lbl_zoom, "Sans Serif", 12, "bold")
            zoom_mgr.add_listener(self._on_zoom_changed)

        self.refresh()

    def _make_card(self, parent, title, rows):
        card = tk.Frame(parent, bg=COLOR_PANEL, highlightthickness=1,
                        highlightbackground=COLOR_BORDER)
        card.pack(fill="x", pady=(0, 14))

        title_lbl = tk.Label(card, text=title, font=("Sans Serif", 14, "bold"),
                             bg=COLOR_PANEL, fg=COLOR_PRIMARY, anchor="w",
                             padx=14, pady=10)
        title_lbl.pack(fill="x")
        tk.Frame(card, bg=COLOR_BORDER, height=1).pack(fill="x")

        grid = tk.Frame(card, bg=COLOR_PANEL, padx=14, pady=10)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=0)
        grid.columnconfigure(1, weight=1)

        for i, (key, _val, kind) in enumerate(rows):
            label_widget = tk.Label(
                grid,
                text=self._pretty_label(key),
                font=("Sans Serif", 10, "normal"),
                bg=COLOR_PANEL, fg=COLOR_MUTED, anchor="w")
            label_widget.grid(row=i, column=0, sticky="w", padx=(0, 10), pady=4)

            if kind == "big":
                val_lbl = tk.Label(grid, text="—",
                                   font=("Sans Serif", 32, "bold"),
                                   bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w")
            else:
                val_lbl = tk.Label(grid, text="—",
                                   font=("Sans Serif", 11, "normal"),
                                   bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w",
                                   justify="left", wraplength=380)
            val_lbl.grid(row=i, column=1, sticky="w", pady=4)

            self.labels[key] = val_lbl

            if self.zoom_mgr:
                if kind == "big":
                    self.zoom_mgr.register_widget(val_lbl, "Sans Serif", 32, "bold")
                else:
                    self.zoom_mgr.register_widget(val_lbl, "Sans Serif", 11, "normal")
                self.zoom_mgr.register_widget(label_widget, "Sans Serif", 10, "normal")

        if self.zoom_mgr:
            self.zoom_mgr.register_widget(title_lbl, "Sans Serif", 14, "bold")

    @staticmethod
    def _pretty_label(key: str) -> str:
        mapping = {
            "level_big": "Nivel",
            "state": "Estado",
            "energy": "Energía actual",
            "rate": "Potencia",
            "voltage": "Voltaje",
            "temperature": "Temperatura",
            "time_left": "Tiempo restante",
            "time_full": "Tiempo a completa",
            "energy_full": "energy-full",
            "energy_full_design": "energy-full-design",
            "capacity": "capacity (salud)",
            "capacity_diag": "Diagnóstico",
            "cycles": "charge-cycles",
            "idle_time": "Tiempo inactivo",
            "media_playing": "Multimedia activa",
            "media_process": "Reproductor activo",
            "media_window": "Ventana reproductor",
            "browser_in_use": "Navegador en uso",
            "browser_reason": "Motivo",
            "browser_class": "Ventana activa",
            "sudoers": "Sudoers",
            "shutdown_enabled": "Auto-apagado",
            "shutdown_minutes": "Apagar tras",
            "browser_mode": "Modo navegador",
            "cfg_max": "Máximo carga",
            "cfg_min": "Mínimo carga",
            "cfg_sound": "Pitido",
            "cfg_fullscreen": "Alerta fullscreen",
            "cfg_zoom": "Zoom",
            "device": "Dispositivo",
            "app_version": "Versión",
        }
        return mapping.get(key, key)

    def _on_zoom_changed(self):
        if not self.win.winfo_exists():
            return
        try:
            if self.zoom_mgr:
                self.lbl_zoom.config(text=f"{self.zoom_mgr.percent()}%")
        except tk.TclError:
            pass

    def _zoom_in(self):
        if self.zoom_mgr:
            self.zoom_mgr.zoom_in()
            self._on_zoom_changed()

    def _zoom_out(self):
        if self.zoom_mgr:
            self.zoom_mgr.zoom_out()
            self._on_zoom_changed()

    def _zoom_reset(self):
        if self.zoom_mgr:
            self.zoom_mgr.zoom_reset()
            self._on_zoom_changed()

    def refresh(self):
        info = get_battery_full_info()
        idle = get_idle_seconds()
        media = is_multimedia_playing()
        sudoers_ok = check_sudoers_configured()
        browser = get_browser_status()

        def fnum(v, unidad="", dec=2):
            if v is None:
                return "No disponible"
            return f"{v:.{dec}f} {unidad}".strip()

        def fbool(v):
            return "✅ SÍ" if v else "❌ No"

        estado_map = {
            "charging": "🔌 Cargando",
            "discharging": "🔋 Descargando",
            "fully-charged": "✅ Completamente cargada",
            "pending-charge": "⏳ Pendiente de carga",
            "pending-discharge": "⏳ Pendiente de descarga",
            "unknown": "❓ Desconocido",
        }

        try:
            pct = info["percentage"]
            if pct is None:
                self.labels["level_big"].config(text="—", fg=COLOR_TEXT)
            else:
                if pct <= 20:
                    color = COLOR_DANGER
                elif pct <= 40:
                    color = COLOR_WARN
                else:
                    color = COLOR_SUCCESS
                self.labels["level_big"].config(text=f"{pct}%", fg=color)

            self.labels["state"].config(
                text=estado_map.get(info["state"], info["state"] or "—"))
            self.labels["energy"].config(text=fnum(info["energy"], "Wh"))
            self.labels["rate"].config(text=fnum(info["energy_rate"], "W"))
            self.labels["voltage"].config(text=fnum(info["voltage"], "V"))
            self.labels["temperature"].config(text=fnum(info["temperature"], "°C", 1))
            self.labels["time_left"].config(text=info["time_to_empty"] or "—")
            self.labels["time_full"].config(text=info["time_to_full"] or "—")

            self.labels["energy_full"].config(text=fnum(info["energy_full"], "Wh"))
            self.labels["energy_full_design"].config(
                text=fnum(info["energy_full_design"], "Wh"))
            self.labels["capacity"].config(text=fnum(info["capacity"], "%"))
            cap = info.get("capacity")
            if cap is None:
                diag, color = "—", COLOR_MUTED
            elif cap >= 90:
                diag, color = "🟢 Excelente", COLOR_SUCCESS
            elif cap >= 80:
                diag, color = "🟡 Buena", COLOR_SUCCESS
            elif cap >= 60:
                diag, color = "🟠 Aceptable", COLOR_WARN
            elif cap >= 40:
                diag, color = "🔴 Degradada", COLOR_DANGER
            else:
                diag, color = "⛔ Muy degradada", COLOR_DANGER
            self.labels["capacity_diag"].config(text=diag, fg=color)

            self.labels["cycles"].config(
                text=str(info["charge_cycles"]) if info["charge_cycles"] is not None
                else "No reportado")

            if idle < 0:
                self.labels["idle_time"].config(text="No disponible")
            else:
                self.labels["idle_time"].config(
                    text=f"{int(idle // 60)} min {int(idle % 60)} s")

            self.labels["media_playing"].config(
                text=fbool(media),
                fg=COLOR_SUCCESS if media else COLOR_MUTED)
            self.labels["media_process"].config(
                text=fbool(is_media_player_running()),
                fg=COLOR_SUCCESS if is_media_player_running() else COLOR_MUTED)
            self.labels["media_window"].config(
                text=fbool(is_media_player_window_visible()),
                fg=COLOR_SUCCESS if is_media_player_window_visible() else COLOR_MUTED)

            self.labels["browser_in_use"].config(
                text=fbool(browser.get("in_use")),
                fg=COLOR_SUCCESS if browser.get("in_use") else COLOR_MUTED)
            self.labels["browser_reason"].config(
                text=browser.get("reason", "—") or "—")
            self.labels["browser_class"].config(
                text=browser.get("active_class", "—") or "—")

            self.labels["sudoers"].config(
                text="✅ configurado" if sudoers_ok else "❌ NO configurado",
                fg=COLOR_SUCCESS if sudoers_ok else COLOR_DANGER)
            shutdown_enabled = bool(get_vault_config_value("auto_shutdown_enabled"))
            self.labels["shutdown_enabled"].config(text=fbool(shutdown_enabled))
            shutdown_min = get_vault_config_value("auto_shutdown_minutes") or 10
            self.labels["shutdown_minutes"].config(text=f"{shutdown_min} min")
            self.labels["browser_mode"].config(
                text=str(get_vault_config_value("ignore_browser_mode") or "any"))

            self.labels["cfg_max"].config(
                text=f"{get_vault_config_value('max_charge') or 80}%")
            self.labels["cfg_min"].config(
                text=f"{get_vault_config_value('min_charge') or 20}%")
            self.labels["cfg_sound"].config(
                text=fbool(get_vault_config_value("sound_enabled")))
            self.labels["cfg_fullscreen"].config(
                text=fbool(get_vault_config_value("fullscreen_alert")))
            self.labels["cfg_zoom"].config(
                text=f"{self.zoom_mgr.percent() if self.zoom_mgr else 100}%")

            self.labels["device"].config(text=info["device"] or "No detectado")
        except Exception as e:
            log.error(f"Error refrescando info: {e}")


# =========================================================
# GESTOR DE AUTO-APAGADO
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
        if self._dialog_active or time.time() < self._warning_until:
            return

        if is_multimedia_playing():
            log.info("AutoShutdown: multimedia activa, no se apaga")
            return

        mode = cfg.get("ignore_browser_mode", "any")
        if mode != "off":
            browser = get_browser_status()
            if browser.get("in_use"):
                log.info(f"AutoShutdown: navegador en uso -> "
                         f"{browser['reason']}, no se apaga")
                return

        idle = get_idle_seconds()
        if idle < 0:
            return
        threshold_s = float(cfg.get("auto_shutdown_minutes", 10)) * 60
        if idle < threshold_s:
            return

        warn_s = int(cfg.get("auto_shutdown_warning_seconds", 20))
        log.warning(f"AutoShutdown: idle={idle:.0f}s >= {threshold_s:.0f}s")
        self._dialog_active = True
        self.app.root.after(0, lambda: self._run_dialog(idle, warn_s))

    def _run_dialog(self, idle_s, warn_s):
        try:
            # v2.2.10: recordar si la ventana principal estaba oculta
            was_hidden = self.app._is_root_hidden()
            dlg = ShutdownCountdownDialog(
                self.app.root, warn_s, idle_s / 60.0, self.app.zoom_mgr)
            self.app.root.wait_window(dlg.win)
            if dlg.confirmed:
                log.warning("AutoShutdown: confirmado -> apagando")
                self._do_shutdown()
            elif dlg.cancelled:
                self._warning_until = time.time() + 60
                log.info("AutoShutdown cancelado por el usuario")
            # v2.2.10: si la ventana principal estaba oculta, mantenerla oculta
            if was_hidden:
                try:
                    self.app.root.withdraw()
                except Exception:
                    pass
        except Exception as e:
            log.error(f"Error en diálogo de apagado: {e}")
        finally:
            self._dialog_active = False

    def _do_shutdown(self):
        """Apaga el equipo. PRIMERO usa 'systemctl poweroff'."""
        methods = [
            # 1) systemctl poweroff (usa polkit, sin sudo)
            ["systemctl", "poweroff"],
            # 2) systemctl poweroff con sudo sin contraseña
            ["sudo", "-n", "systemctl", "poweroff"],
            # 3) systemctl con --force
            ["sudo", "-n", "systemctl", "poweroff", "--force", "--force"],
            # 4) poweroff directo (con sudoers configurado)
            ["sudo", "-n", "/usr/sbin/poweroff", "--force", "--force"],
            # 5) poweroff ruta alternativa
            ["sudo", "-n", "/sbin/poweroff", "--force", "--force"],
            # 6) pkexec (pide contraseña gráfica)
            ["pkexec", "poweroff", "--force", "--force"],
            # 7) shutdown fallback
            ["shutdown", "-h", "now"],
        ]
        for i, cmd in enumerate(methods, 1):
            try:
                log.warning(f"AutoShutdown: intento {i}: {' '.join(cmd)}")
                res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     timeout=10, text=True)
                if res.returncode == 0:
                    log.warning(f"AutoShutdown: apagado iniciado con {' '.join(cmd)}")
                    return
                err = res.stderr.strip() if res.stderr else ""
                log.warning(f"AutoShutdown: método {i} falló (rc={res.returncode}): {err}")
            except FileNotFoundError:
                log.warning(f"AutoShutdown: comando no encontrado: {cmd[0]}")
                continue
            except subprocess.TimeoutExpired:
                log.warning(f"AutoShutdown: timeout con {' '.join(cmd)}")
                continue
            except Exception as e:
                log.warning(f"AutoShutdown: error con {cmd[0]}: {e}")
                continue
        log.error("AutoShutdown: NINGÚN método de apagado funcionó.")


# =========================================================
# ICONO EN LA BANDEJA
# =========================================================
class TrayIcon:

    def __init__(self, app):
        self.app = app
        self.icon = None
        self._thread = None
        self._last_image_key = None
        if not TRAY_AVAILABLE:
            log.warning("pystray/Pillow no disponibles.")
            return
        try:
            self._create_icon()
        except Exception as e:
            log.error(f"Error creando icono: {e}")
            self.icon = None

    def _create_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar ventana", self._on_show, default=True),
            pystray.MenuItem("Ocultar ventana", self._on_hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Activar / desactivar monitoreo", self._on_toggle,
                             checked=lambda item: self.app.config["enabled"]),
            pystray.MenuItem("Ver informe de batería", self._on_info),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zoom +", self._on_zoom_in),
            pystray.MenuItem("Zoom -", self._on_zoom_out),
            pystray.MenuItem("Zoom 100%", self._on_zoom_reset),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Auto-apagado", self._on_toggle_shutdown,
                             checked=lambda item: self.app.config.get(
                                 "auto_shutdown_enabled", False)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._on_quit),
        )
        self.icon = pystray.Icon(name="battery_guardian",
                                 icon=make_tray_image(level=None),
                                 title=APP_NAME, menu=menu)

    def _on_show(self, i=None, it=None): self.app.root.after(0, self.app.show_window)
    def _on_hide(self, i=None, it=None): self.app.root.after(0, self.app.hide_window)
    def _on_toggle(self, i=None, it=None): self.app.root.after(0, self.app.toggle_enabled)
    def _on_toggle_shutdown(self, i=None, it=None): self.app.root.after(0, self.app.toggle_auto_shutdown)
    def _on_info(self, i=None, it=None): self.app.root.after(0, self.app.open_info_window)
    def _on_zoom_in(self, i=None, it=None): self.app.root.after(0, self.app.zoom_in)
    def _on_zoom_out(self, i=None, it=None): self.app.root.after(0, self.app.zoom_out)
    def _on_zoom_reset(self, i=None, it=None): self.app.root.after(0, self.app.zoom_reset)
    def _on_quit(self, i=None, it=None): self.app.root.after(0, self.app.ask_quit)

    def _run_safe(self):
        try:
            self.icon.run()
        except Exception as e:
            log.error(f"Tray icon thread crashed: {e}\n{traceback.format_exc()}")

    def start(self):
        if self.icon is None:
            return
        self._thread = threading.Thread(target=self._run_safe, daemon=True,
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
            log.error(f"Error actualizando icono: {e}")


# =========================================================
# APLICACIÓN PRINCIPAL
# =========================================================
class BatteryGuardianApp:

    def __init__(self, root: tk.Tk, start_hidden: bool = False):
        log.info("BatteryGuardianApp: __init__ inicio")
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = min(1400, int(sw * 0.95))
        target_w = max(1000, target_w)
        target_h = min(800, int(sh * 0.9))
        target_h = max(620, target_h)
        self.root.geometry(f"{target_w}x{target_h}")
        self.root.minsize(1000, 620)
        self.root.resizable(True, True)

        log.info("Cargando configuración...")
        self.config = load_config()
        self.alert_active = False
        self.alert_window = None
        self.info_window = None
        self._paused_until = 0
        self._force_quit = False
        self._start_hidden = start_hidden
        self._snooze_until = {"connect": 0, "disconnect": 0}
        self._toggle_buttons = []

        # v2.2.10: recordar estado de visibilidad de la ventana principal
        self._root_was_hidden_before_alert = False

        log.info("Aplicando estilos...")
        style = apply_modern_styles(root)
        self.zoom_mgr = ZoomManager(root, style, self.config.get("zoom", 1.0))

        log.info("Construyendo UI...")
        self._build_ui()

        log.info("Aplicando zoom...")
        self.zoom_mgr.apply()

        log.info("Iniciando bandeja...")
        self._setup_tray()

        log.info("Bindings de zoom...")
        self._bind_zoom_keys()

        log.info("Programando chequeo de batería...")
        self._schedule_check(1000)

        log.info("Iniciando AutoShutdownManager...")
        self.auto_shutdown = AutoShutdownManager(self)
        if self.config.get("auto_shutdown_enabled", False):
            self.auto_shutdown.start()

        self._check_sudoers_on_startup()

        if start_hidden:
            self.root.after(500, self.hide_window)

        log.info("BatteryGuardianApp: __init__ OK")

    # ----- v2.2.10: Nuevos helpers de visibilidad -----
    def _is_root_hidden(self) -> bool:
        """Devuelve True si la ventana principal está oculta."""
        try:
            return self.root.state() == "withdrawn"
        except Exception:
            return False

    def _save_visibility_before_alert(self):
        """Guarda el estado actual de visibilidad antes de mostrar una alerta."""
        try:
            self._root_was_hidden_before_alert = self._is_root_hidden()
            log.info(f"Visibilidad guardada antes de alerta: "
                     f"hidden={self._root_was_hidden_before_alert}")
        except Exception:
            self._root_was_hidden_before_alert = False

    def _restore_visibility_after_alert(self):
        """Restaura la visibilidad que había antes de la alerta."""
        try:
            if self._root_was_hidden_before_alert:
                # Estaba oculta → volver a ocultarla
                self.root.withdraw()
                log.info("Ventana principal restaurada a OCULTA tras alerta")
            # Si estaba visible, la dejamos visible
        except Exception as e:
            log.error(f"Error restaurando visibilidad: {e}")

    def _setup_tray(self):
        self.tray = TrayIcon(self)
        self.tray.start()

    def _bind_zoom_keys(self):
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())

    def _check_sudoers_on_startup(self):
        if self.config.get("auto_shutdown_enabled", False):
            if not check_sudoers_configured():
                log.warning("Auto-apagado activado pero sudoers NO configurado")

    def _build_ui(self):
        root = self.root
        root.configure(bg=COLOR_BG)

        # Header
        header = tk.Frame(root, bg=COLOR_BG, padx=18, pady=12)
        header.pack(fill="x")

        self.lbl_app = tk.Label(header, text=f"🔋  {APP_NAME}",
                                font=("Sans Serif", 18, "bold"),
                                bg=COLOR_BG, fg=COLOR_TEXT)
        self.lbl_app.pack(side="left")
        self.zoom_mgr.register_widget(self.lbl_app, "Sans Serif", 18, "bold")

        self.lbl_sub = tk.Label(
            header,
            text=f"v{APP_VERSION}  ·  Cuida la salud de tu batería",
            font=("Sans Serif", 9, "italic"),
            bg=COLOR_BG, fg=COLOR_MUTED)
        self.lbl_sub.pack(side="left", padx=(14, 0), pady=(8, 0))
        self.zoom_mgr.register_widget(self.lbl_sub, "Sans Serif", 9, "italic")

        zbtns = tk.Frame(header, bg=COLOR_BG)
        zbtns.pack(side="right")

        self.lbl_zoom = tk.Label(zbtns, text=f"{self.zoom_mgr.percent()}%",
                                 font=("Sans Serif", 11, "bold"),
                                 bg=COLOR_BG, fg=COLOR_TEXT)
        self.lbl_zoom.pack(side="right", padx=8)
        self.zoom_mgr.register_widget(self.lbl_zoom, "Sans Serif", 11, "bold")

        def _mk_zoom_btn(text, cmd):
            b = tk.Button(zbtns, text=text, font=("Sans Serif", 10, "bold"),
                          bg=COLOR_PANEL, fg=COLOR_TEXT,
                          activebackground=COLOR_BORDER,
                          activeforeground=COLOR_TEXT,
                          relief="flat", padx=10, pady=4, cursor="hand2",
                          command=cmd)
            b.pack(side="right", padx=2)
            self.zoom_mgr.register_widget(b, "Sans Serif", 10, "bold")
            return b

        _mk_zoom_btn("A+", self.zoom_in)
        _mk_zoom_btn("A−", self.zoom_out)
        _mk_zoom_btn("↺", self.zoom_reset)

        tk.Frame(root, bg=COLOR_BORDER, height=1).pack(fill="x")

        # 3 columnas
        cols = tk.Frame(root, bg=COLOR_BG, padx=18, pady=12)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, uniform="col")
        cols.columnconfigure(1, weight=1, uniform="col")
        cols.columnconfigure(2, weight=1, uniform="col")
        cols.rowconfigure(0, weight=1)

        # Columna 1
        col1 = tk.Frame(cols, bg=COLOR_BG)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        card_status = ttk.LabelFrame(col1, text="  🔋 Estado de la batería  ",
                                     style="Card.TLabelframe")
        card_status.pack(fill="x", pady=(0, 10))

        lvl_frame = ttk.Frame(card_status, style="Card.TFrame")
        lvl_frame.pack(fill="x", pady=(0, 8))
        self.lbl_level = ttk.Label(lvl_frame, text="—", style="BigVal.TLabel")
        self.lbl_level.pack(side="left")
        ttk.Label(lvl_frame, text="de carga", style="Card.TLabel"
                  ).pack(side="left", padx=(8, 0))

        self.lbl_state = ttk.Label(card_status, text="Estado: —",
                                   style="Info.TLabel")
        self.lbl_state.pack(anchor="w", pady=1)
        self.lbl_energy_full = ttk.Label(card_status, text="energy-full: —",
                                         style="Info.TLabel")
        self.lbl_energy_full.pack(anchor="w", pady=1)
        self.lbl_capacity = ttk.Label(card_status, text="capacity (salud): —",
                                      style="Info.TLabel")
        self.lbl_capacity.pack(anchor="w", pady=1)
        self.lbl_cycles = ttk.Label(card_status, text="charge-cycles: —",
                                    style="Info.TLabel")
        self.lbl_cycles.pack(anchor="w", pady=1)

        card_lim = ttk.LabelFrame(col1, text="  ⚙️ Límites de carga  ",
                                  style="Card.TLabelframe")
        card_lim.pack(fill="x", pady=(0, 10))

        f_max = ttk.Frame(card_lim, style="Card.TFrame")
        f_max.pack(fill="x", pady=4)
        ttk.Label(f_max, text="Máximo de carga (%):",
                  style="Card.TLabel").pack(side="left")
        self.max_var = tk.IntVar(value=self.config["max_charge"])
        sp_max = ttk.Spinbox(f_max, from_=50, to=100, textvariable=self.max_var,
                             width=6, justify="center")
        sp_max.pack(side="right")
        sp_max.bind("<FocusOut>", lambda e: self._save())
        sp_max.bind("<Return>", lambda e: self._save())

        f_min = ttk.Frame(card_lim, style="Card.TFrame")
        f_min.pack(fill="x", pady=4)
        ttk.Label(f_min, text="Mínimo de carga (%):",
                  style="Card.TLabel").pack(side="left")
        self.min_var = tk.IntVar(value=self.config["min_charge"])
        sp_min = ttk.Spinbox(f_min, from_=0, to=50, textvariable=self.min_var,
                             width=6, justify="center")
        sp_min.pack(side="right")
        sp_min.bind("<FocusOut>", lambda e: self._save())
        sp_min.bind("<Return>", lambda e: self._save())

        card_ctrl = ttk.LabelFrame(col1, text="  🎛️ Control de monitoreo  ",
                                   style="Card.TLabelframe")
        card_ctrl.pack(fill="x")

        self.enabled_var = tk.BooleanVar(value=self.config["enabled"])
        self.tb_enabled = ToggleButton(
            card_ctrl,
            text="Monitoreo de batería",
            variable=self.enabled_var,
            command=self._on_toggle_check,
            zoom_mgr=self.zoom_mgr,
            width=32,
        )
        self.tb_enabled.pack(fill="x", pady=3)
        self._toggle_buttons.append(self.tb_enabled)

        self.sound_var = tk.BooleanVar(value=self.config["sound_enabled"])
        self.tb_sound = ToggleButton(
            card_ctrl,
            text="Pitido de alerta",
            variable=self.sound_var,
            command=self._save,
            zoom_mgr=self.zoom_mgr,
            width=32,
        )
        self.tb_sound.pack(fill="x", pady=3)
        self._toggle_buttons.append(self.tb_sound)

        self.fullscreen_var = tk.BooleanVar(value=self.config["fullscreen_alert"])
        self.tb_fullscreen = ToggleButton(
            card_ctrl,
            text="Alerta a pantalla completa",
            variable=self.fullscreen_var,
            command=self._save,
            zoom_mgr=self.zoom_mgr,
            width=32,
        )
        self.tb_fullscreen.pack(fill="x", pady=3)
        self._toggle_buttons.append(self.tb_fullscreen)

        # Columna 2
        col2 = tk.Frame(cols, bg=COLOR_BG)
        col2.grid(row=0, column=1, sticky="nsew", padx=8)

        card_sd = ttk.LabelFrame(col2,
                                 text="  ⏻ Auto-apagado por inactividad  ",
                                 style="Card.TLabelframe")
        card_sd.pack(fill="both", expand=True)

        self.shutdown_var = tk.BooleanVar(
            value=self.config["auto_shutdown_enabled"])
        self.tb_shutdown = ToggleButton(
            card_sd,
            text="Auto-apagado por inactividad",
            variable=self.shutdown_var,
            command=self._on_toggle_shutdown_check,
            zoom_mgr=self.zoom_mgr,
            width=38,
        )
        self.tb_shutdown.pack(fill="x", pady=(0, 8))
        self._toggle_buttons.append(self.tb_shutdown)

        f1 = ttk.Frame(card_sd, style="Card.TFrame")
        f1.pack(fill="x", pady=4)
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

        f2 = ttk.Frame(card_sd, style="Card.TFrame")
        f2.pack(fill="x", pady=4)
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

        f_mode = ttk.Frame(card_sd, style="Card.TFrame")
        f_mode.pack(fill="x", pady=4)
        ttk.Label(f_mode, text="Modo detección navegador:",
                  style="Card.TLabel").pack(side="left")
        self.browser_mode_var = tk.StringVar(
            value=self.config.get("ignore_browser_mode", "any"))
        combo_mode = ttk.Combobox(
            f_mode, textvariable=self.browser_mode_var,
            values=["any", "video", "off"], state="readonly", width=10)
        combo_mode.pack(side="right")
        combo_mode.bind("<<ComboboxSelected>>", lambda e: self._save())

        ttk.Separator(card_sd, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(card_sd, text="📡 Estado en vivo",
                  style="Card.TLabel",
                  font=("Sans Serif", 10, "bold")).pack(anchor="w", pady=(0, 4))

        self.lbl_idle = ttk.Label(card_sd, text="Inactividad: —",
                                  style="Muted.TLabel")
        self.lbl_idle.pack(anchor="w", pady=1)
        self.lbl_media = ttk.Label(card_sd, text="Multimedia: —",
                                   style="Muted.TLabel")
        self.lbl_media.pack(anchor="w", pady=1)
        self.lbl_browser = ttk.Label(card_sd, text="Navegador: —",
                                     style="Muted.TLabel")
        self.lbl_browser.pack(anchor="w", pady=1)
        self.lbl_sudoers = ttk.Label(card_sd, text="Sudoers: —",
                                     style="Muted.TLabel")
        self.lbl_sudoers.pack(anchor="w", pady=1)

        ttk.Separator(card_sd, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(card_sd,
                  text=("💡 Modos navegador:\n"
                        "   any   = no apaga si hay navegador visible\n"
                        "   video = solo si detecta vídeo/fullscreen\n"
                        "   off   = no comprobar navegador\n\n"
                        "   VLC/mpv/audio siempre bloquean el apagado."),
                  style="Muted.TLabel",
                  justify="left").pack(anchor="w", pady=(0, 8))

        ttk.Button(card_sd, text="🧪  Probar aviso de apagado",
                   command=self._test_shutdown_warning).pack(anchor="w",
                                                             pady=(4, 0))

        # Columna 3
        col3 = tk.Frame(cols, bg=COLOR_BG)
        col3.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        card_actions = ttk.LabelFrame(col3, text="  ⚡ Acciones rápidas  ",
                                      style="Card.TLabelframe")
        card_actions.pack(fill="x", pady=(0, 10))

        ttk.Button(card_actions, text="💾  Guardar cambios",
                   style="Primary.TButton", command=self._save
                   ).pack(fill="x", pady=4)
        ttk.Button(card_actions, text="📊  Ver informe completo",
                   command=self.open_info_window
                   ).pack(fill="x", pady=4)
        ttk.Button(card_actions, text="🧪  Probar alerta de batería",
                   command=self._test_alert
                   ).pack(fill="x", pady=4)
        ttk.Button(card_actions, text="📥  Ocultar en bandeja",
                   command=self.hide_window
                   ).pack(fill="x", pady=4)

        card_help = ttk.LabelFrame(col3, text="  ⌨️ Atajos y zoom  ",
                                   style="Card.TLabelframe")
        card_help.pack(fill="x", pady=(0, 10))

        ttk.Label(card_help,
                  text="• Ctrl + rueda del ratón → Zoom\n"
                       "• Ctrl + / −           → Zoom\n"
                       "• Ctrl + 0              → Reset 100%",
                  style="Muted.TLabel", justify="left"
                  ).pack(anchor="w", pady=2)

        card_sys = ttk.LabelFrame(col3, text="  ℹ️ Acerca de  ",
                                  style="Card.TLabelframe")
        card_sys.pack(fill="both", expand=True)

        ttk.Label(card_sys,
                  text=f"{APP_NAME}\nVersión {APP_VERSION}\n\n"
                       "Cuida la salud de la batería de tu\n"
                       "portátil manteniéndola entre los\n"
                       "límites configurados.",
                  style="Muted.TLabel", justify="left"
                  ).pack(anchor="w", pady=2)

        # Footer
        footer = tk.Frame(root, bg=COLOR_BG, padx=18, pady=8)
        footer.pack(fill="x")

        self.lbl_footer = tk.Label(
            footer,
            text="💡 La ventana se adapta al tamaño de tu pantalla. "
                 "Pulsa X para ocultar en la bandeja.",
            font=("Sans Serif", 9, "italic"),
            bg=COLOR_BG, fg=COLOR_MUTED)
        self.lbl_footer.pack(side="left")
        self.zoom_mgr.register_widget(self.lbl_footer, "Sans Serif", 9, "italic")

        tk.Button(footer, text="Salir del programa",
                  font=("Sans Serif", 10),
                  bg=COLOR_PANEL, fg=COLOR_TEXT,
                  activebackground=COLOR_BORDER,
                  activeforeground=COLOR_TEXT,
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self.ask_quit).pack(side="right")

        self.zoom_mgr.add_listener(self._update_zoom_label)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_x)

    def _update_zoom_label(self):
        try:
            self.lbl_zoom.config(text=f"{self.zoom_mgr.percent()}%")
        except tk.TclError:
            pass

    def show_window(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def hide_window(self):
        try:
            self.root.withdraw()
        except Exception:
            pass

    def toggle_enabled(self):
        self.config["enabled"] = not self.config["enabled"]
        self.enabled_var.set(self.config["enabled"])
        for tb in self._toggle_buttons:
            tb.refresh()
        save_config(self.config)

    def toggle_auto_shutdown(self):
        self.config["auto_shutdown_enabled"] = \
            not self.config.get("auto_shutdown_enabled", False)
        self.shutdown_var.set(self.config["auto_shutdown_enabled"])
        for tb in self._toggle_buttons:
            tb.refresh()
        save_config(self.config)
        if self.config["auto_shutdown_enabled"]:
            self.auto_shutdown.start()
        else:
            self.auto_shutdown.stop()

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
            "Dejará de vigilar la batería hasta que lo vuelvas a abrir."
        ):
            self.quit_app()

    def quit_app(self):
        self._force_quit = True
        log.info("Cerrando Battery Guardian")
        try:
            self.auto_shutdown.stop()
        except Exception:
            pass
        notify_systemd_stop()
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

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

    def _on_toggle_check(self):
        self.config["enabled"] = self.enabled_var.get()
        save_config(self.config)

    def _on_toggle_shutdown_check(self):
        self.config["auto_shutdown_enabled"] = self.shutdown_var.get()
        save_config(self.config)
        if self.config["auto_shutdown_enabled"]:
            self.auto_shutdown.start()
        else:
            self.auto_shutdown.stop()

    def _test_shutdown_warning(self):
        # v2.2.10: guardar visibilidad antes de la alerta
        self._save_visibility_before_alert()
        dlg = ShutdownCountdownDialog(self.root, 15, 10.0, self.zoom_mgr)
        self.root.wait_window(dlg.win)
        # v2.2.10: restaurar visibilidad después de la alerta
        self._restore_visibility_after_alert()
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
        self.config["ignore_browser_mode"] = self.browser_mode_var.get()
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

    def _snooze_alert(self, alert_type):
        minutes = int(self.config.get("alert_snooze_minutes", 5))
        self._snooze_until[alert_type] = time.time() + minutes * 60
        log.info(f"Snooze {alert_type} durante {minutes} min")

    def _schedule_check(self, delay_ms):
        self.root.after(delay_ms, self._check_battery)

    def _check_battery(self):
        try:
            info = get_battery_full_info()
            state = info["state"]
            level = info["percentage"]
            charging = state in ("charging", "fully-charged", "pending-charge")

            if state is None or level is None:
                self.lbl_level.config(text="—", style="BigVal.TLabel")
                self.lbl_state.config(text="Estado: ⚠ No se detectó batería")
                self.lbl_energy_full.config(text="energy-full: —")
                self.lbl_capacity.config(text="capacity (salud): —")
                self.lbl_cycles.config(text="charge-cycles: —")
            else:
                if level <= 20:
                    style_lvl = "BigDanger.TLabel"
                elif level <= 40:
                    style_lvl = "BigWarn.TLabel"
                else:
                    style_lvl = "BigOk.TLabel"
                self.lbl_level.config(text=f"{level}%", style=style_lvl)

                estado_map = {
                    "charging": "🔌 Cargando",
                    "discharging": "🔋 Descargando",
                    "fully-charged": "✅ Completamente cargada",
                    "pending-charge": "⏳ Pendiente de carga",
                    "pending-discharge": "⏳ Pendiente de descarga",
                    "unknown": "❓ Desconocido",
                }
                self.lbl_state.config(text=f"Estado: {estado_map.get(state, state)}")
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
                self.lbl_idle.config(
                    text=f"Inactividad: {int(idle // 60)} min {int(idle % 60)} s")
            else:
                self.lbl_idle.config(text="Inactividad: no disponible")

            media = is_multimedia_playing()
            media_extra = ""
            if is_media_player_running():
                media_extra = " + reproductor (VLC/mpv)"
            if media:
                self.lbl_media.config(
                    text=f"Multimedia: 🎵 activa{media_extra}",
                    style="Ok.TLabel")
            else:
                self.lbl_media.config(
                    text="Multimedia: 🔇 silencio", style="Muted.TLabel")

            browser = get_browser_status()
            if not _cmd_exists("xdotool"):
                self.lbl_browser.config(
                    text="Navegador: ⚠ xdotool no instalado",
                    style="Warn.TLabel")
            elif browser.get("in_use"):
                reason = browser['reason'][:40]
                self.lbl_browser.config(
                    text=f"Navegador: 🌐 EN USO ({reason})",
                    style="Ok.TLabel")
            else:
                self.lbl_browser.config(
                    text="Navegador: ❌ no detectado",
                    style="Muted.TLabel")

            sudoers_ok = check_sudoers_configured()
            if sudoers_ok:
                self.lbl_sudoers.config(
                    text="Sudoers: ✅ configurado", style="Ok.TLabel")
            else:
                self.lbl_sudoers.config(
                    text="Sudoers: ❌ NO configurado", style="Warn.TLabel")

            if self.tray:
                self.tray.update(level=level, charging=charging,
                                 alert=self.alert_active)

            now = time.time()
            if (self.config["enabled"]
                    and not self.alert_active
                    and state is not None
                    and level is not None
                    and now >= self._paused_until):

                if state in ("charging", "fully-charged", "pending-charge") and \
                   level >= self.config["max_charge"]:
                    if now >= self._snooze_until.get("disconnect", 0):
                        self._show_alert("disconnect")
                elif state in ("discharging", "pending-discharge") and \
                     level <= self.config["min_charge"]:
                    if now >= self._snooze_until.get("connect", 0):
                        self._show_alert("connect")
        except Exception as e:
            log.error(f"Error en _check_battery: {e}\n{traceback.format_exc()}")

        self._schedule_check(self.config["check_interval"] * 1000)

    def _show_alert(self, alert_type):
        # v2.2.10: guardar visibilidad actual antes de mostrar la alerta
        self._save_visibility_before_alert()

        self.alert_active = True
        # v2.2.10: NO hacer deiconify() de la ventana principal.
        # La ventana de alerta (Toplevel) ya se muestra por sí sola con
        # sus propias propiedades (topmost, fullscreen si aplica).
        # Así el usuario no ve la ventana principal abrirse por detrás.
        try:
            log.info(f"Mostrando alerta {alert_type} sin abrir la ventana principal")
        except Exception:
            pass

        self.alert_window = AlertWindow(
            self.root, self.config, alert_type,
            self._alert_resolved, self.zoom_mgr,
            on_snooze=self._snooze_alert)

    def _alert_resolved(self):
        self.alert_active = False
        self.alert_window = None
        self._paused_until = time.time() + 5
        # v2.2.10: restaurar visibilidad que había antes de la alerta
        self._restore_visibility_after_alert()


# =========================================================
# MODO CLI
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
    print(f"  capacity (salud):   {info['capacity']}%")
    print(f"  charge-cycles:      {info['charge_cycles']}")
    print("-" * 60)
    if idle >= 0:
        print(f"  Inactividad:        {int(idle // 60)} min {int(idle % 60)} s")
    print(f"  Multimedia activa:  {'SÍ' if media else 'No'}")
    print(f"  Navegador en uso:   {'SÍ' if browser.get('in_use') else 'No'}")
    print(f"  Sudoers:            {'OK' if sudoers_ok else 'NO CONFIGURADO'}")
    print(f"  TRAY_AVAILABLE:     {TRAY_AVAILABLE}")
    print("=" * 60)


# =========================================================
# MAIN
# =========================================================
def main():
    try:
        setup_logging()
        install_excepthooks()
    except Exception as e:
        print(f"Error inicializando logging: {e}")

    if "--info" in sys.argv:
        print_info_cli()
        return

    debug = "--debug" in sys.argv
    start_hidden = "--hidden" in sys.argv

    log.info(f"Iniciando {APP_NAME} v{APP_VERSION} "
             f"(hidden={start_hidden}, debug={debug}, "
             f"systemd={is_running_under_systemd()}, "
             f"DISPLAY={os.environ.get('DISPLAY', 'NO')})")

    if not os.environ.get("DISPLAY"):
        msg = ("No hay DISPLAY. El programa no puede abrir una ventana.\n"
               "Asegúrate de ejecutarlo desde una sesión gráfica.")
        log.error(msg)
        print(f"ERROR: {msg}")
        if not debug:
            sys.exit(1)

    try:
        root = tk.Tk()
    except tk.TclError as e:
        msg = f"Error al crear ventana Tk: {e}"
        log.error(msg)
        print(f"ERROR: {msg}")
        sys.exit(1)
    except Exception as e:
        msg = f"Error inesperado al crear Tk: {e}"
        log.error(msg + "\n" + traceback.format_exc())
        print(f"ERROR: {msg}")
        sys.exit(1)

    try:
        app = BatteryGuardianApp(root, start_hidden=start_hidden)
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"Error creando BatteryGuardianApp:\n{tb}")
        print(f"ERROR CRÍTICO:\n{tb}")
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.error(f"Error en mainloop: {e}\n{traceback.format_exc()}")
    finally:
        try:
            app.auto_shutdown.stop()
        except Exception:
            pass
        try:
            app.tray.stop()
        except Exception:
            pass
    log.info(f"{APP_NAME} finalizado")


if __name__ == "__main__":
    main()

