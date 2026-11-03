# Guía: instalar el Asistente de inversión en Windows

Para un PC con Windows 10 u 11. Se tarda unos 20 minutos. No hace falta ser administrador, salvo para instalar Python.

## 1. Instalar Python

Abre **PowerShell** (menú Inicio, escribe "PowerShell") y ejecuta:

```powershell
winget install -e --id Python.Python.3.12
```

Cierra PowerShell y abre una ventana nueva, para que reconozca Python.

> Sin `winget`: descárgalo de <https://www.python.org/downloads/> y marca **"Add python.exe to PATH"** al instalar.

## 2. Descargar el programa

**Opción A, con Git:**
```powershell
cd $HOME
git clone -b claude/investment-app-sl48gt https://github.com/sebastianalcaraz/sector-blockchain.git
cd sector-blockchain\investment-app
```

**Opción B, sin Git:** en GitHub, abre el repositorio, elige la rama `claude/investment-app-sl48gt` y pulsa
**Code → Download ZIP**. Descomprímelo, por ejemplo en `C:\Users\TuUsuario\sector-blockchain`, y en PowerShell entra en la carpeta
`investment-app`:
```powershell
cd $HOME\sector-blockchain\investment-app
```

## 3. Ejecutar el instalador

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\instalar.ps1
```

El instalador:
- crea el entorno de Python e instala lo necesario (tarda unos minutos);
- crea el archivo de claves en `%APPDATA%\AsistenteInversion\env` y **genera la contraseña de la web**, que aparece en pantalla: guárdala;
- pregunta si quieres instalar **Claude Code**. Contesta **s** para usar tu suscripción;
- crea tres **tareas programadas** de Windows:
  - **Web**: arranca al iniciar sesión;
  - **Bot**: los días laborables a las 9:30, 13:30, 17:30 y 21:30, y los fines de semana a las 12:30;
  - **Revisión**: los domingos a las 10:30;
- pone un acceso directo **"Asistente de inversión"** en el escritorio y abre la web.

Si el ordenador está apagado a la hora de una tarea, se ejecuta al encenderlo.

## 4. Poner las claves

**Token de tu suscripción de Claude:**
```powershell
claude setup-token
```
Inicia sesión en el navegador y copia el token que aparece. Si dice que no encuentra `claude`, abre una ventana nueva de PowerShell.

**Claves de eToro:** créalas en el portal de desarrolladores de eToro. Hacen falta la clave de la aplicación y la clave de usuario.

Abre el archivo de claves:
```powershell
notepad "$env:APPDATA\AsistenteInversion\env"
```
Rellena `CLAUDE_CODE_OAUTH_TOKEN=`, `ETORO_API_KEY=` y `ETORO_USER_KEY=` (sin espacios ni comillas) y guarda.

Para que la web lea las claves nuevas, **cierra sesión en Windows y vuelve a entrar**, o ejecuta:
```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\desinstalar.ps1
powershell -ExecutionPolicy Bypass -File deploy\windows\instalar.ps1
```

## 5. Probar

1. Abre el acceso directo del escritorio (o <http://localhost:8501>) y escribe la contraseña.
2. Ve a **Bot de inversión → Configuración**:
   - en **Conexión con Claude**, elige **Suscripción** y pulsa **Guardar**;
   - pulsa **Probar la conexión con Claude**.
3. Pulsa **Analizar el mercado ahora** y mira la pestaña **Registro**.

El bot opera en la **cuenta demo de eToro**, o en la simulación local si faltan las claves. Nunca con dinero real.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Datos del bot (cartera, historial, estrategias) | `investment-app\data\bot\` |
| Registros | `investment-app\data\logs\web.log` y `bot.log` |
| Claves | `%APPDATA%\AsistenteInversion\env` |
| Tareas | Programador de tareas de Windows, nombres "Asistente inversion - …" |

## Pasarlo después al mini PC

1. Instálalo en el mini PC con `deploy/linux/GUIA-MINIPC.md`.
2. Copia la carpeta `investment-app\data\` de este PC a `~/sector-blockchain/investment-app/data/` en el mini PC, para conservar el historial y lo aprendido.
3. Copia también el contenido del archivo de claves.
4. En este PC, ejecuta `deploy\windows\desinstalar.ps1` para que no haya dos bots funcionando a la vez.

## Si algo falla

- **"No se encontró Python"**: abre una ventana nueva de PowerShell después de instalarlo.
- **La web no abre**: mira `data\logs\web.log`.
- **El bot no hace nada**: mira `data\logs\bot.log` y la pestaña **Registro** de la web.
- **Desinstalar**: `powershell -ExecutionPolicy Bypass -File deploy\windows\desinstalar.ps1`. No borra tus datos ni las claves.
