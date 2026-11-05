[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ServiceAccount,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$PublicUrl,

    [ValidateRange(1, 65535)]
    [int]$Port = 8000,

    [ValidateNotNullOrEmpty()]
    [string]$TaskName = "Portal 4DX - Inicio automático",

    [switch]$AllowInternalHttp
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if ($IsWindows -or $PSVersionTable.PSEdition -eq "Desktop") {
    & chcp.com 65001 | Out-Null
}
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$controller = Join-Path $PSScriptRoot "portal.ps1"
$envFile = Join-Path $projectRoot ".env"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Este script debe ejecutarse desde PowerShell como administrador para registrar la tarea programada."
    }
}

function ConvertTo-AbsoluteUrl {
    param([Parameter(Mandatory = $true)][string]$Value)

    $uri = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri)) {
        throw "PublicUrl debe ser una URL absoluta, por ejemplo http://10.0.0.15:$Port."
    }
    if ($uri.Scheme -notin @("http", "https")) {
        throw "PublicUrl solo admite los esquemas http o https."
    }
    if ($uri.AbsolutePath -ne "/" -or $uri.Query -or $uri.Fragment) {
        throw "PublicUrl debe contener solo esquema, host y puerto, sin ruta, consulta ni fragmento."
    }
    if ($uri.Scheme -eq "http" -and -not $AllowInternalHttp) {
        throw "HTTP interno requiere el parámetro -AllowInternalHttp. Para acceso externo usa un proxy inverso con HTTPS."
    }
    return $uri
}

function Set-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowEmptyString()][Parameter(Mandatory = $true)][string]$Value
    )

    $lines = [Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $envFile -PathType Leaf) {
        foreach ($line in [IO.File]::ReadAllLines($envFile)) { $lines.Add($line) }
    }
    $pattern = '^\s*' + [regex]::Escape($Name) + '\s*='
    $replacement = "$Name=$Value"
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) {
            if (-not $found) {
                $lines[$index] = $replacement
                $found = $true
            }
            else {
                $lines.RemoveAt($index)
                $index--
            }
        }
    }
    if (-not $found) { $lines.Add($replacement) }
    [IO.File]::WriteAllLines($envFile, $lines, [Text.UTF8Encoding]::new($false))
}

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) { return $null }
    foreach ($line in [IO.File]::ReadAllLines($envFile)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1 -or $trimmed.Substring(0, $separator).Trim() -ne $Name) { continue }
        return $trimmed.Substring($separator + 1).Trim().Trim('"').Trim("'")
    }
    return $null
}

function Merge-CommaValue {
    param(
        [AllowNull()][string]$Existing,
        [Parameter(Mandatory = $true)][string]$RequiredValue
    )

    if ($Existing -eq "*") { return $RequiredValue }
    $items = [Collections.Generic.List[string]]::new()
    foreach ($item in (($Existing -split ",") + @($RequiredValue))) {
        $candidate = $item.Trim()
        if ($candidate -and -not $items.Contains($candidate)) { $items.Add($candidate) }
    }
    return ($items -join ",")
}

function Save-PublicConfiguration {
    param([Parameter(Mandatory = $true)][Uri]$Uri)

    $origin = $Uri.GetLeftPart([UriPartial]::Authority).TrimEnd("/")
    Set-DotEnvValue -Name "DEBUG" -Value "False"
    Set-DotEnvValue -Name "PORTAL_PORT" -Value ([string]$Port)
    Set-DotEnvValue -Name "WEB_BIND_ADDRESS" -Value "0.0.0.0"
    if (-not (Get-DotEnvValue "PORTAL_RUNTIME_DIR")) {
        Set-DotEnvValue -Name "PORTAL_RUNTIME_DIR" -Value ".runtime\windows-portal"
    }
    if (-not (Get-DotEnvValue "STATIC_ROOT")) {
        Set-DotEnvValue -Name "STATIC_ROOT" -Value "staticfiles"
    }
    Set-DotEnvValue -Name "PORTAL_PUBLIC_URL" -Value $origin
    Set-DotEnvValue -Name "ALLOWED_HOSTS" -Value (Merge-CommaValue (Get-DotEnvValue "ALLOWED_HOSTS") $Uri.Host)
    if ($Uri.Scheme -eq "https") {
        Set-DotEnvValue -Name "CSRF_TRUSTED_ORIGINS" -Value (Merge-CommaValue (Get-DotEnvValue "CSRF_TRUSTED_ORIGINS") $origin)
        Set-DotEnvValue -Name "COOKIE_SECURE" -Value "true"
        Set-DotEnvValue -Name "TRUST_PROXY_HTTPS" -Value "true"
        Set-DotEnvValue -Name "SECURE_SSL_REDIRECT" -Value "true"
    }
    else {
        Set-DotEnvValue -Name "COOKIE_SECURE" -Value "false"
        Set-DotEnvValue -Name "TRUST_PROXY_HTTPS" -Value "false"
        Set-DotEnvValue -Name "SECURE_SSL_REDIRECT" -Value "false"
        Write-Warning "El portal se publicará por HTTP solo para la red interna. No abras este puerto directamente a Internet."
    }
}

function Invoke-Controller {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $controller @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "El controlador del portal falló con código $LASTEXITCODE."
    }
}

function Get-TaskBackup {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) { return $null }
    if ($existing.Principal.UserId -and
        $existing.Principal.UserId -ne $ServiceAccount) {
        throw "La tarea '$TaskName' pertenece a '$($existing.Principal.UserId)'. Para actualizarla de forma recuperable usa esa misma cuenta de servicio o elige otro -TaskName."
    }
    return Export-ScheduledTask -TaskName $TaskName
}

function Get-RuntimePidPath {
    $runtimeValue = Get-DotEnvValue "PORTAL_RUNTIME_DIR"
    if (-not $runtimeValue) { $runtimeValue = [Environment]::GetEnvironmentVariable("PORTAL_RUNTIME_DIR", "Process") }
    if (-not $runtimeValue) { $runtimeValue = ".runtime\windows-portal" }
    if ([IO.Path]::IsPathRooted($runtimeValue)) {
        $runtimePath = [IO.Path]::GetFullPath($runtimeValue)
    }
    else {
        $runtimePath = [IO.Path]::GetFullPath((Join-Path $projectRoot $runtimeValue))
    }
    return (Join-Path $runtimePath "portal.pid")
}

function Restore-Task {
    param(
        [AllowNull()][string]$Xml,
        [Parameter(Mandatory = $true)][string]$PlainPassword
    )

    if ($Xml) {
        Register-ScheduledTask -TaskName $TaskName -Xml $Xml -User $ServiceAccount -Password $PlainPassword -Force | Out-Null
        Start-ScheduledTask -TaskName $TaskName
        Write-Warning "Se restauró la definición anterior de la tarea '$TaskName'."
    }
    else {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Warning "Se eliminó la tarea nueva '$TaskName' porque la prueba de inicio falló."
    }
}

function Restore-EnvironmentFile {
    param(
        [Parameter(Mandatory = $true)][bool]$Existed,
        [AllowNull()][byte[]]$Content
    )

    if ($Existed) {
        [IO.File]::WriteAllBytes($envFile, $Content)
    }
    else {
        Remove-Item -LiteralPath $envFile -Force -ErrorAction SilentlyContinue
    }
}

Assert-Administrator
if (-not (Test-Path -LiteralPath $controller -PathType Leaf)) {
    throw "No existe el controlador '$controller'."
}
$publicUri = ConvertTo-AbsoluteUrl -Value $PublicUrl
$envExisted = Test-Path -LiteralPath $envFile -PathType Leaf
$envBackup = if ($envExisted) { [IO.File]::ReadAllBytes($envFile) } else { $null }
try {
    Save-PublicConfiguration -Uri $publicUri
    Write-Host "Validando el portal antes de registrar la tarea..."
    Invoke-Controller -Arguments @("validate", "-Port", [string]$Port)
}
catch {
    Restore-EnvironmentFile -Existed $envExisted -Content $envBackup
    throw
}

$securePassword = Read-Host "Contraseña de $ServiceAccount" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$plainPassword = $null
$taskBackup = $null
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if (-not $plainPassword) { throw "La contraseña de la cuenta de servicio está vacía." }
    $taskBackup = Get-TaskBackup

    $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" start -Port {1}' -f $controller, $Port
    $taskAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $projectRoot
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description "Inicia el Portal 4DX con Waitress al arrancar Windows." `
        -Action $taskAction `
        -Trigger $trigger `
        -Settings $settings `
        -User $ServiceAccount `
        -Password $plainPassword `
        -RunLevel Limited `
        -Force | Out-Null

    Write-Host "Probando la tarea con la cuenta de servicio..."
    Invoke-Controller -Arguments @("stop", "-Port", [string]$Port)
    Start-ScheduledTask -TaskName $TaskName
    $deadline = [DateTime]::UtcNow.AddSeconds(120)
    $started = $false
    $pidPath = Get-RuntimePidPath
    do {
        Start-Sleep -Seconds 2
        $taskState = (Get-ScheduledTask -TaskName $TaskName).State
        if ($taskState -ne "Running" -and (Test-Path -LiteralPath $pidPath -PathType Leaf)) {
            try {
                $pidValue = [int]([IO.File]::ReadAllText($pidPath).Trim())
                $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
                $portResponds = Test-NetConnection -ComputerName "127.0.0.1" -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
                if ($taskInfo.LastTaskResult -eq 0 -and $portResponds -and (Get-Process -Id $pidValue -ErrorAction SilentlyContinue)) {
                    $started = $true
                    break
                }
            }
            catch { }
        }
    } while ([DateTime]::UtcNow -lt $deadline)

    if (-not $started) {
        $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
        throw "La tarea no dejó el portal activo. LastTaskResult=$($taskInfo.LastTaskResult). Revisa permisos de la cuenta sobre el proyecto, STATIC_ROOT y la carpeta .runtime."
    }

    Write-Host "Tarea programada registrada y probada correctamente."
    Write-Host "Tarea: $TaskName"
    Write-Host "Cuenta: $ServiceAccount"
    Write-Host "URL configurada: $($publicUri.GetLeftPart([UriPartial]::Authority))"
    Write-Host "Puerto: $Port"
    Invoke-Controller -Arguments @("status", "-Port", [string]$Port)
}
catch {
    Restore-EnvironmentFile -Existed $envExisted -Content $envBackup
    if ($null -ne $plainPassword) {
        try { Restore-Task -Xml $taskBackup -PlainPassword $plainPassword } catch { Write-Warning "No se pudo restaurar la tarea anterior: $($_.Exception.Message)" }
    }
    throw
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $plainPassword = $null
    $securePassword = $null
}
