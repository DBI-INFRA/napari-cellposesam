# Install napari and napari-cellposesam (Windows) into a folder of their own, with the PyTorch
# build that fits this machine's GPU, and add Start menu and desktop shortcuts.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/installer/install.ps1 | iex"
#
# Run it again to update. To uninstall, set $env:NAPARI_CELLPOSESAM_UNINSTALL = 1 first, or run
# the saved copy of this script with -Uninstall.
#
# Environment variables:
#   NAPARI_CELLPOSESAM_HOME   install folder (default: %LOCALAPPDATA%\napari-cellposesam)
#   NAPARI_CELLPOSESAM_SPEC   what to install (default: napari-cellposesam), e.g. a version pin,
#                             a wheel or a git URL
#   NAPARI_CELLPOSESAM_TORCH  PyTorch build (default: auto), e.g. cpu or cu128
#   NAPARI_CELLPOSESAM_NO_DESKTOP=1  add the Start menu entry only, no desktop icon (or -NoDesktop)
#   NAPARI_CELLPOSESAM_MODEL=1 or 0  download the Cellpose-SAM model now, or not (or -Model yes/no);
#                             without it, the script asks
#
# -PauseOnError keeps the window open after a failure, for runs from the setup .exe
param([switch]$Uninstall, [switch]$NoDesktop, [switch]$PauseOnError,
      [ValidateSet('ask', 'yes', 'no')][string]$Model = 'ask')

$ErrorActionPreference = 'Stop'
trap {
    Write-Host "error: $_" -ForegroundColor Red
    if ($PauseOnError) { Read-Host 'Press Enter to close' }
    exit 1
}
# Invoke-WebRequest is many times slower with its progress bar on
$ProgressPreference = 'SilentlyContinue'

$UvVersion = '0.13.5'
$PythonVersion = '3.12'
$Root = if ($env:NAPARI_CELLPOSESAM_HOME) { $env:NAPARI_CELLPOSESAM_HOME } else { Join-Path $env:LOCALAPPDATA 'napari-cellposesam' }
$Spec = if ($env:NAPARI_CELLPOSESAM_SPEC) { $env:NAPARI_CELLPOSESAM_SPEC } else { 'napari-cellposesam' }
$Torch = if ($env:NAPARI_CELLPOSESAM_TORCH) { $env:NAPARI_CELLPOSESAM_TORCH } else { 'auto' }
# marks a folder this script made, so uninstalling never deletes anything else
$Marker = Join-Path $Root '.napari-cellposesam-install'
$Uv = Join-Path $Root 'bin\uv.exe'
$Python = Join-Path $Root 'env\Scripts\python.exe'

function Say($message) { Write-Host "==> $message" -ForegroundColor Cyan }

# native commands do not stop the script on failure by themselves
function Run {
    & $args[0] @($args | Select-Object -Skip 1)
    if ($LASTEXITCODE -ne 0) { throw "$($args[0]) failed with exit code $LASTEXITCODE" }
}

if ($Uninstall -or $env:NAPARI_CELLPOSESAM_UNINSTALL -eq '1') {
    if (-not (Test-Path $Marker)) { throw "$Root is not a napari-cellposesam install" }
    if (Test-Path $Python) { & $Python -m napari_cellposesam shortcut --remove }
    Remove-Item -Recurse -Force $Root
    Say "Removed $Root"
    return
}

if ((Test-Path $Root) -and -not (Test-Path $Marker) -and (Get-ChildItem -Force $Root | Select-Object -First 1)) {
    throw "$Root exists and was not made by this installer; set NAPARI_CELLPOSESAM_HOME to another folder"
}
if ($env:NAPARI_CELLPOSESAM_MODEL -eq '1') { $Model = 'yes' }
if ($env:NAPARI_CELLPOSESAM_MODEL -eq '0') { $Model = 'no' }
if ($Model -eq 'ask') {
    $answer = Read-Host 'Download the Cellpose-SAM model (about 1.2 GB) now? Otherwise napari downloads it the first time you segment. [Y/n]'
    $Model = if ($answer -match '^[nN]') { 'no' } else { 'yes' }
}

New-Item -ItemType Directory -Force $Root | Out-Null
New-Item -ItemType File -Force $Marker | Out-Null

# python, packages and their cache stay inside $Root, so deleting it removes everything
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root 'python'
$env:UV_CACHE_DIR = Join-Path $Root 'cache'
$env:UV_NO_CONFIG = '1'

if (-not (Test-Path $Uv) -or ((& $Uv --version) -split ' ')[1] -ne $UvVersion) {
    Say "Downloading uv $UvVersion"
    $env:UV_INSTALL_DIR = Join-Path $Root 'bin'
    $env:UV_NO_MODIFY_PATH = '1'
    Invoke-RestMethod "https://astral.sh/uv/$UvVersion/install.ps1" | Invoke-Expression
}

Say "Installing Python $PythonVersion"
Run $Uv python install --no-bin --no-registry $PythonVersion
# --seed: pip, which the plugin uses to fetch cellpose 3
Run $Uv venv --quiet --allow-existing --seed --managed-python --python $PythonVersion (Join-Path $Root 'env')

Say "Installing napari and $Spec (PyTorch build: $Torch)"
Run $Uv pip install --python $Python --torch-backend $Torch --upgrade 'napari[all]' $Spec

Run $Python -c "import torch; print('PyTorch', torch.__version__, '| CUDA:', torch.cuda.is_available())"

Say 'Adding shortcuts'
if ($NoDesktop -or $env:NAPARI_CELLPOSESAM_NO_DESKTOP -eq '1') {
    Run $Python -m napari_cellposesam shortcut --no-desktop
} else {
    Run $Python -m napari_cellposesam shortcut
}

if ($Model -eq 'yes') {
    Say 'Downloading the Cellpose-SAM model'
    Run $Python -m napari_cellposesam fetch-cpsam
}

Say 'Done. Start napari-cellposesam from the Start menu or desktop shortcut, or run:'
Write-Host "    & `"$Python`" -m napari_cellposesam launch"
