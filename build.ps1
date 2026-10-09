param([string]$Python = "python")

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all tkinterdnd2 --name LenzeCsvConverter LenzeCsvParser/main.py
    if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }
    Copy-Item -LiteralPath dist/LenzeCsvConverter.exe -Destination LenzeCsvParser/LenzeCsvConverter.exe -Force
} finally {
    Pop-Location
}
