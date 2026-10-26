#!/bin/sh
# Install napari and napari-cellposesam (macOS and Linux) into a folder of their own, with the
# PyTorch build that fits this machine's GPU, and add an app shortcut.
#
#   curl -LsSf https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/installer/install.sh | sh
#
# Run it again to update. Pass --uninstall to remove the shortcuts and the install folder.
#
# Environment variables:
#   NAPARI_CELLPOSESAM_HOME   install folder (default: ~/.local/share/napari-cellposesam)
#   NAPARI_CELLPOSESAM_SPEC   what to install (default: napari-cellposesam), e.g. a version pin,
#                             a wheel or a git URL
#   NAPARI_CELLPOSESAM_TORCH  PyTorch build (default: auto), e.g. cpu, cu128 or rocm6.4
#   NAPARI_CELLPOSESAM_NO_DESKTOP=1  add the app menu entry only, no desktop icon
#   NAPARI_CELLPOSESAM_MODEL=1 or 0  download the Cellpose-SAM model now, or not; without it,
#                             the script asks when run in a terminal and skips it otherwise
# SC2218 is a false positive of shellcheck 0.11 here: every function is defined before it runs
# shellcheck disable=SC2218
set -eu

UV_VERSION=0.13.5
PYTHON_VERSION=3.12
ROOT="${NAPARI_CELLPOSESAM_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/napari-cellposesam}"
SPEC="${NAPARI_CELLPOSESAM_SPEC:-napari-cellposesam}"
TORCH="${NAPARI_CELLPOSESAM_TORCH:-auto}"
MODEL="${NAPARI_CELLPOSESAM_MODEL:-}"
# marks a folder this script made, so --uninstall never deletes anything else
MARKER="$ROOT/.napari-cellposesam-install"
UV="$ROOT/bin/uv"
PYTHON="$ROOT/env/bin/python"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 -LsSf "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget --https-only -qO- "$1"
    else
        die "curl or wget is needed to download uv"
    fi
}

# asks on the terminal, which stays readable when the script itself comes through `curl | sh`
ask_model() {
    if [ -z "$MODEL" ] && (: </dev/tty) 2>/dev/null; then
        printf 'Download the Cellpose-SAM model (about 1.2 GB) now? Otherwise napari downloads it\n'
        printf 'the first time you segment. [Y/n] '
        read -r answer </dev/tty || answer=n
        case "$answer" in [nN]*) MODEL=0 ;; *) MODEL=1 ;; esac
    fi
}

# Qt 6 needs libxcb-cursor, which Ubuntu and some other distributions leave out. Without root,
# copy conda-forge's build into Qt's own lib folder, which Qt searches first ($ORIGIN).
# imagecodecs, a plugin dependency, unpacks the zstd-compressed .conda package.
add_xcb_cursor() {
    "$PYTHON" -I - <<'PY'
import ctypes.util
import hashlib
import io
import platform
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import PyQt6

PACKAGES = {
    'x86_64': ('linux-64/xcb-util-cursor-0.1.6-hb03c661_0.conda',
               'c2be9cae786fdb2df7c2387d2db31b285cf90ab3bfabda8fa75a596c3d20fc67'),
    'aarch64': ('linux-aarch64/xcb-util-cursor-0.1.6-he30d5cf_0.conda',
                '2e31eeeac0ad76229a565f1df3a8fb4ea54852a68404a99558adab9c92c0ac4d'),
}
target = Path(PyQt6.__file__).parent / 'Qt6' / 'lib' / 'libxcb-cursor.so.0'
if ctypes.util.find_library('xcb-cursor') or target.exists() or platform.machine() not in PACKAGES:
    sys.exit()
path, sha256 = PACKAGES[platform.machine()]
data = urllib.request.urlopen(f'https://conda.anaconda.org/conda-forge/{path}', timeout=60).read()
if hashlib.sha256(data).hexdigest() != sha256:
    sys.exit('the xcb-util-cursor download does not match its checksum')
import imagecodecs

with zipfile.ZipFile(io.BytesIO(data)) as conda:
    pkg = next(name for name in conda.namelist() if name.startswith('pkg-'))
    tar = tarfile.open(fileobj=io.BytesIO(imagecodecs.zstd_decode(conda.read(pkg))))
lib = next(m for m in tar.getmembers() if m.isfile() and m.name.startswith('lib/libxcb-cursor.so.0'))
target.write_bytes(tar.extractfile(lib).read())
print(f'added {target}, which Qt needs')
PY
}

uninstall() {
    [ -f "$MARKER" ] || die "$ROOT is not a napari-cellposesam install"
    "$PYTHON" -m napari_cellposesam shortcut --remove || true
    rm -rf "$ROOT"
    say "Removed $ROOT"
}

install() {
    if [ -e "$ROOT" ] && [ ! -f "$MARKER" ] && [ -n "$(ls -A "$ROOT")" ]; then
        die "$ROOT exists and was not made by this installer; set NAPARI_CELLPOSESAM_HOME to another folder"
    fi
    ask_model
    mkdir -p "$ROOT"
    touch "$MARKER"

    # python, packages and their cache stay inside $ROOT, so deleting it removes everything
    export UV_PYTHON_INSTALL_DIR="$ROOT/python"
    export UV_CACHE_DIR="$ROOT/cache"
    export UV_NO_CONFIG=1

    uv_found=$("$UV" --version 2>/dev/null | cut -d' ' -f2 || true)
    if [ "$uv_found" != "$UV_VERSION" ]; then
        say "Downloading uv $UV_VERSION"
        uv_installer=$(fetch "https://astral.sh/uv/$UV_VERSION/install.sh")
        printf '%s\n' "$uv_installer" | env UV_INSTALL_DIR="$ROOT/bin" UV_NO_MODIFY_PATH=1 sh -s -- --quiet
    fi

    say "Installing Python $PYTHON_VERSION"
    "$UV" python install --no-bin "$PYTHON_VERSION"
    # --seed: pip, which the plugin uses to fetch cellpose 3
    "$UV" venv --quiet --allow-existing --seed --managed-python --python "$PYTHON_VERSION" "$ROOT/env"

    say "Installing napari and $SPEC (PyTorch build: $TORCH)"
    "$UV" pip install --python "$PYTHON" --torch-backend "$TORCH" --upgrade "napari[all]" "$SPEC"

    "$PYTHON" -c "import torch; print('PyTorch', torch.__version__, '| CUDA:', torch.cuda.is_available(), '| MPS:', torch.backends.mps.is_available())"

    if [ "$(uname)" = Linux ]; then
        add_xcb_cursor || say "Could not add libxcb-cursor; if napari does not open, run: sudo apt install libxcb-cursor0"
    fi

    say "Adding shortcuts"
    if [ "${NAPARI_CELLPOSESAM_NO_DESKTOP:-}" = 1 ]; then
        "$PYTHON" -m napari_cellposesam shortcut --no-desktop
    else
        "$PYTHON" -m napari_cellposesam shortcut
    fi

    if [ "$MODEL" = 1 ]; then
        say "Downloading the Cellpose-SAM model"
        "$PYTHON" -m napari_cellposesam fetch-cpsam
    fi

    say "Done. Start napari-cellposesam from the shortcut, or run:"
    echo "    \"$PYTHON\" -m napari_cellposesam launch"
    echo "To uninstall:"
    echo "    curl -LsSf https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/installer/install.sh | sh -s -- --uninstall"
}

# everything runs from here, so a download cut short by `curl | sh` runs nothing
if [ "${1:-}" = "--uninstall" ]; then
    uninstall
else
    install
fi
