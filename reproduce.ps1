[CmdletBinding()]
param(
 [string]$AssetDirectory,
 [switch]$InstallOnly,
 [switch]$VerifyOnly,
 [string]$GameDir,
 [string]$World,
 [string]$JavaHome,
 [int]$GamePid = 0,
 [ValidateSet('both','ninfer','llama')][string]$Backend = 'both',
 [int]$Seconds = 300
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $PSScriptRoot
$setupTemp = Join-Path $PSScriptRoot 'cache\setup-temp'
New-Item -ItemType Directory -Force -Path $setupTemp | Out-Null
$env:TEMP = $setupTemp
$env:TMP = $setupTemp
$py = Join-Path $PSScriptRoot 'runtime-env\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) {
 & python -c "import sys,struct; assert sys.version_info >= (3,12) and struct.calcsize('P')==8, 'Python 3.12+ x64 required (tested 3.14.3)'"
 if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12+ x64 and add it to PATH.' }
 & python -m venv (Join-Path $PSScriptRoot 'runtime-env')
 if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& $py -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'pip initialization failed' }
& $py -m pip install --disable-pip-version-check -r requirements-runtime-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
$setupArgs = @('tools\install_release.py')
if ($AssetDirectory) { $setupArgs += @('--asset-directory',$AssetDirectory) }
if ($VerifyOnly) { $setupArgs += '--verify-only' }
& $py @setupArgs
if ($LASTEXITCODE -ne 0) { throw 'Artifact verification failed' }
if ($InstallOnly) { exit 0 }
$runArgs = @('tools\reproduce.py','--backend',$Backend,'--seconds',"$Seconds")
if ($GameDir) {
 if (-not $World) { throw '-World must name the current single-player save folder.' }
 $runArgs += @('--game-dir',$GameDir,'--world',$World)
 if ($JavaHome) { $runArgs += @('--java-home',$JavaHome) }
 if ($GamePid) { $runArgs += @('--pid',"$GamePid") }
}
& $py @runArgs
exit $LASTEXITCODE
