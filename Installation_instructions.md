# 📖 Guía de instalación y desinstalación

Guía paso a paso para instalar **Battery Guardian v1.3.0** en Linux Mint
(o cualquier distro basada en Ubuntu/Debian) y desinstalarlo por completo.

---

## 📋 Índice

1. [Requisitos previos](#-requisitos-previos)
2. [Instalación](#-instalación)
3. [Cómo abrir el programa](#-cómo-abrir-el-programa)
4. [Cómo se ejecuta en segundo plano](#-cómo-se-ejecuta-en-segundo-plano)
5. [Cómo detenerlo temporalmente](#-cómo-detenerlo-temporalmente)
6. [Desinstalación](#-desinstalación)
7. [Solución de problemas](#-solución-de-problemas)

---

## 🔧 Requisitos previos

### 1. Comprobar Python

```bash
python3 --version
```
Debe devolver Python 3.8 o superior.

2. Instalar dependencias del sistema
```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk upower
```

💡 Estas son las únicas dependencias del sistema. Todo lo demás
(pystray, Pillow) se instala dentro del entorno virtual del
programa, sin tocar el sistema.

3. Comprobar el icono
El instalador necesita el archivo battery_guardian_icon.png en la
raíz del proyecto:

text
Battery_Guardian/
├── battery_guardian_icon.png   ← debe estar aquí
├── battery_guardian.py
├── install.sh
├── requirements.txt
└── ...
🚀 Instalación
Paso 1 — Abrir la terminal

```bash
cd "/home/asus/Documentos/INFORMATICA/PROGRAMACIÓN/PROYECTOS/Battery_Guardian"
```
Paso 2 — Ejecutar el instalador

```bash
chmod +x install.sh uninstall.sh
./install.sh
```
Paso 3 — Esperar a que termine
El instalador hace 11 pasos automáticamente:

#	Acción
1	Comprobar dependencias del sistema
2	Comprobar el icono
3	Detener instancias antiguas
4	Copiar archivos a ~/Apps/Battery_Guardian/
5	Crear el entorno virtual
6	Instalar pystray y Pillow en el venv
7	Crear el lanzador run.sh
8	Crear el enlace CLI ~/.local/bin/battery-guardian
9	Crear el icono del escritorio y la entrada del menú
10	Instalar el servicio systemd --user (arranque + auto-reinicio)
11	Verificar que todo funciona
Al final verás:

text
═══════════════════════════════════════════════════════
  ✅ Instalación completada
═══════════════════════════════════════════════════════

  📌 El programa ya está corriendo en segundo plano.
     Búscalo en la bandeja del sistema (donde WiFi/Bluetooth).
🖱️ Cómo abrir el programa
Tienes 4 formas de abrir la ventana de configuración:

Método	Cómo
🖥️ Bandeja	Clic en el icono de la bandeja del sistema
🖱️ Escritorio	Doble clic en el icono Battery Guardian
📋 Menú	Menú de aplicaciones → Battery Guardian
💻 Terminal	battery-guardian
⚠ La primera vez que hagas doble clic en el icono del escritorio,
Linux puede mostrar un aviso: "Confiar y ejecutar".
Púlsalo una vez y ya no volverá a aparecer.

🔄 Cómo se ejecuta en segundo plano
El programa se instala como un servicio de usuario de systemd:

✅ Arranca automáticamente al iniciar sesión.

✅ Se ejecuta oculto en la bandeja del sistema.

✅ Si se cae o lo matan, se reinicia solo a los 5 segundos.

✅ No aparece ninguna ventana hasta que tú la abras.

Comprobar que está corriendo
bash
systemctl --user status battery-guardian.service
Deberías ver Active: active (running).

Ver los logs
bash
# Logs del servicio
journalctl --user -u battery-guardian.service -f

# Logs internos del programa
tail -f ~/.config/battery_guardian/battery_guardian.log
🛑 Cómo detenerlo temporalmente
Opción 1 — Desde el icono de la bandeja
Clic derecho → Salir.

Esto lo detiene sin desinstalarlo. Se reiniciará la próxima vez que
inicies sesión.

Opción 2 — Desde la terminal
bash
# Detener ahora (vuelve al iniciar sesión)
systemctl --user stop battery-guardian.service

# Detener y que NO arranque al iniciar sesión
systemctl --user disable --now battery-guardian.service

# Volver a activarlo
systemctl --user enable --now battery-guardian.service
🗑️ Desinstalación
Paso 1 — Ir al proyecto
bash
cd "/home/asus/Documentos/INFORMATICA/PROGRAMACIÓN/PROYECTOS/Battery_Guardian"
Paso 2 — Ejecutar el desinstalador
bash
./uninstall.sh
Paso 3 — Responder a la pregunta
Al final te preguntará:

text
⚙  Configuración encontrada en: /home/asus/.config/battery_guardian

   ¿Eliminar también la configuración y los logs? (s/N):
Escribe s y Enter para borrar todo.

Pulsa solo Enter para conservar la configuración
(útil si vas a reinstalar más tarde).

Qué elimina el desinstalador
Elemento	Ruta
Servicio systemd	~/.config/systemd/user/battery-guardian.service
Procesos activos	(se matan)
Icono del escritorio	~/Desktop/battery-guardian.desktop
Entrada del menú	~/.local/share/applications/battery-guardian.desktop
Autostart (si existía)	~/.config/autostart/battery-guardian.desktop
Enlace CLI	~/.local/bin/battery-guardian
Carpeta del programa (venv + código)	~/Apps/Battery_Guardian/
Configuración	~/.config/battery_guardian/ (opcional)
🐛 Solución de problemas
❌ "Faltan dependencias del sistema"
bash
sudo apt update
sudo apt install python3 python3-venv python3-tk upower
Y vuelve a ejecutar ./install.sh.

❌ El servicio systemd no arranca
bash
# Ver por qué falla
systemctl --user status battery-guardian.service
journalctl --user -u battery-guardian.service --no-pager | tail -30
❌ El icono del escritorio no se ejecuta al hacer doble clic
bash
gio set ~/Desktop/battery-guardian.desktop metadata::trusted true
chmod +x ~/Desktop/battery-guardian.desktop
O clic derecho → Permitir ejecución / Confiar y ejecutar.

❌ "battery-guardian: command not found"
bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
❌ El icono no aparece en la bandeja del sistema
Asegúrate de tener el applet activo:

Cinnamon: Configuración → Applets → activar "Bandeja del sistema".

MATE: Clic derecho en el panel → Añadir → "Bandeja del sistema".

XFCE: Clic derecho en el panel → Añadir → "Área de notificación".

❌ Quiero reinstalar desde cero
bash
cd "/home/asus/Documentos/INFORMATICA/PROGRAMACIÓN/PROYECTOS/Battery_Guardian"
./uninstall.sh          # responde "s" para borrar también la config
./install.sh
📝 Notas finales
El programa no se cierra con la X: se oculta en la bandeja.

Para salir de verdad: clic derecho en el icono → Salir.

Configuración: ~/.config/battery_guardian/config.json

Logs: ~/.config/battery_guardian/battery_guardian.log

El venv no toca el Python del sistema.
EOF
