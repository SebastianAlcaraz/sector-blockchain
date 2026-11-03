# Instala el Asistente de inversion en Windows 10/11.
# Uso (desde la carpeta del programa, en PowerShell):
#   powershell -ExecutionPolicy Bypass -File deploy\windows\instalar.ps1
# Guia paso a paso: deploy\windows\GUIA-WINDOWS.md

$ErrorActionPreference = "Stop"
$App = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ConfDir = Join-Path $env:APPDATA "AsistenteInversion"
$EnvFile = Join-Path $ConfDir "env"
$Here = Join-Path $App "deploy\windows"

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 1. Python
Paso "Buscando Python 3.10 o superior"
$Py = $null
foreach ($cand in @(@("py", "-3"), @("python"))) {
    try {
        $ver = & $cand[0] @($cand | Select-Object -Skip 1) -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -match '^(\d+)\.(\d+)$' -and ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 10))) {
            $Py = $cand
            Write-Host "    Encontrado Python $ver"
            break
        }
    } catch { }
}
if (-not $Py) {
    Write-Host "    No se encontro Python 3.10 o superior." -ForegroundColor Yellow
    Write-Host "    Instalalo con este comando y vuelve a ejecutar el instalador en una ventana NUEVA de PowerShell:"
    Write-Host "      winget install -e --id Python.Python.3.12"
    Write-Host "    (o descargalo de https://www.python.org/downloads/ marcando 'Add python.exe to PATH')"
    exit 1
}

# ---------------------------------------------------------------- 2. Entorno de Python
Paso "Creando el entorno de Python en $App\.venv (tarda unos minutos)"
& $Py[0] @($Py | Select-Object -Skip 1) -m venv (Join-Path $App ".venv")
if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno de Python." }
$VPy = Join-Path $App ".venv\Scripts\python.exe"
& $VPy -m pip install --upgrade pip --quiet
& $VPy -m pip install -r (Join-Path $App "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }

# ---------------------------------------------------------------- 3. Archivo de claves
Paso "Preparando el archivo de claves en $EnvFile"
New-Item -ItemType Directory -Force -Path $ConfDir | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding $false
if (-not (Test-Path $EnvFile)) {
    $plantilla = [IO.File]::ReadAllText((Join-Path $App "deploy\linux\env.example"))
    [IO.File]::WriteAllText($EnvFile, $plantilla, $utf8)
}
$contenido = [IO.File]::ReadAllText($EnvFile)
if ($contenido -notmatch '(?m)^APP_PASSWORD=\S+') {
    $chars = [char[]]'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    $pass = -join (1..14 | ForEach-Object { $chars | Get-Random })
    $contenido = [regex]::Replace($contenido, '(?m)^APP_PASSWORD=.*$', "APP_PASSWORD=$pass")
    [IO.File]::WriteAllText($EnvFile, $contenido, $utf8)
    Write-Host "    Contrasena de la web generada: $pass" -ForegroundColor Green
    Write-Host "    (guardala; tambien esta en $EnvFile)"
}
# Solo tu usuario puede leer el archivo de claves.
icacls $EnvFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null

# ---------------------------------------------------------------- 4. Claude Code (opcional)
Paso "Claude Code (para usar tu suscripcion de Claude en lugar de la API)"
$claudeExe = Join-Path $HOME ".local\bin\claude.exe"
if ((Get-Command claude -ErrorAction SilentlyContinue) -or (Test-Path $claudeExe)) {
    Write-Host "    Ya esta instalado."
} else {
    $resp = Read-Host "    Instalar Claude Code? Solo hace falta si vas a usar tu suscripcion [s/N]"
    if ($resp -match '^[sS]') {
        Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    }
}

# ---------------------------------------------------------------- 5. Tareas programadas
Paso "Programando las tareas de Windows"
$ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
function Accion($script, $extra) {
    $argumentos = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" $extra"
    return New-ScheduledTaskAction -Execute $ps -Argument $argumentos.Trim() -WorkingDirectory $App
}
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$ajustesWeb = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

# La web arranca al iniciar sesion.
Register-ScheduledTask -TaskName "Asistente inversion - Web" -Force `
    -Action (Accion (Join-Path $Here "iniciar-web.ps1") "") `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) -Settings $ajustesWeb | Out-Null

# El bot: dias laborables a las 09:30, 13:30, 17:30 y 21:30; fin de semana a las 12:30.
$laborables = "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
$disparadores = @()
foreach ($hora in "09:30", "13:30", "17:30", "21:30") {
    $disparadores += New-ScheduledTaskTrigger -Weekly -DaysOfWeek $laborables -At $hora
}
$disparadores += New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday, Sunday -At "12:30"
Register-ScheduledTask -TaskName "Asistente inversion - Bot" -Force `
    -Action (Accion (Join-Path $Here "ejecutar-bot.ps1") "") -Trigger $disparadores -Settings $ajustes | Out-Null

# Revision semanal de la estrategia: domingos a las 10:30.
Register-ScheduledTask -TaskName "Asistente inversion - Revision" -Force `
    -Action (Accion (Join-Path $Here "ejecutar-bot.ps1") "-Revisar") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "10:30") -Settings $ajustes | Out-Null
Write-Host "    Tareas creadas: Web (al iniciar sesion), Bot (cada 4 h) y Revision (domingos)."

# ---------------------------------------------------------------- 6. Acceso directo y arranque
$escritorio = [Environment]::GetFolderPath("Desktop")
[IO.File]::WriteAllText((Join-Path $escritorio "Asistente de inversion.url"), "[InternetShortcut]`r`nURL=http://localhost:8501`r`n", $utf8)

Paso "Arrancando la web"
Start-ScheduledTask -TaskName "Asistente inversion - Web"
Start-Sleep -Seconds 10
Start-Process "http://localhost:8501"

Write-Host ""
Write-Host "Listo." -ForegroundColor Green
Write-Host "  - Web:           http://localhost:8501  (acceso directo en el escritorio)"
Write-Host "  - Claves:        notepad `"$EnvFile`"   y despues reinicia la sesion de Windows (o ejecuta iniciar-web.ps1)"
Write-Host "  - Suscripcion:   claude setup-token    (pega el token en CLAUDE_CODE_OAUTH_TOKEN del archivo de claves)"
Write-Host "  - Registros:     $App\data\logs"
Write-Host "  - Desinstalar:   powershell -ExecutionPolicy Bypass -File deploy\windows\desinstalar.ps1"
Write-Host ""
Write-Host "El bot empieza en la cuenta DEMO de eToro (o en simulacion si faltan las claves). Nunca opera con dinero real."
