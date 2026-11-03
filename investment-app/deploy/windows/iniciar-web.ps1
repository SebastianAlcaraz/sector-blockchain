# Arranca la web del Asistente de inversion (la usa la tarea "Asistente inversion - Web").
$App = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONUTF8 = "1"
Set-Location $App
$logs = Join-Path $App "data\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
# Si la web ya esta funcionando, no se arranca otra.
$enUso = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($enUso) { exit 0 }
& (Join-Path $App ".venv\Scripts\python.exe") -m streamlit run app.py `
    --server.address 127.0.0.1 --server.port 8501 --server.headless true *>> (Join-Path $logs "web.log")
