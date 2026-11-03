# Quita las tareas programadas y detiene la web. NO borra tus datos ni el archivo de claves.
$tareas = "Asistente inversion - Web", "Asistente inversion - Bot", "Asistente inversion - Revision"
foreach ($t in $tareas) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "Quitada la tarea: $t"
    }
}
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "streamlit" -and $_.CommandLine -match "app.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "Web detenida." }
$acceso = Join-Path ([Environment]::GetFolderPath("Desktop")) "Asistente de inversion.url"
if (Test-Path $acceso) { Remove-Item $acceso }
Write-Host ""
Write-Host "Hecho. Se conservan la carpeta del programa (con data\, tu historial) y el archivo de claves en $env:APPDATA\AsistenteInversion."
