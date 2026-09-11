# Compile le frontend et le place dans le paquet CLI (datavortex-cli/datavortex/static/).
# Équivalent Windows de build.sh — voir ce fichier pour le pourquoi.
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Static = Join-Path $Root "datavortex-cli\datavortex\static"

Write-Host "🔨 Build du frontend DataVortex"

Push-Location (Join-Path $Root "frontend")
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci a échoué" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build a échoué" }

    if (Test-Path $Static) { Remove-Item -Recurse -Force $Static }
    New-Item -ItemType Directory -Path $Static | Out-Null
    Copy-Item -Recurse -Path (Join-Path "dist" "*") -Destination $Static
}
finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $Static "index.html"))) {
    throw "$Static\index.html manquant après le build"
}

$Count = (Get-ChildItem -Recurse -File $Static).Count
Write-Host "✅ Frontend compilé dans datavortex-cli\datavortex\static\ ($Count fichiers)"
Write-Host "📦 Prochaine étape : git add datavortex-cli/datavortex/static ; git commit"
