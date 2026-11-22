param (
    [string]$Configuration = "Debug"
)

$ErrorActionPreference = "Stop"

$vsPath = "C:\Program Files\Microsoft Visual Studio\18\Community"
$vcvars = Join-Path $vsPath "VC\Auxiliary\Build\vcvars64.bat"
$wdkInclude = "C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0"
$wdkLib = "C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0"

$workspaceRoot = $PSScriptRoot | Split-Path -Parent
$srcDir = Join-Path $workspaceRoot "MinifilterDriver"
$outDir = Join-Path $srcDir "bin"
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

$sourceFile = Join-Path $srcDir "RansomAgent.c"
$infFile = Join-Path $srcDir "RansomAgent.inf"
$infDest = Join-Path $outDir "RansomAgent.inf"

if (Test-Path $infFile) {
    Copy-Item $infFile $infDest -Force
}

if (-not (Test-Path $sourceFile)) {
    Write-Host "[ERROR] Source file not found: $sourceFile" -ForegroundColor Red
    exit 1
}

# Run inside $srcDir to avoid any Unicode path issues with cl.exe / cmd.exe
Push-Location $srcDir
try {
    $cmd = @"
@echo off
chcp 65001 >nul
call "$vcvars" >nul

cl.exe /c /nologo /W3 /WX- /Od /Oi /kernel /std:c17 /FC ^
  /I "$wdkInclude\km" ^
  /I "$wdkInclude\km\crt" ^
  /I "$wdkInclude\shared" ^
  /D _AMD64_ /D AMD64 /D CONDITION_HANDLING=1 /D NT_UP=1 /D NT_INST=0 /D WIN32=100 /D _NT1X_=100 /D WINNT=1 /D _WIN32_WINNT=0x0A00 /D WINVER=0x0A00 /D DEVL=1 /D DBG=1 ^
  /Fo"bin\RansomAgent.obj" "RansomAgent.c"

if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

link.exe /nologo /DRIVER /ENTRY:DriverEntry /SUBSYSTEM:NATIVE /MERGE:_PAGE=PAGE /MERGE:_TEXT=.text /SECTION:INIT,d /OPT:REF /OPT:ICF /INCREMENTAL:NO ^
  /LIBPATH:"$wdkLib\km\x64" ^
  fltMgr.lib ntoskrnl.lib BufferOverflowK.lib hal.lib ^
  /OUT:"bin\RansomAgent.sys" "bin\RansomAgent.obj"

if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
"@

    $tempBat = [System.IO.Path]::GetTempFileName() + ".bat"
    [System.IO.File]::WriteAllText($tempBat, $cmd, [System.Text.Encoding]::UTF8)
    & cmd.exe /c $tempBat
    $exitCode = $LASTEXITCODE
    if (Test-Path $tempBat) {
        Remove-Item -Path $tempBat -Force
    }

    $sysFile = Join-Path $outDir "RansomAgent.sys"
    if ($exitCode -eq 0 -and (Test-Path $sysFile)) {
        Write-Host ""
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host " [SUCCESS] Minifilter Driver built successfully!" -ForegroundColor Green
        Write-Host " Binary: $sysFile" -ForegroundColor Cyan
        Write-Host " INF:    $infDest" -ForegroundColor Cyan
        Write-Host "==========================================================" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[ERROR] Driver build failed with exit code $exitCode" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}
