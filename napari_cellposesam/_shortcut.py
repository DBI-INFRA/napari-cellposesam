"""
start napari with the plugin open, and add or remove an app shortcut that does it

The shortcut runs `python -m napari_cellposesam launch` with the Python of this environment,
so it works for any environment, not only for the one the installer scripts make.
"""
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

NAME = 'napari-cellposesam'
PLUGIN = 'napari-cellposesam'
WIDGET = 'cellpose'
COMMENT = 'Cell segmentation with cellpose in napari'


def launch(paths=()):
    """open napari with the cellpose widget docked, and `paths` loaded"""
    if sys.platform == 'win32':
        # torch must load before Qt on Windows: https://github.com/pytorch/pytorch/issues/166628
        import torch  # noqa: F401
    from napari.__main__ import main as napari_main

    sys.argv = ['napari', '-w', PLUGIN, WIDGET, '--', *paths]
    return napari_main()


def _icon(suffix):
    """the cellpose logo that the installed cellpose ships, as .png or .ico"""
    return Path(str(files('cellpose') / 'logo' / ('logo.png' if suffix == '.png' else 'cellpose.ico')))


def _command(python):
    return [str(python), '-m', 'napari_cellposesam', 'launch']


def _windows_folder(name):
    """a Windows shell folder such as Desktop or Programs, wherever the user has moved it"""
    out = subprocess.run(['powershell', '-NoProfile', '-Command', f"[Environment]::GetFolderPath('{name}')"],
                         capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def _windows(desktop):
    folders = [_windows_folder('Programs')] + ([_windows_folder('Desktop')] if desktop else [])
    return [folder / f'{NAME}.lnk' for folder in folders]


def _macos(home, desktop):
    app = home / 'Applications' / f'{NAME}.app'
    return [app] + ([home / 'Desktop' / f'{NAME}.app'] if desktop else [])


def _linux(home, desktop):
    data = Path(os.environ.get('XDG_DATA_HOME') or home / '.local' / 'share')
    entry = data / 'applications' / f'{NAME}.desktop'
    return [entry] + ([home / 'Desktop' / f'{NAME}.desktop'] if desktop else [])


def shortcut_paths(desktop=True, home=None):
    """where the shortcuts go on this platform: the app menu first, then the desktop"""
    home = Path(home) if home else Path.home()
    if sys.platform == 'win32':
        return _windows(desktop)
    if sys.platform == 'darwin':
        return _macos(home, desktop)
    return _linux(home, desktop)


def _write_lnk(path, python):
    # pythonw: no console window behind napari
    pythonw = Path(python).with_name('pythonw.exe')
    target, *args = _command(pythonw if pythonw.exists() else python)
    path.parent.mkdir(parents=True, exist_ok=True)
    # paths reach PowerShell through the environment, so no quoting can break them
    script = ('$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:NCS_LNK); '
              '$s.TargetPath = $env:NCS_TARGET; $s.Arguments = $env:NCS_ARGS; '
              '$s.WorkingDirectory = $env:USERPROFILE; $s.IconLocation = $env:NCS_ICON; '
              '$s.Description = $env:NCS_COMMENT; $s.Save()')
    env = {**os.environ, 'NCS_LNK': str(path), 'NCS_TARGET': target, 'NCS_ARGS': subprocess.list2cmdline(args),
           'NCS_ICON': str(_icon('.ico')), 'NCS_COMMENT': COMMENT}
    subprocess.run(['powershell', '-NoProfile', '-Command', script], env=env, check=True)


def _write_app(app, python):
    contents = app / 'Contents'
    (contents / 'MacOS').mkdir(parents=True, exist_ok=True)
    (contents / 'Resources').mkdir(exist_ok=True)
    launcher = contents / 'MacOS' / NAME
    launcher.write_text(f'#!/bin/sh\nexec {shlex.join(_command(python))} "$@"\n')
    launcher.chmod(0o755)
    with open(contents / 'Info.plist', 'wb') as f:
        plistlib.dump({'CFBundleName': NAME, 'CFBundleDisplayName': NAME, 'CFBundleExecutable': NAME,
                       'CFBundleIdentifier': 'io.github.jeskowagner.napari-cellposesam',
                       'CFBundlePackageType': 'APPL', 'CFBundleIconFile': 'icon.icns',
                       'NSHighResolutionCapable': True}, f)
    # sips ships with macOS; without the .icns the app still works, with a generic icon
    subprocess.run(['sips', '-s', 'format', 'icns', str(_icon('.png')), '--out',
                    str(contents / 'Resources' / 'icon.icns')], capture_output=True)


def _write_desktop_entry(path, python):
    path.parent.mkdir(parents=True, exist_ok=True)
    exec_line = ' '.join(f'"{part}"' for part in _command(python))
    path.write_text('[Desktop Entry]\nType=Application\n'
                    f'Name={NAME}\nComment={COMMENT}\nExec={exec_line} %F\nIcon={_icon(".png")}\n'
                    'Terminal=false\nStartupWMClass=napari\nCategories=Science;Graphics;\n')
    path.chmod(0o755)
    # GNOME only starts desktop-folder launchers that are marked trusted
    if shutil.which('gio'):
        subprocess.run(['gio', 'set', str(path), 'metadata::trusted', 'true'], capture_output=True)


def create(python=sys.executable, desktop=True, home=None):
    """add shortcuts that start napari with this plugin open; returns their paths"""
    paths = shortcut_paths(desktop, home)
    for path in paths:
        if sys.platform == 'win32':
            _write_lnk(path, python)
        elif sys.platform == 'darwin':
            if path == paths[0]:
                _write_app(path, python)
            else:  # the desktop gets a link to the app, so the Dock and Launchpad see one app
                path.parent.mkdir(parents=True, exist_ok=True)
                path.unlink(missing_ok=True)
                path.symlink_to(paths[0])
        else:
            _write_desktop_entry(path, python)
    return paths


def remove(home=None):
    """delete the shortcuts that create() makes; returns the paths that existed"""
    removed = []
    for path in shortcut_paths(desktop=True, home=home):
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            continue
        removed.append(path)
    return removed
