# Ejecuta un ciclo del bot, o la revision semanal con -Revisar (lo usan las tareas programadas).
param([switch]$Revisar)
$App = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONUTF8 = "1"
Set-Location $App
$logs = Join-Path $App "data\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$log = Join-Path $logs "bot.log"
$que = if ($Revisar) { "revision de la estrategia" } else { "ciclo del bot" }
Add-Content -Path $log -Value ("`r`n==== {0} - {1} ====" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $que) -Encoding UTF8
$argumentos = @("-m", "invest.trading")
if ($Revisar) { $argumentos += "--revisar" }
& (Join-Path $App ".venv\Scripts\python.exe") @argumentos *>> $log
exit $LASTEXITCODE
