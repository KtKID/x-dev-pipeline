[CmdletBinding()]
param(
    [string]$PluginName = "x-dev-pipeline",
    [string]$SourceDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[info] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[ok]   $Message" -ForegroundColor Green
}

function New-MarketplaceObject {
    return [pscustomobject]@{
        name = "local-plugins"
        interface = [pscustomobject]@{
            displayName = "Local Plugins"
        }
        plugins = @()
    }
}

function Read-MarketplaceObject {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return New-MarketplaceObject
    }

    $raw = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return New-MarketplaceObject
    }

    $parsed = ConvertFrom-Json -InputObject $raw
    if (-not ($parsed.PSObject.Properties.Name -contains "plugins") -or $null -eq $parsed.plugins) {
        Add-Member -InputObject $parsed -MemberType NoteProperty -Name plugins -Value @() -Force
    }

    if (-not ($parsed.plugins -is [System.Collections.IList])) {
        $parsed.plugins = @($parsed.plugins)
    }

    if (-not ($parsed.PSObject.Properties.Name -contains "name") -or [string]::IsNullOrWhiteSpace([string]$parsed.name)) {
        $parsed.name = "local-plugins"
    }

    if (-not ($parsed.PSObject.Properties.Name -contains "interface") -or $null -eq $parsed.interface) {
        $parsed.interface = [pscustomobject]@{
            displayName = "Local Plugins"
        }
    }

    return $parsed
}

function Update-MarketplaceFile {
    param(
        [string]$Path,
        [string]$PluginName,
        [string]$SourcePath
    )

    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $marketplace = Read-MarketplaceObject -Path $Path
    $updatedPlugins = @()
    $found = $false

    foreach ($plugin in @($marketplace.plugins)) {
        if ($plugin.name -eq $PluginName) {
            $updatedPlugins += [pscustomobject]@{
                name = $PluginName
                source = [pscustomobject]@{
                    source = "local"
                    path = $SourcePath
                }
                policy = [pscustomobject]@{
                    installation = "AVAILABLE"
                    authentication = "ON_INSTALL"
                }
                category = "Productivity"
            }
            $found = $true
            continue
        }

        $updatedPlugins += $plugin
    }

    if (-not $found) {
        $updatedPlugins += [pscustomobject]@{
            name = $PluginName
            source = [pscustomobject]@{
                source = "local"
                path = $SourcePath
            }
            policy = [pscustomobject]@{
                installation = "AVAILABLE"
                authentication = "ON_INSTALL"
            }
            category = "Productivity"
        }
    }

    $marketplace.plugins = $updatedPlugins
    $json = $marketplace | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    Write-Ok "Updated marketplace: $Path"
}

if ([string]::IsNullOrWhiteSpace($SourceDir)) {
    $SourceDir = $PSScriptRoot
}

$sourceRoot = (Resolve-Path -LiteralPath $SourceDir).Path
$userProfile = [Environment]::GetFolderPath("UserProfile")
$codexHome = Join-Path $userProfile ".codex"
$codexPluginsDir = Join-Path $codexHome "plugins"
$targetDir = Join-Path $codexPluginsDir $PluginName
$agentsMarketplace = Join-Path $userProfile ".agents\plugins\marketplace.json"
$codexMarketplace = Join-Path $codexHome "marketplace.json"
$codexPluginsMarketplace = Join-Path $codexPluginsDir "marketplace.json"

Write-Info "Source: $sourceRoot"
Write-Info "Target: $targetDir"

New-Item -ItemType Directory -Force -Path $codexPluginsDir | Out-Null
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$null = robocopy $sourceRoot $targetDir /MIR /XD .git tmp /NFL /NDL /NJH /NJS /NP
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -gt 7) {
    throw "robocopy failed with exit code $robocopyExit"
}
Write-Ok "Synced plugin files to $targetDir"

Update-MarketplaceFile -Path $agentsMarketplace -PluginName $PluginName -SourcePath "./.codex/plugins/$PluginName"
Update-MarketplaceFile -Path $codexMarketplace -PluginName $PluginName -SourcePath "./.codex/plugins/$PluginName"
Update-MarketplaceFile -Path $codexPluginsMarketplace -PluginName $PluginName -SourcePath ($targetDir -replace "\\", "/")

Write-Host ""
Write-Ok "Codex deployment completed."
Write-Host "Open Codex in this repo or restart Codex to refresh plugin discovery." -ForegroundColor Yellow
