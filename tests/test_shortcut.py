import plistlib
import sys

import pytest
from napari_cellposesam import _shortcut
from napari_cellposesam.__main__ import main

unix_only = pytest.mark.skipif(sys.platform == 'win32', reason='makes .app bundles or .desktop entries')


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.delenv('XDG_DATA_HOME', raising=False)
    return tmp_path


def test_icons_ship_with_cellpose():
    assert _shortcut._icon('.png').is_file()
    assert _shortcut._icon('.ico').is_file()


@unix_only
@pytest.mark.parametrize('desktop', [True, False])
def test_create_and_remove(home, desktop):
    paths = _shortcut.create(python='/opt/my env/bin/python', desktop=desktop)
    assert paths == _shortcut.shortcut_paths(desktop)
    assert len(paths) == (2 if desktop else 1)
    assert all(p.exists() and p.is_relative_to(home) for p in paths)

    assert _shortcut.remove() == paths
    assert not any(p.exists() or p.is_symlink() for p in paths)
    assert _shortcut.remove() == []


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS app bundle')
def test_macos_app(home):
    app, desktop = _shortcut.create(python='/opt/my env/bin/python')
    contents = app / 'Contents'
    with open(contents / 'Info.plist', 'rb') as f:
        info = plistlib.load(f)
    launcher = contents / 'MacOS' / info['CFBundleExecutable']
    assert "exec '/opt/my env/bin/python' -m napari_cellposesam launch" in launcher.read_text()
    assert launcher.stat().st_mode & 0o111
    assert (contents / 'Resources' / info['CFBundleIconFile']).is_file()
    assert desktop.resolve() == app.resolve()


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='freedesktop entry')
def test_linux_desktop_entry(home):
    entry, _ = _shortcut.create(python='/opt/my env/bin/python')
    assert entry == home / '.local' / 'share' / 'applications' / 'napari-cellposesam.desktop'
    text = entry.read_text()
    assert 'Exec="/opt/my env/bin/python" "-m" "napari_cellposesam" "launch" %F' in text
    assert f'Icon={_shortcut._icon(".png")}' in text


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows .lnk')
def test_windows_lnk(monkeypatch, tmp_path):
    monkeypatch.setattr(_shortcut, '_windows_folder', lambda name: tmp_path / name)
    menu, desktop = _shortcut.create()
    assert menu == tmp_path / 'Programs' / 'napari-cellposesam.lnk'
    assert menu.is_file() and desktop.is_file()
    assert _shortcut.remove() == [menu, desktop]


def test_cli_shortcut(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(_shortcut, 'create', lambda desktop: calls.append(desktop) or ['a.app'])
    monkeypatch.setattr(_shortcut, 'remove', lambda: ['a.app'])
    assert main(['shortcut']) == 0
    assert main(['shortcut', '--no-desktop']) == 0
    assert calls == [True, False]
    assert main(['shortcut', '--remove']) == 0
    assert capsys.readouterr().out.splitlines() == ['created a.app', 'created a.app', 'removed a.app']


def test_cli_shortcut_failure(monkeypatch, capsys):
    def fail(desktop):
        raise OSError('read-only file system')

    monkeypatch.setattr(_shortcut, 'create', fail)
    with pytest.raises(SystemExit) as exit_:
        main(['shortcut'])
    assert exit_.value.code == 1
    assert 'read-only file system' in capsys.readouterr().err


def test_launch_opens_the_widget(monkeypatch):
    import napari.__main__

    argv = []
    monkeypatch.setattr(napari.__main__, 'main', lambda: argv.extend(sys.argv))
    monkeypatch.setattr(sys, 'argv', sys.argv[:])
    main(['launch', 'a.tif', 'b.tif'])
    assert argv == ['napari', '-w', 'napari-cellposesam', 'cellpose', '--', 'a.tif', 'b.tif']


def test_cli_fetch_cpsam(monkeypatch, capsys):
    from cellpose import models

    monkeypatch.setattr(models, 'cache_model_path', lambda name: f'/models/{name}')
    assert main(['fetch-cpsam']) == 0
    assert capsys.readouterr().out == 'the Cellpose-SAM model is in /models/cpsam\n'

    def offline(name):
        raise OSError('no network')

    monkeypatch.setattr(models, 'cache_model_path', offline)
    with pytest.raises(SystemExit) as exit_:
        main(['fetch-cpsam'])
    assert exit_.value.code == 1
    assert 'no network' in capsys.readouterr().err
