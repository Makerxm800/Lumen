@echo off
setlocal
cd /d "%~dp0"

where cargo >nul 2>nul
if errorlevel 1 (
    echo Rust/Cargo was not found. Install the stable Rust toolchain from https://rustup.rs/
    exit /b 1
)

if not exist "runtime\mpv.exe" (
    echo Preparing the portable mpv runtime. This downloads about 30 MB from GitHub and requires 7-Zip.
    powershell -NoProfile -ExecutionPolicy Bypass -File prepare_runtime.ps1
    if errorlevel 1 exit /b 1
)

cargo build --release --manifest-path rust\Cargo.toml
if errorlevel 1 exit /b 1

if not exist dist mkdir dist
copy /Y "rust\target\release\Lumen.exe" "dist\Lumen.exe" >nul
if errorlevel 1 exit /b 1
if exist "dist\runtime" rmdir /s /q "dist\runtime"
xcopy "runtime" "dist\runtime\" /E /I /Y >nul
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   %CD%\dist\Lumen.exe
echo   %CD%\dist\runtime\  (bundled mpv media engine)
endlocal
