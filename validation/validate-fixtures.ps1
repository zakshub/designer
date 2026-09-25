$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { $runtime = 'python' }
Push-Location $root
try {
  & $runtime -m sentinel validate
  if ($LASTEXITCODE -ne 0) { throw 'Schema or graph validation failed.' }
} finally { Pop-Location }
