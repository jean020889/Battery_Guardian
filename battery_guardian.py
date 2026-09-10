#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Battery Guardian
================
Cuida la salud de la batería de tu portátil Linux.

- Alerta visual a pantalla completa + pitido cuando:
  * La batería llega al máximo configurado (con cargador conectado)
  * La batería baja al mínimo configurado (sin cargador)
- La alerta NO se puede cerrar hasta realizar la acción.
- Interfaz gráfica para activar/desactivar y regular los porcentajes.
- Información detallada: energy-full, capacity, charge-cycles.
- Icono en la bandeja del sistema (donde WiFi, Bluetooth…).
- Se ejecuta siempre en segundo plano. Al pulsar la X se oculta
  en la bandeja (no se cierra). Sólo se puede salir desde el menú
  del icono → "Salir".

Autor: Proyecto Battery Guardian
Licencia: MIT
"""

import os
import re
import sys
import json
import time
import logging
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# =========================================================
#  DEPENDENCIAS OPCIONALES (bandeja del sistema)
# =========================================================
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


# =========================================================
#  CONSTANTES Y RUTAS
# =========================================================
APP_NAME = "Battery Guardian"
APP_VERSION = "1.3.0"
SYSTEMD_SERVICE = "battery-guardian.service"

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
}

SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/ubuntu/stereo/bell.ogg",
    "/usr/share/sounds/alsa/Front_Center.wav",
]


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
#  SYSTEMD (para que no se reinicie al salir desde el menú)
# =========================================================
def is_running_under_systemd() -> bool:
    """Detecta si el proceso fue lanzado por systemd."""
    return bool(os.environ.get("INVOCATION_ID"))


def notify_systemd_stop():
    """Avisa a systemd de que no reinicie el servicio."""
    if not is_running_under_systemd():
        return
    try:
        subprocess.Popen(
            ["systemctl", "--user", "stop", SYSTEMD_SERVICE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


# =========================================================
#  BATERÍA
# =========================================================
def find_battery_device():
    try:
        out = subprocess.check_output(
            ["upower", "-e"], text=True, stderr=subprocess.DEVNULL
        )
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
    num = m.group(0).replace(",", ".")
    try:
        return float(num)
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
            ["upower", "-i", device], text=True, stderr=subprocess.DEVNULL
        )
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
            info["energy_full"] / info["energy_full_design"] * 100, 2
        )

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
                    subprocess.Popen(
                        ["aplay", "-q", path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["paplay", path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                return
            except Exception as e:
                log.warning(f"No se pudo reproducir {path}: {e}")


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
                fill="#FFF176", outline="#FFF176",
            )

    return img


# =========================================================
#  VENTANA DE ALERTA BLOQUEANTE
# =========================================================
class AlertWindow:

    def __init__(self, parent, config, alert_type, on_resolved):
        self.config = config
        self.alert_type = alert_type
        self.on_resolved = on_resolved
        self._running = True

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
            w, h = 900, 600
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

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

        tk.Label(frame, text=f"⚠  {title}  ⚠",
                 font=("Arial", 40, "bold"),
                 fg="white", bg=bg).pack(pady=30)
        tk.Label(frame, text=msg, font=("Arial", 24),
                 fg="white", bg=bg, justify="center").pack(pady=20)

        self.status_label = tk.Label(frame, text="", font=("Arial", 16),
                                     fg="#FFFFCC", bg=bg, justify="center")
        self.status_label.pack(pady=20)

        tk.Label(frame,
                 text="Esta ventana se cerrará automáticamente al realizar la acción.",
                 font=("Arial", 14, "italic"),
                 fg="#EEEEEE", bg=bg).pack(pady=10)

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

    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - Información de la batería")
        self.win.geometry("620x560")
        self.win.resizable(False, False)

        main = ttk.Frame(self.win, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="📊  Información detallada de la batería",
                  font=("Arial", 14, "bold")).pack(pady=(0, 12))

        self.text = tk.Text(main, wrap="word", font=("Monospace", 10),
                            height=22, width=72, bg="#1e1e1e",
                            fg="#e0e0e0", insertbackground="white",
                            relief="flat")
        self.text.pack(fill="both", expand=True)

        btns = ttk.Frame(main)
        btns.pack(pady=10)
        ttk.Button(btns, text="🔄  Actualizar",
                   command=self.refresh).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="❌  Cerrar",
                   command=self.win.destroy).grid(row=0, column=1, padx=4)

        self.refresh()

    def refresh(self):
        info = get_battery_full_info()
        text = self._format_info(info)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.config(state="disabled")

    @staticmethod
    def _format_info(info: dict) -> str:
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
            pystray.MenuItem("Salir", self._on_quit),
        )

        self.icon = pystray.Icon(
            name="battery_guardian",
            icon=make_tray_image(level=None),
            title=f"{APP_NAME}",
            menu=menu,
        )

    def _on_show(self, icon=None, item=None):
        self.app.root.after(0, self.app.show_window)

    def _on_hide(self, icon=None, item=None):
        self.app.root.after(0, self.app.hide_window)

    def _on_toggle(self, icon=None, item=None):
        self.app.root.after(0, self.app.toggle_enabled)

    def _on_info(self, icon=None, item=None):
        self.app.root.after(0, self.app.open_info_window)

    def _on_quit(self, icon=None, item=None):
        self.app.root.after(0, self.app.ask_quit)

    def start(self):
        if self.icon is None:
            return
        self._thread = threading.Thread(
            target=self.icon.run, daemon=True, name="tray-icon")
        self._thread.start()
        log.info("Icono de bandeja iniciado")

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            log.info("Icono de bandeja detenido")

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
            level_txt = f"{level}%" if level is not None else "—"
            self.icon.title = f"{APP_NAME} — {level_txt} ({state_txt})"
        except Exception as e:
            log.error(f"Error actualizando icono de bandeja: {e}")


# =========================================================
#  APLICACIÓN PRINCIPAL
# =========================================================
class BatteryGuardianApp:

    def __init__(self, root, start_hidden=False):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("520x740")
        self.root.resizable(False, False)
        self.config = load_config()
        self.alert_active = False
        self.alert_window = None
        self.info_window = None
        self._paused_until = 0
        self._force_quit = False
        self._start_hidden = start_hidden

        self._build_ui()
        self._setup_tray()
        self._schedule_check(1000)

        # Arrancar oculto si se pidió
        if start_hidden:
            self.root.after(500, self.hide_window)

    def _setup_tray(self):
        self.tray = TrayIcon(self)
        self.tray.start()

    # ----- UI -----
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text=f"🔋  {APP_NAME}",
                  font=("Arial", 20, "bold")).pack(pady=(0, 2))
        ttk.Label(main,
                  text=f"Versión {APP_VERSION}   |   Cuida la salud de tu batería",
                  font=("Arial", 9, "italic")).pack(pady=(0, 10))

        self.enabled_var = tk.BooleanVar(value=self.config["enabled"])
        ttk.Checkbutton(main, text="Activar monitoreo de batería",
                        variable=self.enabled_var,
                        command=self._on_toggle_check).pack(anchor="w", pady=4)

        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=8)

        # --- Máximo ---
        frame_max = ttk.Frame(main)
        frame_max.pack(fill="x", pady=4)
        ttk.Label(frame_max, text="Máximo de carga (%):",
                  font=("Arial", 11)).pack(side="left")
        self.max_var = tk.IntVar(value=self.config["max_charge"])
        spin_max = ttk.Spinbox(frame_max, from_=50, to=100,
                               textvariable=self.max_var, width=6, justify="center")
        spin_max.pack(side="right")
        spin_max.bind("<FocusOut>", lambda e: self._save())
        spin_max.bind("<Return>", lambda e: self._save())

        # --- Mínimo ---
        frame_min = ttk.Frame(main)
        frame_min.pack(fill="x", pady=4)
        ttk.Label(frame_min, text="Mínimo de carga (%):",
                  font=("Arial", 11)).pack(side="left")
        self.min_var = tk.IntVar(value=self.config["min_charge"])
        spin_min = ttk.Spinbox(frame_min, from_=0, to=50,
                               textvariable=self.min_var, width=6, justify="center")
        spin_min.pack(side="right")
        spin_min.bind("<FocusOut>", lambda e: self._save())
        spin_min.bind("<Return>", lambda e: self._save())

        # --- Opciones ---
        self.sound_var = tk.BooleanVar(value=self.config["sound_enabled"])
        ttk.Checkbutton(main, text="Activar pitido de alerta",
                        variable=self.sound_var,
                        command=self._save).pack(anchor="w", pady=(8, 2))

        self.fullscreen_var = tk.BooleanVar(value=self.config["fullscreen_alert"])
        ttk.Checkbutton(main, text="Alerta a pantalla completa",
                        variable=self.fullscreen_var,
                        command=self._save).pack(anchor="w", pady=2)

        # --- Panel de información ---
        info_frame = ttk.LabelFrame(main, text=" Información de la batería ",
                                    padding=10)
        info_frame.pack(fill="x", pady=8)

        self.lbl_state = ttk.Label(info_frame, text="Estado: —", font=("Arial", 10))
        self.lbl_state.pack(anchor="w")
        self.lbl_level = ttk.Label(info_frame, text="Nivel: —", font=("Arial", 10))
        self.lbl_level.pack(anchor="w")
        self.lbl_energy_full = ttk.Label(info_frame, text="energy-full: —",
                                         font=("Arial", 10))
        self.lbl_energy_full.pack(anchor="w")
        self.lbl_capacity = ttk.Label(info_frame, text="capacity (salud): —",
                                      font=("Arial", 10))
        self.lbl_capacity.pack(anchor="w")
        self.lbl_cycles = ttk.Label(info_frame, text="charge-cycles: —",
                                    font=("Arial", 10))
        self.lbl_cycles.pack(anchor="w")

        # --- Botones ---
        btns = ttk.Frame(main)
        btns.pack(pady=12)

        ttk.Button(btns, text="💾  Guardar", command=self._save,
                   width=14).grid(row=0, column=0, padx=4, pady=3)
        ttk.Button(btns, text="📊  Ver informe completo",
                   command=self.open_info_window,
                   width=22).grid(row=0, column=1, padx=4, pady=3)
        ttk.Button(btns, text="🧪  Probar alerta", command=self._test_alert,
                   width=14).grid(row=1, column=0, padx=4, pady=3)
        ttk.Button(btns, text="Ocultar en bandeja",
                   command=self.hide_window,
                   width=18).grid(row=1, column=1, padx=4, pady=3)

        # La X SIEMPRE oculta en bandeja (nunca cierra)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_x)

    # ----- Acciones públicas -----
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
        estado = "activado" if self.config["enabled"] else "desactivado"
        log.info(f"Monitoreo {estado} (desde bandeja)")

    def open_info_window(self):
        if self.info_window is not None and self.info_window.win.winfo_exists():
            self.info_window.refresh()
            self.info_window.win.lift()
            return
        self.info_window = InfoWindow(self.root)

    def ask_quit(self):
        """Pregunta antes de salir de verdad (sólo desde la bandeja)."""
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
        log.info("Cerrando Battery Guardian (petición del usuario)")
        # Avisar a systemd para que no lo reinicie
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

    # ----- Callbacks -----
    def _on_toggle_check(self):
        self.config["enabled"] = self.enabled_var.get()
        save_config(self.config)
        log.info(f"Monitoreo "
                 f"{'activado' if self.config['enabled'] else 'desactivado'}")

    def _save(self):
        try:
            maxv = int(self.max_var.get())
            minv = int(self.min_var.get())
        except Exception:
            messagebox.showerror("Error", "Introduce números válidos.")
            return
        if minv >= maxv:
            messagebox.showerror("Error",
                                 "El mínimo debe ser menor que el máximo.")
            return

        self.config["max_charge"] = maxv
        self.config["min_charge"] = minv
        self.config["enabled"] = self.enabled_var.get()
        self.config["sound_enabled"] = self.sound_var.get()
        self.config["fullscreen_alert"] = self.fullscreen_var.get()
        save_config(self.config)
        log.info(f"Config guardada: máx {maxv}% mín {minv}%")

    def _test_alert(self):
        if self.alert_active:
            return
        self._save()
        self._show_alert("disconnect")

    def _on_close_x(self):
        """La X SIEMPRE oculta en bandeja. Nunca cierra."""
        self.hide_window()
        if not getattr(self, "_tray_hint_shown", False):
            self._tray_hint_shown = True
            try:
                subprocess.Popen(
                    ["notify-send", "-i", "battery", APP_NAME,
                     "El programa sigue activo en la bandeja del sistema."],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    # ----- Bucle de chequeo -----
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
            self.root, self.config, alert_type, self._alert_resolved)

    def _alert_resolved(self):
        self.alert_active = False
        self.alert_window = None
        self._paused_until = time.time() + 5


# =========================================================
#  MODO CLI
# =========================================================
def print_info_cli():
    info = get_battery_full_info()
    print("=" * 55)
    print(f"  {APP_NAME} v{APP_VERSION} - Informe de batería")
    print("=" * 55)
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
    print("=" * 55)


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
    if TRAY_AVAILABLE:
        log.info("Soporte de bandeja del sistema: SÍ")
    else:
        log.warning("Soporte de bandeja del sistema: NO")

    try:
        root = tk.Tk()
    except tk.TclError as e:
        print(f"Error: no se pudo iniciar la interfaz gráfica ({e})")
        print("Asegúrate de tener un entorno de escritorio activo.")
        sys.exit(1)

    app = BatteryGuardianApp(root, start_hidden=start_hidden)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if app.tray:
                app.tray.stop()
        except Exception:
            pass
    log.info(f"{APP_NAME} finalizado")


if __name__ == "__main__":
    main()
