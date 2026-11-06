# Conecta tu Google Drive con el bot (se hace una sola vez).
# Uso: clic derecho sobre este archivo -> "Ejecutar con PowerShell"
#   o en PowerShell:  powershell -ExecutionPolicy Bypass -File .\configurar_drive.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Paso($texto) { Write-Host "`n=== $texto" -ForegroundColor Cyan }

# 1. Instalar rclone si no está
if (-not (Get-Command rclone -ErrorAction SilentlyContinue)) {
    Paso "Instalando rclone..."
    winget install --id Rclone.Rclone -e --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Get-Command rclone -ErrorAction SilentlyContinue)) {
        Write-Host "rclone se instaló, pero esta ventana no lo ve todavía. Ciérrala y vuelve a ejecutar el script." -ForegroundColor Yellow
        Read-Host "Presiona Enter para salir"; exit 1
    }
}

# 2. Leer de config.yaml la carpeta raíz y las series
$config = Get-Content "config.yaml" -Encoding UTF8 -Raw
$remoto = [regex]::Match($config, 'remoto:\s*"([^"]+)"').Groups[1].Value
$nombreRemoto = $remoto.Split(":")[0]
$series = [regex]::Matches($config, 'carpeta:\s*"([^"]+)"') | ForEach-Object { $_.Groups[1].Value }

# 3. Dar permiso a Google Drive (solo la primera vez)
if ((rclone listremotes) -notcontains "${nombreRemoto}:") {
    Paso "Se abrirá el navegador: elige tu cuenta de Google y toca 'Permitir'."
    rclone config create $nombreRemoto drive scope=drive
    if ($LASTEXITCODE -ne 0) { Write-Host "No se pudo conectar con Drive." -ForegroundColor Red; Read-Host "Enter para salir"; exit 1 }
} else {
    Paso "Drive ya estaba conectado ($nombreRemoto)."
}

# 4. Crear las carpetas
Paso "Creando carpetas en $remoto ..."
$carpetas = @("procesados", "errores", "pendientes") + ($series | ForEach-Object { "entrada/$_" })
foreach ($c in $carpetas) {
    rclone mkdir "$remoto/$c"
    Write-Host "  OK  $remoto/$c"
}

# 5. Copiar la llave (contenido de rclone.conf) al portapapeles
$archivo = (rclone config file)[-1].Trim()
Get-Content $archivo -Raw | Set-Clipboard

Paso "Listo"
Write-Host "Revisa en drive.google.com que exista la carpeta '$($remoto.Split(':')[1])'."
Write-Host ""
Write-Host "La llave RCLONE_CONF YA ESTÁ COPIADA en tu portapapeles." -ForegroundColor Green
Write-Host "Ve a GitHub -> tu repositorio -> Settings -> Secrets and variables -> Actions ->"
Write-Host "New repository secret -> Name: RCLONE_CONF -> pega (Ctrl+V) en Secret -> Add secret."
Write-Host "(Si copias otra cosa antes, vuelve a ejecutar este script: no repite el permiso.)"
Read-Host "`nPresiona Enter para cerrar"
