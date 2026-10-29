# Install napari and napari-cellposesam (Windows) into a folder of their own,
# with the PyTorch build that fits this machine's GPU, and add Start menu and desktop shortcuts.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.ps1 | iex"
#
# Run it again to update. To uninstall:
#
#   powershell -ExecutionPolicy ByPass -c "& ([scriptblock]::Create((irm https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.ps1))) -Uninstall"
#
# or run a saved copy of this script with -Uninstall.
#
# Environment variables:
#   NAPARI_CELLPOSESAM_HOME      install folder (default: %LOCALAPPDATA%\napari-cellposesam); -Root takes precedence
#   NAPARI_CELLPOSESAM_SPEC      what to install (default: napari-cellposesam),
#                       e.g. a version pin, a wheel or a git URL
#   NAPARI_CELLPOSESAM_TORCH     PyTorch build (default: auto), e.g. cpu or cu128
#   NAPARI_CELLPOSESAM_NO_DESKTOP=1  add the Start menu entry only, no desktop shortcut (or -NoDesktop)
#   NAPARI_CELLPOSESAM_EXTRA_SETUP=1 or 0  run the extra setup step now, or not (or -ExtraSetup yes/no);
#                       without it, the script asks when run in a console and skips it otherwise
#   NAPARI_CELLPOSESAM_LAUNCHER  what provides the shortcuts (default: napari-launcher>=0.1,<0.2)
#
# -PauseOnError keeps the window open after a failure, for runs from the setup .exe
#
# Made with napari-installer-template; update with `copier update -a installer/.copier-answers.yml`.
param([string]$Root, [switch]$Uninstall, [switch]$NoDesktop, [switch]$PauseOnError,
      [ValidateSet('ask', 'yes', 'no')][string]$ExtraSetup = 'ask')

# Windows PowerShell started from PowerShell 7 inherits its module path, then loads PowerShell 7's
# modules and fails ("The member ... is already present"); keep only its own paths
if ($PSVersionTable.PSEdition -eq 'Desktop') {
    $env:PSModulePath = (($env:PSModulePath -split ';') -notmatch '\\PowerShell\\') -join ';'
}

$ErrorActionPreference = 'Stop'
function Exit-Install($code) {
    try { Stop-Transcript | Out-Null } catch {}
    if ($PauseOnError) { Read-Host 'Press Enter to close' }
    exit $code
}
trap {
    Write-Host "error: $_" -ForegroundColor Red
    Exit-Install 1
}
# Invoke-WebRequest is many times slower with its progress bar on
$ProgressPreference = 'SilentlyContinue'
# GitHub needs TLS 1.2, which older .NET Framework versions leave off
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$UvVersion = '0.13.6'
$UvSha256 = 'a2a8820d5eea32f08ef467ef3b7f66883a9b076d5737a2fc2fbb5f458d1bb50f'
$PythonVersion = '3.12'
if (-not $Root) { $Root = if ($env:NAPARI_CELLPOSESAM_HOME) { $env:NAPARI_CELLPOSESAM_HOME } else { Join-Path $env:LOCALAPPDATA 'napari-cellposesam' } }
# absolute, as .NET methods take it
$Root = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Root)
# marks a folder this script made, so uninstalling never deletes anything else
$MarkerName = '.napari-cellposesam-install'
$Marker = Join-Path $Root $MarkerName
$Uv = Join-Path $Root 'bin\uv.exe'
$Python = Join-Path $Root 'env\Scripts\python.exe'
$Step = Join-Path $Root 'install-step.py'

# the rest of the work, shared with install.sh, runs in the environment's Python
$StepCode = @'
"""
The work of install.sh and install.ps1 once uv, Python and the environment exist. Both scripts include
this file, write it into the install folder and run it with the environment's Python:

    python -I -u install-step.py install [--no-desktop] [--extra-setup ask|yes|no]
    python -I -u install-step.py uninstall

It uses only the standard library, and stays ASCII because install.ps1 does.
"""

import argparse
import ctypes.util
import json
import os
import subprocess
import sys
import sysconfig
import traceback
from pathlib import Path

# the template's answers, filled in by copier
CONFIG = r"""{
    "app_name": "napari-cellposesam",
    "branch": "main",
    "comment": "Cell segmentation with cellpose in napari",
    "dist": "napari-cellposesam",
    "env": "NAPARI_CELLPOSESAM",
    "extra_setup_command": "-m napari_cellposesam fetch-cpsam",
    "extra_setup_desc": "download the Cellpose-SAM model (about 1.2 GB)",
    "launcher_spec": "napari-launcher\u003e=0.1,\u003c0.2",
    "plugin": "napari-cellposesam",
    "python_version": "3.12",
    "repo": "DBI-INFRA/napari-cellposesam",
    "shortcut_icon": "cellpose:logo/logo.png",
    "torch": true,
    "widget": "cellpose"
}"""

# conda-forge's build of libxcb-cursor for each machine, and its sha256
XCB_CURSOR = {
    'x86_64': (
        'linux-64/xcb-util-cursor-0.1.6-hb03c661_0.conda',
        'c2be9cae786fdb2df7c2387d2db31b285cf90ab3bfabda8fa75a596c3d20fc67',
    ),
    'aarch64': (
        'linux-aarch64/xcb-util-cursor-0.1.6-he30d5cf_0.conda',
        '2e31eeeac0ad76229a565f1df3a8fb4ea54852a68404a99558adab9c92c0ac4d',
    ),
}

# which PyTorch build the install got
TORCH_CHECK = (
    "import torch; print('PyTorch', torch.__version__, '| CUDA:', torch.cuda.is_available(), "
    "'| MPS:', torch.backends.mps.is_available())"
)

WINDOWS = sys.platform == 'win32'
# on Windows, messages also go to install.log, which the setup's error message points to
LOG = None
COLOUR = not WINDOWS


class Failed(Exception):
    """stops the install, with a message for the user"""


def show(text, colour='', stream=None):
    stream = stream or sys.stdout
    stream.write(f'\033[{colour}m{text}\033[0m\n' if colour and COLOUR else f'{text}\n')
    stream.flush()
    if LOG:
        with open(LOG, 'a', encoding='utf-8') as log:
            log.write(f'{text}\n')


def say(text):
    show(f'==> {text}', '36' if WINDOWS else '1')


def warn(text):
    if WINDOWS:
        show(text, '33')
    else:
        say(text)


def windows_colour():
    """turns on colour codes in the console, which Windows PowerShell 5.1 leaves off"""
    kernel32 = ctypes.windll.kernel32
    handle, mode = kernel32.GetStdHandle(-11), ctypes.c_uint32()
    return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)) and kernel32.SetConsoleMode(handle, mode.value | 4))


def utf8_output(environ):
    """
    UTF-8 output from this step and the Pythons it runs, as from uv. On Windows, Python otherwise writes
    the ANSI code page into a pipe or file, such as a CI log, which garbles names that are not ASCII.
    """
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    environ['PYTHONIOENCODING'] = 'utf-8'


def run(*command):
    """runs a command and stops the install if it fails"""
    try:
        code = subprocess.run(command, check=False).returncode
    except OSError as e:
        raise Failed(f'could not run {command[0]}: {e.strerror or e}') from None
    if code:
        raise Failed(f'{command[0]} failed with exit code {code}')


def setting(config, environ, name, default=''):
    """the <ENV>_<NAME> environment variable; empty counts as unset"""
    return environ.get(f'{config["env"]}_{name}') or default


def install_command(config, environ, uv, python):
    spec = setting(config, environ, 'SPEC', config['dist'])
    launcher = setting(config, environ, 'LAUNCHER', config['launcher_spec'])
    torch = ['--torch-backend', setting(config, environ, 'TORCH', 'auto')] if config['torch'] else []
    return [str(uv), 'pip', 'install', '--python', str(python), *torch, '--upgrade', 'napari[all]', spec, launcher]


def shortcut_command(config, environ, python, no_desktop=False):
    command = [str(python), '-m', 'napari_launcher', 'shortcut', 'add']
    command += ['--name', config['app_name'], '--comment', config['comment']]
    if config['shortcut_icon']:
        command += ['--icon', config['shortcut_icon']]
    if no_desktop or setting(config, environ, 'NO_DESKTOP') == '1':
        command.append('--no-desktop')
    # the plugin and widget to dock, as napari-launcher's -w takes them
    return command + ['-w', config['plugin']] + ([config['widget']] if config['widget'] else [])


# where questions go and answers come from: in `curl | sh`, standard input is the script itself
TERMINAL = ('CONIN$', 'CONOUT$') if WINDOWS else ('/dev/tty', '/dev/tty')


def extra_setup_title(config):
    """the extra setup step's description, with a capital letter, to start a sentence"""
    desc = config['extra_setup_desc']
    return desc[:1].upper() + desc[1:]


def wants_extra_setup(config, environ, choice='ask', terminal=TERMINAL):
    """
    Whether to run the extra setup step: <ENV>_EXTRA_SETUP=1 or 0 decides, then -ExtraSetup yes or no from
    the setup, then the user's answer. Without a terminal to ask on, the step does not run.
    """
    value = setting(config, environ, 'EXTRA_SETUP')
    if value in ('0', '1'):
        return value == '1'
    if choice != 'ask':
        return choice == 'yes'
    try:
        with (
            open(terminal[0], encoding='utf-8', errors='replace') as answers,
            open(terminal[1], 'w', encoding='utf-8') as questions,
        ):
            questions.write(f'{extra_setup_title(config)} now? [Y/n] ')
            questions.flush()
            answer = answers.readline()
    except OSError:
        return False
    # Enter alone is yes; the end of the input, as from a closed terminal, is no
    return bool(answer) and not answer.strip().lower().startswith('n')


def xcb_cursor_folder(site_packages, find_library=ctypes.util.find_library):
    """
    Qt's own library folder if libxcb-cursor has to go there, otherwise None. Qt 6 needs the library,
    which Ubuntu and some other distributions leave out, and Qt looks in its own folder first ($ORIGIN).
    """
    folder = Path(site_packages) / 'PyQt6' / 'Qt6' / 'lib'
    if find_library('xcb-cursor') or not folder.is_dir() or (folder / 'libxcb-cursor.so.0').exists():
        return None
    return folder


def add_xcb_cursor(config, uv):
    folder = xcb_cursor_folder(sysconfig.get_path('purelib'))
    if folder is None:
        return
    # zstandard unpacks the .conda package, in a throwaway environment
    command = [str(uv), 'run', '--quiet', '--no-project', '--isolated', '--python', config['python_version']]
    command += ['--with', 'zstandard', 'python', '-I', str(Path(__file__).resolve()), 'xcb-cursor', str(folder)]
    if subprocess.run(command, check=False).returncode:
        warn('Could not add libxcb-cursor; if napari does not open, run: sudo apt install libxcb-cursor0')


def fetch_xcb_cursor(folder):
    """copies conda-forge's libxcb-cursor into folder, in the environment that add_xcb_cursor makes"""
    import hashlib
    import io
    import platform
    import tarfile
    import urllib.request
    import zipfile

    import zstandard

    if platform.machine() not in XCB_CURSOR:
        sys.exit(f'no libxcb-cursor build for {platform.machine()}')
    path, sha256 = XCB_CURSOR[platform.machine()]
    data = urllib.request.urlopen(f'https://conda.anaconda.org/conda-forge/{path}', timeout=60).read()
    if hashlib.sha256(data).hexdigest() != sha256:
        sys.exit('the xcb-util-cursor download does not match its checksum')
    with zipfile.ZipFile(io.BytesIO(data)) as conda:
        pkg = next(name for name in conda.namelist() if name.startswith('pkg-'))
        payload = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(conda.read(pkg))).read()
    target = Path(folder) / 'libxcb-cursor.so.0'
    with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
        lib = next(m for m in tar.getmembers() if m.isfile() and m.name.startswith('lib/libxcb-cursor.so.0'))
        target.write_bytes(tar.extractfile(lib).read())
    print(f'added {target}, which Qt needs')


def summary(config, python):
    """the closing lines: how to start the app and, on macOS and Linux, how to uninstall it"""
    quote = "'" if WINDOWS else '"'
    widget = f' {quote}{config["widget"]}{quote}' if config['widget'] else ''
    if WINDOWS:
        return [
            f'Done. Start {config["app_name"]} from the Start menu or desktop shortcut, or run:',
            f'    & "{python}" -m napari_launcher launch -w {config["plugin"]}{widget}',
        ]
    url = f'https://raw.githubusercontent.com/{config["repo"]}/{config["branch"]}/installer/install.sh'
    return [
        f'Done. Start {config["app_name"]} from the shortcut, or run:',
        f'    "{python}" -m napari_launcher launch -w {config["plugin"]}{widget}',
        'To uninstall:',
        f'    curl -LsSf {url} | sh -s -- --uninstall',
    ]


def install(config, root, environ, no_desktop=False, extra_setup='ask'):
    python = root / 'env' / ('Scripts/python.exe' if WINDOWS else 'bin/python')
    uv = root / 'bin' / ('uv.exe' if WINDOWS else 'uv')
    extra_setup_now = bool(config['extra_setup_command']) and wants_extra_setup(config, environ, extra_setup)

    spec = setting(config, environ, 'SPEC', config['dist'])
    if config['torch']:
        say(f'Installing napari and {spec} (PyTorch build: {setting(config, environ, "TORCH", "auto")})')
    else:
        say(f'Installing napari and {spec}')
    run(*install_command(config, environ, uv, python))
    if config['torch']:
        run(str(python), '-c', TORCH_CHECK)

    if sys.platform.startswith('linux'):
        add_xcb_cursor(config, uv)

    say('Adding shortcuts')
    if subprocess.run(shortcut_command(config, environ, python, no_desktop), check=False).returncode:
        raise Failed(
            f'napari and {config["dist"]} are installed, but the shortcuts are not. If the error above says a '
            'file was not made by napari-launcher, rename or delete that file, then run this again. If it says '
            f'a plugin or widget is not there, report it at https://github.com/{config["repo"]}/issues.'
        )

    if extra_setup_now:
        say(extra_setup_title(config))
        run(str(python), *config['extra_setup_command'].split())

    first, *rest = summary(config, python)
    say(first)
    for line in rest:
        show(line)


def uninstall(config, root):
    python = root / 'env' / ('Scripts/python.exe' if WINDOWS else 'bin/python')
    command = [str(python), '-m', 'napari_launcher', 'shortcut', 'remove', '--name', config['app_name']]
    if subprocess.run(command, check=False).returncode:
        name = config['app_name']
        warn(f'The shortcuts were not removed (see above); delete any {name} shortcuts that are left by hand.')
        return 1
    return 0


def main(argv=None):
    global LOG, COLOUR
    parser = argparse.ArgumentParser(prog='install-step.py')
    commands = parser.add_subparsers(dest='command', required=True)
    install_args = commands.add_parser('install')
    install_args.add_argument('--no-desktop', action='store_true')
    install_args.add_argument('--extra-setup', choices=['ask', 'yes', 'no'], default='ask')
    commands.add_parser('uninstall')
    commands.add_parser('xcb-cursor').add_argument('folder')
    args = parser.parse_args(argv)
    if args.command == 'xcb-cursor':
        fetch_xcb_cursor(args.folder)
        return 0

    utf8_output(os.environ)
    root = Path(__file__).resolve().parent
    config = json.loads(CONFIG)
    if WINDOWS:
        COLOUR = windows_colour()
        LOG = root / 'install.log' if args.command == 'install' else None
    try:
        if args.command == 'uninstall':
            return uninstall(config, root)
        install(config, root, os.environ, args.no_desktop, args.extra_setup)
    except Failed as e:
        show(f'error: {e}', '31' if WINDOWS else '', sys.stderr)
        return 1
    except Exception:
        if LOG:
            with open(LOG, 'a', encoding='utf-8') as log:
                log.write(traceback.format_exc())
        raise
    return 0


if __name__ == '__main__':
    sys.exit(main())
'@

function Say($message) { Write-Host "==> $message" -ForegroundColor Cyan }

# native commands do not stop the script on failure by themselves
function Run {
    & $args[0] @($args | Select-Object -Skip 1)
    if ($LASTEXITCODE -ne 0) { throw "$($args[0]) failed with exit code $LASTEXITCODE" }
}

if ($Uninstall) {
    if (-not (Test-Path -LiteralPath $Marker)) { throw "$Root is not a napari-cellposesam install" }
    # removes the shortcuts, or says to delete them by hand
    if (Test-Path -LiteralPath $Python) {
        [IO.File]::WriteAllText($Step, $StepCode)
        & $Python -I -u $Step uninstall
    }
    # the marker goes last, so an uninstall that stops part-way can run again
    try {
        Get-ChildItem -LiteralPath $Root -Force | Where-Object { $_.Name -ne $MarkerName } | Remove-Item -Recurse -Force
    } catch {
        throw "could not delete everything in $Root ($_). Close napari, then uninstall again."
    }
    Remove-Item -LiteralPath $Marker -Force
    Remove-Item -LiteralPath $Root -Force
    Say "Removed $Root"
    return
}

if ((Test-Path -LiteralPath $Root) -and -not (Test-Path -LiteralPath $Marker) -and
    (Get-ChildItem -LiteralPath $Root -Force | Select-Object -First 1)) {
    throw "$Root exists and was not made by this installer; set NAPARI_CELLPOSESAM_HOME to another folder"
}

[void][IO.Directory]::CreateDirectory($Root)
[IO.File]::WriteAllText($Marker, '')
# what the script says, and any error, also goes to install.log; uv's own output does not
Start-Transcript -LiteralPath (Join-Path $Root 'install.log') | Out-Null

# python, packages and their cache stay inside $Root, so deleting it removes everything
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root 'python'
$env:UV_CACHE_DIR = Join-Path $Root 'cache'
$env:UV_NO_CONFIG = '1'

if (-not (Test-Path -LiteralPath $Uv) -or ((& $Uv --version) -split ' ')[1] -ne $UvVersion) {
    Say "Downloading uv $UvVersion"
    # the x64 build, which Windows on Arm also runs
    $zip = Join-Path $Root 'uv.zip'
    Invoke-WebRequest -UseBasicParsing -OutFile $zip `
        "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
    if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $UvSha256) {
        throw 'the uv download does not match its checksum'
    }
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $Root 'bin') -Force
    Remove-Item -LiteralPath $zip
}

Say "Installing Python $PythonVersion"
# --no-bin, --no-registry: Python stays private to this install, off PATH and the py launcher
Run $Uv python install --no-bin --no-registry $PythonVersion
# --seed: pip, which napari's plugin manager installs other plugins with
Run $Uv venv --quiet --allow-existing --seed --managed-python --python $PythonVersion (Join-Path $Root 'env')

# the packages, the shortcuts, the extra setup step and the closing message; the step writes its
# own messages to install.log, so the transcript stops first and leaves the file to it
$StepArgs = @()
if ($NoDesktop) { $StepArgs += '--no-desktop' }
if ($ExtraSetup -ne 'ask') { $StepArgs += @('--extra-setup', $ExtraSetup) }
Stop-Transcript | Out-Null
[IO.File]::WriteAllText($Step, $StepCode)
& $Python -I -u $Step install @StepArgs
$code = $LASTEXITCODE
Remove-Item -LiteralPath $Step
if ($code -ne 0) { Exit-Install $code }
