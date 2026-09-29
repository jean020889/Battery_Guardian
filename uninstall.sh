
#!/bin/bash
# =========================================================
#  Battery Guardian - Desinstalador
#  Elimina SOLO lo que instaló install.sh
# =========================================================
set -e

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"
NC="\033[0m"

print_ok()   { echo -e "   [${GREEN}✓${NC}] $1"; }
print_warn() { echo -e "   [${YELLOW}⚠${NC}] $1"; }
print_info() { echo -e "   [i] $1"; }

# ---------------------------------------------------------
#  Rutas (mismas que install.sh)
# ---------------------------------------------------------
APPS_DIR="/home/asus/Apps"
APP_NAME="Battery Guardian"
APP_SLUG="battery-guardian"
INSTALL_DIR="$APPS_DIR/Battery_Guardian"

if [ -d "$HOME/Escritorio" ]; then
    DESKTOP_DIR="$HOME/Escritorio"
elif [ -d "$HOME/Desktop" ]; then
    DESKTOP_DIR="$HOME/Desktop"
else
    DESKTOP_DIR="$HOME"
fi
DESKTOP_FILE="$DESKTOP_DIR/${APP_SLUG}.desktop"
MENU_FILE="$HOME/.local/share/applications/${APP_SLUG}.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/${APP_SLUG}.desktop"
BIN_LINK="$HOME/.local/bin/${APP_SLUG}"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SYSTEMD_FILE="$SYSTEMD_USER_DIR/${APP_SLUG}.service"
ICON_USER="$HOME/.local/share/icons/${APP_SLUG}.png"

SUDOERS_FILE="/etc/sudoers.d/battery-guardian"

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  🗑️  Desinstalando $APP_NAME${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo "  Se eliminará ÚNICAMENTE: $INSTALL_DIR"
echo ""

read -r -p "¿Estás seguro de que quieres desinstalar $APP_NAME? (s/N): " confirm
if [[ ! "$confirm" =~ ^[sS]$ ]]; then
    echo "Desinstalación cancelada."
    exit 0
fi

# =========================================================
#  1) Detener y eliminar servicio systemd
# =========================================================
echo -e "${BLUE}${BOLD}▶ [1/8] Deteniendo y eliminando servicio systemd...${NC}"
if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop    "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
fi
[ -f "$SYSTEMD_FILE" ] && rm -f "$SYSTEMD_FILE" && print_ok "Servicio eliminado: $SYSTEMD_FILE"
systemctl --user daemon-reload 2>/dev/null || true
systemctl --user reset-failed 2>/dev/null || true

# Matar cualquier proceso residual de esta app
pkill -9 -f "battery_guardian.py" 2>/dev/null || true
print_ok "Procesos residuales detenidos"
echo ""

# =========================================================
#  2) Eliminar accesos directos
# =========================================================
echo -e "${BLUE}${BOLD}▶ [2/8] Eliminando accesos directos...${NC}"
rm -f "$DESKTOP_FILE"
rm -f "$MENU_FILE"
rm -f "$AUTOSTART_FILE"
rm -f "$HOME/Escritorio/${APP_SLUG}.desktop"
rm -f "$HOME/Desktop/${APP_SLUG}.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
print_ok "Accesos directos eliminados"
echo ""

# =========================================================
#  3) Eliminar enlace CLI
# =========================================================
echo -e "${BLUE}${BOLD}▶ [3/8] Eliminando enlace CLI...${NC}"
if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    print_ok "$BIN_LINK"
fi
echo ""

# =========================================================
#  4) Eliminar icono de usuario
# =========================================================
echo -e "${BLUE}${BOLD}▶ [4/8] Eliminando icono...${NC}"
[ -f "$ICON_USER" ] && rm -f "$ICON_USER" && print_ok "$ICON_USER"
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/" 2>/dev/null || true
fi
echo ""

# =========================================================
#  5) Eliminar sudoers (con confirmación extra)
# =========================================================
echo -e "${BLUE}${BOLD}▶ [5/8] Eliminando regla de sudoers...${NC}"
if [ -f "$SUDOERS_FILE" ]; then
    read -r -p "  ¿Eliminar $SUDOERS_FILE? [S/n]: " RESP_SUDO
    if [[ "$RESP_SUDO" =~ ^[nN]$ ]]; then
        print_warn "Sudoers conservado. Elimínalo manualmente si quieres."
    else
        sudo rm -f "$SUDOERS_FILE"
        print_ok "Sudoers eliminado"
    fi
else
    print_info "No existía $SUDOERS_FILE"
fi
echo ""

# =========================================================
#  6) Eliminar SOLO la subcarpeta del programa
# =========================================================
echo -e "${BLUE}${BOLD}▶ [6/8] Eliminando carpeta de instalación...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    print_ok "$INSTALL_DIR"
else
    print_warn "No se encontró $INSTALL_DIR"
fi
# ⚠️  NO se borra $APPS_DIR porque puede contener otros programas.
echo ""

# =========================================================
#  7) Preguntar si eliminar dependencias recomendadas
# =========================================================
echo -e "${BLUE}${BOLD}▶ [7/8] Dependencias recomendadas (opcional)...${NC}"
print_info "xprintidle, xdotool, x11-utils NO se eliminan automáticamente."
print_info "Si quieres quitarlas: sudo apt remove xprintidle xdotool x11-utils"
echo ""

# =========================================================
#  8) Resumen
# =========================================================
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ Desinstalación completada${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "  Se eliminaron:"
echo "    - Servicio systemd --user (${APP_SLUG}.service)"
echo "    - Lanzadores .desktop (menú, escritorio, autostart)"
echo "    - Enlace CLI en ~/.local/bin/"
echo "    - Icono en ~/.local/share/icons/"
echo "    - $INSTALL_DIR (código, venv, install.sh, uninstall.sh, etc.)"
echo ""
echo "  Los demás programas en $APPS_DIR NO fueron afectados."
echo ""
