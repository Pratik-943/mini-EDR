$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$build = Join-Path $root '.build\windows-agent'
$venv = Join-Path $build 'venv'
$dist = Join-Path $root 'dist'

Remove-Item -LiteralPath $build -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $build, $dist | Out-Null
python -m venv $venv
& "$venv\Scripts\python.exe" -m pip install --upgrade pip pyinstaller
& "$venv\Scripts\python.exe" -m pip install -r "$root\requirements.txt"
& "$venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --name mini-edr-agent --paths $root --distpath "$build\dist" --workpath "$build\work" --specpath "$build\spec" "$root\agent\main.py"

$wix = Get-Command wix -ErrorAction SilentlyContinue
if (-not $wix) {
    throw 'WiX Toolset is required. Install it with: winget install WiXToolset.WiXToolset'
}

& $wix.Source build "$PSScriptRoot\Package.wxs" "-dAgentExecutable=$build\dist\mini-edr-agent.exe" -arch x64 -o "$dist\mini-edr-agent-windows.msi"
Write-Host "Built $dist\mini-edr-agent-windows.msi"
