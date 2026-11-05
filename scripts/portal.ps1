[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "validate")]
    [string]$Action,

    [ValidateRange(0, 65535)]
    [int]$Port = 0,

    [ValidateRange(1, 5000)]
    [int]$Tail = 80
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if ($IsWindows -or $PSVersionTable.PSEdition -eq "Desktop") {
    & chcp.com 65001 | Out-Null
}
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$script:ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$script:EnvFile = Join-Path $script:ProjectRoot ".env"
$script:PythonExe = Join-Path $script:ProjectRoot ".venv\Scripts\python.exe"
$script:ManagePy = Join-Path $script:ProjectRoot "manage.py"
$script:RunPy = Join-Path $script:ProjectRoot "run.py"

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Test-Path -LiteralPath $script:EnvFile -PathType Leaf)) {
        return $null
    }
    foreach ($line in [IO.File]::ReadAllLines($script:EnvFile)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) { continue }
        if ($trimmed.Substring(0, $separator).Trim() -ne $Name) { continue }
        $value = $trimmed.Substring($separator + 1).Trim()
        if ($value.Length -ge 2) {
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        return $value
    }
    return $null
}

function Get-ConfigValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][string]$DefaultValue = $null
    )

    $processValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($null -ne $processValue -and $processValue.Trim()) {
        return $processValue.Trim()
    }
    $fileValue = Get-DotEnvValue -Name $Name
    if ($null -ne $fileValue -and $fileValue.Trim()) {
        return $fileValue.Trim()
    }
    return $DefaultValue
}

function Resolve-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ([IO.Path]::IsPathRooted($Value)) {
        return [IO.Path]::GetFullPath($Value)
    }
    return [IO.Path]::GetFullPath((Join-Path $script:ProjectRoot $Value))
}

function Resolve-PortalPort {
    if ($Port -gt 0) { return $Port }
    $configured = Get-ConfigValue -Name "PORTAL_PORT" -DefaultValue $null
    if (-not $configured) {
        $configured = Get-ConfigValue -Name "PORT" -DefaultValue "8000"
    }
    $parsed = 0
    if (-not [int]::TryParse($configured, [ref]$parsed) -or $parsed -lt 1 -or $parsed -gt 65535) {
        throw "PORTAL_PORT debe ser un número entre 1 y 65535. Valor recibido: '$configured'."
    }
    return $parsed
}

$script:ResolvedPort = Resolve-PortalPort
$script:RuntimeDir = Resolve-ProjectPath (Get-ConfigValue -Name "PORTAL_RUNTIME_DIR" -DefaultValue ".runtime\windows-portal")
$script:LogDir = Join-Path $script:RuntimeDir "logs"
$script:StdoutLog = Join-Path $script:LogDir "portal.stdout.log"
$script:StderrLog = Join-Path $script:LogDir "portal.stderr.log"
$script:PidFile = Join-Path $script:RuntimeDir "portal.pid"
$script:MetadataFile = Join-Path $script:RuntimeDir "portal.json"
$script:StaticRoot = Resolve-ProjectPath (Get-ConfigValue -Name "STATIC_ROOT" -DefaultValue "staticfiles")

function Ensure-WritableDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
            New-Item -ItemType Directory -Path $Path -Force | Out-Null
        }
        $probe = Join-Path $Path (".portal-write-test-{0}.tmp" -f [guid]::NewGuid().ToString("N"))
        [IO.File]::WriteAllText($probe, "ok", [Text.UTF8Encoding]::new($false))
        Remove-Item -LiteralPath $probe -Force
    }
    catch {
        throw "La cuenta '$([Security.Principal.WindowsIdentity]::GetCurrent().Name)' no puede escribir en $Purpose '$Path'. Corrige sus permisos NTFS. Detalle: $($_.Exception.Message)"
    }
}

function Assert-ExclusiveDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    $marker = Join-Path $Path ".portal-4dx-owner"
    if (Test-Path -LiteralPath $marker -PathType Leaf) {
        $owner = [IO.File]::ReadAllText($marker, [Text.Encoding]::UTF8).Trim()
        if ($owner -and $owner -ne $script:ProjectRoot) {
            throw "$Purpose '$Path' ya pertenece a otra instalación ('$owner'). Configura una carpeta exclusiva."
        }
    }
    [IO.File]::WriteAllText($marker, $script:ProjectRoot, [Text.UTF8Encoding]::new($false))
}

function Assert-RequiredFilesAndConfiguration {
    foreach ($required in @($script:PythonExe, $script:ManagePy, $script:RunPy)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Falta el archivo requerido '$required'. Crea .venv e instala requirements.lock.txt antes de iniciar."
        }
    }

    $engine = (Get-ConfigValue -Name "DB_ENGINE" -DefaultValue "oracle").ToLowerInvariant()
    if ($engine -eq "oracle") {
        $plainPassword = Get-ConfigValue -Name "ORACLE_PASSWORD" -DefaultValue $null
        $encodedPassword = Get-ConfigValue -Name "ORACLE_PASSWORD_B64" -DefaultValue $null
        if (-not $plainPassword -and -not $encodedPassword) {
            $passwordFileValue = Get-ConfigValue -Name "ORACLE_PASSWORD_FILE" -DefaultValue "secrets\oracle_password.txt"
            $passwordFile = Resolve-ProjectPath $passwordFileValue
            if (-not (Test-Path -LiteralPath $passwordFile -PathType Leaf)) {
                throw "Falta la contraseña Oracle. Crea '$passwordFile' con la contraseña en una sola línea o configura ORACLE_PASSWORD mediante el entorno seguro del servidor."
            }
            try {
                if (-not ([IO.File]::ReadAllText($passwordFile, [Text.Encoding]::UTF8).Trim())) {
                    throw "el archivo está vacío"
                }
            }
            catch {
                throw "No se puede leer la contraseña Oracle en '$passwordFile'. Concede lectura a la cuenta de servicio. Detalle: $($_.Exception.Message)"
            }
        }
    }

    $configuredSecretKey = Get-ConfigValue -Name "SECRET_KEY" -DefaultValue $null
    if (-not $configuredSecretKey -or $configuredSecretKey -eq "change-me") {
        $secretKeyFileValue = Get-ConfigValue -Name "SECRET_KEY_FILE" -DefaultValue "runtime-config\django_secret_key.txt"
        $secretKeyFile = Resolve-ProjectPath $secretKeyFileValue
        $secretKeyDirectory = Split-Path -Parent $secretKeyFile
        Ensure-WritableDirectory -Path $secretKeyDirectory -Purpose "la carpeta de la clave privada de Django"
        if (Test-Path -LiteralPath $secretKeyFile -PathType Leaf) {
            try {
                if (-not ([IO.File]::ReadAllText($secretKeyFile, [Text.Encoding]::UTF8).Trim())) {
                    throw "el archivo está vacío"
                }
            }
            catch {
                throw "No se puede leer la clave privada de Django en '$secretKeyFile'. Detalle: $($_.Exception.Message)"
            }
        }
    }

    $mailRecipients = Get-ConfigValue -Name "CORREO_PARA" -DefaultValue $null
    if ($mailRecipients) {
        foreach ($name in @("CORREO_SSH_HOST", "CORREO_SSH_USER", "CORREO_SSH_PASSWORD")) {
            if (-not (Get-ConfigValue -Name $name -DefaultValue $null)) {
                Write-Warning "Integración de correo: $name no está definido en el entorno o .env. El portal puede iniciar, pero el envío de correo podría fallar."
            }
        }
        $mailWorkDir = Resolve-ProjectPath "work"
        Ensure-WritableDirectory -Path $mailWorkDir -Purpose "los archivos privados de la integración de correo"
        $knownHosts = Join-Path $mailWorkDir "correo_known_hosts"
        if (Test-Path -LiteralPath $knownHosts -PathType Leaf) {
            try {
                $stream = [IO.File]::Open($knownHosts, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
                $stream.Dispose()
            }
            catch {
                throw "La integración de correo no puede leer y actualizar '$knownHosts'. Corrige sus permisos NTFS. Detalle: $($_.Exception.Message)"
            }
        }
    }

    Ensure-WritableDirectory -Path $script:RuntimeDir -Purpose "la carpeta privada de ejecución"
    Ensure-WritableDirectory -Path $script:LogDir -Purpose "la carpeta de logs"
    Ensure-WritableDirectory -Path $script:StaticRoot -Purpose "STATIC_ROOT"
    Assert-ExclusiveDirectory -Path $script:RuntimeDir -Purpose "La carpeta privada de ejecución"
    Assert-ExclusiveDirectory -Path $script:StaticRoot -Purpose "STATIC_ROOT"
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Host "==> $Description"
    & $script:PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description falló con código $LASTEXITCODE."
    }
}

function Test-PortAvailable {
    param([Parameter(Mandatory = $true)][int]$PortNumber)

    $listener = $null
    try {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, $PortNumber)
        $listener.Start()
        return $true
    }
    catch [Net.Sockets.SocketException] {
        return $false
    }
    finally {
        if ($null -ne $listener) {
            try { $listener.Stop() } catch { }
        }
    }
}

function Read-PidValue {
    if (-not (Test-Path -LiteralPath $script:PidFile -PathType Leaf)) { return $null }
    $value = [IO.File]::ReadAllText($script:PidFile).Trim()
    $pidValue = 0
    if (-not [int]::TryParse($value, [ref]$pidValue) -or $pidValue -le 0) {
        throw "El archivo PID '$script:PidFile' está dañado. Elimínalo solo después de confirmar que este portal no está en ejecución."
    }
    return $pidValue
}

function Read-PortalMetadata {
    if (-not (Test-Path -LiteralPath $script:MetadataFile -PathType Leaf)) { return $null }
    try {
        return ([IO.File]::ReadAllText($script:MetadataFile, [Text.Encoding]::UTF8) | ConvertFrom-Json)
    }
    catch {
        throw "No se pudo leer la metadata '$script:MetadataFile'. Detalle: $($_.Exception.Message)"
    }
}

function Get-OwnedPortalProcess {
    param([switch]$Quiet)

    $pidValue = Read-PidValue
    if ($null -eq $pidValue) { return $null }
    try {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction Stop
    }
    catch {
        throw "No se pudo consultar el PID $pidValue. Ejecuta el comando con una cuenta autorizada para administrar este portal. Detalle: $($_.Exception.Message)"
    }
    if ($null -eq $processInfo) {
        Remove-Item -LiteralPath $script:PidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $script:MetadataFile -Force -ErrorAction SilentlyContinue
        if (-not $Quiet) { Write-Host "Se eliminó un PID obsoleto ($pidValue)." }
        return $null
    }

    $expectedPython = [IO.Path]::GetFullPath($script:PythonExe).ToLowerInvariant()
    $actualExecutable = ""
    if ($processInfo.ExecutablePath) {
        $actualExecutable = [IO.Path]::GetFullPath($processInfo.ExecutablePath).ToLowerInvariant()
    }
    $commandLine = [string]$processInfo.CommandLine
    $expectedRun = [IO.Path]::GetFullPath($script:RunPy)
    $owned = ($actualExecutable -eq $expectedPython) -and
             ($commandLine.IndexOf($expectedRun, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    if (-not $owned) {
        throw "El PID $pidValue existe, pero no pertenece con certeza a este portal. No se detendrá. Revisa '$script:PidFile' y el proceso manualmente."
    }
    return $processInfo
}

function Write-PortalMetadata {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    $metadata = [ordered]@{
        project = $script:ProjectRoot
        python = $script:PythonExe
        runScript = $script:RunPy
        pid = $ProcessId
        port = $script:ResolvedPort
        stdout = $script:StdoutLog
        stderr = $script:StderrLog
        startedAt = [DateTime]::UtcNow.ToString("o")
    }
    [IO.File]::WriteAllText($script:PidFile, [string]$ProcessId, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText(
        $script:MetadataFile,
        ($metadata | ConvertTo-Json -Depth 3),
        [Text.UTF8Encoding]::new($false)
    )
}

function Invoke-PortalValidation {
    Assert-RequiredFilesAndConfiguration
    $env:DEBUG = "False"
    $env:PORTAL_PORT = [string]$script:ResolvedPort
    $env:STATIC_ROOT = $script:StaticRoot
    if (-not $env:WEB_BIND_ADDRESS) { $env:WEB_BIND_ADDRESS = "0.0.0.0" }

    Push-Location $script:ProjectRoot
    try {
        Invoke-CheckedCommand -Description "Validación de Django" -Arguments @($script:ManagePy, "check")
        Write-Host "==> Revisión de seguridad de despliegue (sus resultados son advertencias)"
        & $script:PythonExe $script:ManagePy check --deploy
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Django detectó advertencias de despliegue. Revisa HTTPS, cookies y ALLOWED_HOSTS antes de exponer el proxy; esto no sustituye los errores bloqueantes."
        }
        Invoke-CheckedCommand -Description "Conexión, migraciones y esquema de base de datos" -Arguments @($script:RunPy, "--check", "--port", [string]$script:ResolvedPort)
        Invoke-CheckedCommand -Description "Preparación de archivos estáticos" -Arguments @($script:ManagePy, "collectstatic", "--noinput", "--verbosity", "0")
    }
    finally {
        Pop-Location
    }
    Write-Host "Validaciones completadas. STATIC_ROOT: $script:StaticRoot"
}

function Wait-PortalHttp {
    param(
        [Parameter(Mandatory = $true)][int]$PortNumber,
        [int]$TimeoutSeconds = 30
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $client = [Net.Sockets.TcpClient]::new()
            $client.Connect("127.0.0.1", $PortNumber)
            $stream = $client.GetStream()
            $request = [Text.Encoding]::ASCII.GetBytes("GET /login/ HTTP/1.1`r`nHost: 127.0.0.1`r`nConnection: close`r`n`r`n")
            $stream.Write($request, 0, $request.Length)
            $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::ASCII)
            $statusLine = $reader.ReadLine()
            $reader.Dispose()
            $client.Dispose()
            if ($statusLine -and $statusLine.StartsWith("HTTP/")) { return $statusLine }
        }
        catch {
            if ($null -ne $client) { try { $client.Dispose() } catch { } }
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    return $null
}

function Show-LogFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    Write-Host "`n--- ${Label}: $Path ---"
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Write-Host "Todavía no existe."
        return
    }
    try {
        Get-Content -LiteralPath $Path -Tail $Tail -Encoding UTF8
    }
    catch {
        $message = "No se pudo leer '$Path': $($_.Exception.Message)"
        Write-Host "ERROR: $message" -ForegroundColor Red
        Write-Host "Un administrador puede conceder lectura con:"
        Write-Host ('  icacls "{0}" /grant "DOMINIO\USUARIO:(OI)(CI)R" /T' -f $script:LogDir)
        throw $message
    }
}

function Show-PortalLogs {
    Show-LogFile -Path $script:StdoutLog -Label "Salida"
    Show-LogFile -Path $script:StderrLog -Label "Errores"
}

function Start-Portal {
    $existing = Get-OwnedPortalProcess -Quiet
    if ($null -ne $existing) {
        $metadata = Read-PortalMetadata
        $activePort = if ($null -ne $metadata -and $metadata.port) { $metadata.port } else { $script:ResolvedPort }
        Write-Host "El portal ya está activo. PID: $($existing.ProcessId), puerto: $activePort."
        return
    }
    if (-not (Test-PortAvailable -PortNumber $script:ResolvedPort)) {
        throw "El puerto $script:ResolvedPort ya está ocupado. No se inició este portal ni se detuvo ningún otro proceso."
    }

    Invoke-PortalValidation
    if (-not (Test-PortAvailable -PortNumber $script:ResolvedPort)) {
        throw "El puerto $script:ResolvedPort dejó de estar disponible durante las validaciones. No se inició el portal."
    }

    $env:PORTAL_PORT = [string]$script:ResolvedPort
    $env:STATIC_ROOT = $script:StaticRoot
    $env:WEB_BIND_ADDRESS = "0.0.0.0"
    $env:DEBUG = "False"
    $arguments = '"{0}" --host 0.0.0.0 --port {1}' -f $script:RunPy, $script:ResolvedPort
    $process = Start-Process -FilePath $script:PythonExe `
        -ArgumentList $arguments `
        -WorkingDirectory $script:ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $script:StdoutLog `
        -RedirectStandardError $script:StderrLog `
        -PassThru
    Write-PortalMetadata -ProcessId $process.Id

    $statusLine = Wait-PortalHttp -PortNumber $script:ResolvedPort -TimeoutSeconds 30
    $process.Refresh()
    if ($process.HasExited -or -not $statusLine) {
        Show-PortalLogs
        Remove-Item -LiteralPath $script:PidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $script:MetadataFile -Force -ErrorAction SilentlyContinue
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        throw "El proceso no respondió correctamente en http://127.0.0.1:$script:ResolvedPort/login/. Revisa los logs anteriores."
    }
    Write-Host "Portal iniciado en segundo plano."
    Write-Host "PID: $($process.Id)"
    Write-Host "Escucha: 0.0.0.0:$script:ResolvedPort"
    Write-Host "Respuesta local: $statusLine"
    Write-Host "Logs: $script:LogDir"
}

function Stop-Portal {
    $ownedProcess = Get-OwnedPortalProcess
    if ($null -eq $ownedProcess) {
        Write-Host "El portal no está activo. No se detuvo ningún proceso."
        return
    }
    $pidValue = [int]$ownedProcess.ProcessId
    Stop-Process -Id $pidValue -ErrorAction Stop
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 250
        $stillRunning = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    } while ($null -ne $stillRunning -and [DateTime]::UtcNow -lt $deadline)
    if ($null -ne $stillRunning) {
        $confirmed = Get-OwnedPortalProcess -Quiet
        if ($null -ne $confirmed) { Stop-Process -Id $pidValue -Force -ErrorAction Stop }
    }
    Remove-Item -LiteralPath $script:PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $script:MetadataFile -Force -ErrorAction SilentlyContinue
    Write-Host "Portal detenido. PID anterior: $pidValue."
}

function Show-PortalStatus {
    $ownedProcess = Get-OwnedPortalProcess -Quiet
    $metadata = if ($null -ne $ownedProcess) { Read-PortalMetadata } else { $null }
    $activePort = if ($null -ne $metadata -and $metadata.port) { $metadata.port } else { $script:ResolvedPort }
    Write-Host "Proyecto: $script:ProjectRoot"
    if ($null -eq $ownedProcess) {
        Write-Host "Estado: INACTIVO"
    }
    else {
        Write-Host "Estado: ACTIVO"
        Write-Host "PID: $($ownedProcess.ProcessId)"
    }
    Write-Host "Puerto: $activePort"
    Write-Host "PID file: $script:PidFile"
    Write-Host "Logs: $script:LogDir"
}

switch ($Action.ToLowerInvariant()) {
    "start" { Start-Portal }
    "stop" { Stop-Portal }
    "restart" { Stop-Portal; Start-Portal }
    "status" { Show-PortalStatus }
    "logs" { Show-PortalLogs }
    "validate" {
        if (-not (Test-PortAvailable -PortNumber $script:ResolvedPort)) {
            $owned = Get-OwnedPortalProcess -Quiet
            if ($null -eq $owned) {
                throw "El puerto $script:ResolvedPort está ocupado por otro proceso."
            }
            Write-Warning "El puerto $script:ResolvedPort está ocupado por este portal; se validará sin intentar reservarlo."
        }
        Invoke-PortalValidation
    }
}
