# Guía: instalar el Asistente de inversión en un mini PC

Para un mini PC con procesador Intel N100/N150, 16 GB de RAM y SSD. Se tarda alrededor de una hora.
Solo necesitas el mini PC el primer día con pantalla y teclado. Después lo manejas desde tu ordenador.

## Qué necesitas

- El mini PC, conectado al router **por cable**.
- Un pendrive USB de 8 GB o más. Se borrará.
- Tu ordenador habitual (Windows, Mac o Linux).
- Una pantalla y un teclado USB, solo para la instalación.

## 1. Preparar el pendrive con Ubuntu Server

1. Descarga **Ubuntu Server 24.04 LTS** desde <https://ubuntu.com/download/server>. Es gratuito.
2. Descarga **balenaEtcher** (<https://etcher.balena.io>) o **Rufus** (<https://rufus.ie>, solo Windows).
3. Abre el programa, elige el archivo `.iso` de Ubuntu y el pendrive, y pulsa *Flash* o *Empezar*.

## 2. Ajustes del mini PC (BIOS)

1. Conecta el pendrive, la pantalla y el teclado al mini PC, y enciéndelo.
2. Pulsa repetidamente **Supr** o **F7**, según el modelo, para entrar en la BIOS. Si no funciona, prueba **F2** o **Esc**.
3. Busca y ajusta:
   - **Arranque tras corte de luz**: *Restore on AC Power Loss*, *State After G3* o similar → **Power On**.
     Así, si se va la luz, el equipo se enciende solo al volver.
   - **Orden de arranque** (*Boot*): pon el **USB** primero.
4. Guarda y sal (normalmente **F10**).

> El mini PC suele venir con Windows. Al instalar Ubuntu en el paso siguiente **se borra Windows**.
> Si quieres conservarlo, haz antes una copia de lo que te interese.

## 3. Instalar Ubuntu Server

El instalador está en inglés y se maneja con el teclado (flechas, Enter y Tab). Elige estas opciones:

| Pantalla | Qué elegir |
|---|---|
| Language | Español (o English) |
| Keyboard | Spanish |
| Type of install | **Ubuntu Server** (no la versión *minimized*) |
| Network | Debe aparecer una dirección IP en la conexión por cable. Apúntala, por ejemplo `192.168.1.50` |
| Storage | **Use an entire disk** (el SSD interno) |
| Profile | Tu nombre, nombre del equipo (por ejemplo `inversion`), usuario y contraseña. **No los olvides** |
| SSH | Marca **Install OpenSSH server** (para manejarlo desde tu ordenador) |
| Featured snaps | No marques nada |

Al terminar, quita el pendrive y pulsa *Reboot*. Inicia sesión con tu usuario y contraseña.

## 4. Primeros ajustes

Desde aquí puedes seguir **desde tu ordenador**. Abre una terminal (en Windows, *PowerShell*) y escribe,
cambiando el usuario y la IP por los tuyos:

```bash
ssh tu-usuario@192.168.1.50
```

Ya dentro del mini PC:

```bash
sudo apt update && sudo apt upgrade -y          # actualiza el sistema (tarda unos minutos)
sudo timedatectl set-timezone Europe/Madrid     # tu zona horaria (el bot programa sus horarios con ella)
```

**IP fija (recomendado):** en la configuración de tu router, busca *DHCP*, *Reserva de IP* o *IP estática*
y reserva la IP actual para el mini PC. Así la dirección de la web no cambiará.

## 5. Instalar el Asistente

```bash
git clone -b claude/investment-app-sl48gt https://github.com/sebastianalcaraz/sector-blockchain.git
cd sector-blockchain/investment-app
bash deploy/linux/install.sh
```

> Si el repositorio es privado, GitHub te pedirá usuario y contraseña. La contraseña tiene que ser un
> *token* creado en GitHub → Settings → Developer settings → Personal access tokens.

El instalador:
- instala lo necesario y crea el entorno de Python;
- **genera la contraseña de la web**. Aparece en pantalla: guárdala;
- pregunta si quieres instalar **Claude Code**. Contesta **s** si vas a usar tu suscripción de Claude;
- deja la web y los temporizadores funcionando.

## 6. Conectar Claude

**Con tu suscripción (Pro/Max):**

```bash
~/.local/bin/claude setup-token
```

Aparece un enlace. Ábrelo en el navegador de tu ordenador, inicia sesión con tu cuenta de Claude y autoriza.
La terminal mostrará un **token** largo: cópialo.

**Con la API:** crea una clave en <https://platform.claude.com>.

Después, edita el archivo de claves:

```bash
nano ~/.config/asistente-inversion/env
```

Pega el token en `CLAUDE_CODE_OAUTH_TOKEN=` o la clave en `ANTHROPIC_API_KEY=`, sin espacios ni comillas.
Guarda con **Ctrl+O** y Enter, y sal con **Ctrl+X**. Luego reinicia la web:

```bash
sudo systemctl restart asistente-web
```

## 7. Abrir la web y configurar el bot

1. En el navegador de tu ordenador o móvil, conectado a la red de casa, abre `http://192.168.1.50:8501`
   (con tu IP).
2. Escribe la contraseña del paso 5.
3. Ve a **Bot de inversión → Configuración**:
   - **Conexión con Claude**: *Suscripción* o *API*. Con el plan Pro, el modelo *Sonnet* gasta menos.
   - Pulsa **Guardar** y después **Probar la conexión con Claude**.
4. El bot empieza en **simulación**: no toca dinero real.

## 8. Comprobar que funciona

```bash
systemctl list-timers 'asistente-*'              # próximos análisis y revisión semanal
sudo systemctl start asistente-bot.service       # lanzar un análisis ahora
journalctl -u asistente-bot.service -n 30        # ver qué ha hecho
```

## Acceso desde fuera de casa (opcional)

No abras puertos en el router. Instala **Tailscale**, una red privada gratuita para uso personal,
en el mini PC y en tu móvil u ordenador:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up            # muestra un enlace para iniciar sesión
```

Después abre la web con la dirección de Tailscale del mini PC, por ejemplo `http://inversion:8501`.

## Mantenimiento

| Qué | Cómo |
|---|---|
| Actualizar el Asistente | `cd ~/sector-blockchain && git pull && bash investment-app/deploy/linux/install.sh` |
| Actualizar el sistema | `sudo apt update && sudo apt upgrade -y` (una vez al mes) |
| Renovar el token de Claude | `~/.local/bin/claude setup-token` cada año y pegarlo de nuevo en el archivo de claves |
| Copia de seguridad | Copia la carpeta `~/sector-blockchain/investment-app/data/` (cartera, historial y estrategias) |
| Ver errores de la web | `journalctl -u asistente-web -n 50` |

## Si algo falla

- **No encuentro la IP:** en la pantalla del mini PC escribe `hostname -I`.
- **La web no abre:** `sudo systemctl status asistente-web` muestra el error.
- **"Claude no está disponible" en el registro del bot:** revisa el token o la clave en el archivo de claves y
  pulsa *Probar la conexión con Claude* en la web. Si dice que se alcanzó el límite, es el de tu suscripción:
  el bot usa las reglas hasta que se renueve.
