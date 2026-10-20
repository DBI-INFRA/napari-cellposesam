"""
pick the cellpose release a model needs, and fetch cellpose v3 on demand

napari-cellposesam depends on cellpose v4. The cellpose v3 models (cyto3, nuclei, ...)
run on a private copy of cellpose v3, imported as `_cellpose3` so it cannot clash with
the installed `cellpose`. The copy is made from the pinned PyPI wheel the first time a v3
model is used, once the user agrees.
"""
import ast
import hashlib
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from importlib.metadata import version as _pkg_version
from pathlib import Path

V3_VERSION = '3.1.1.3'
V3_WHEEL = f'cellpose-{V3_VERSION}-py3-none-any.whl'
V3_SHA256 = '0c309f306a8356ba2779054dfd8a1b4a88ea7d6c3388a6fdac99b91b21ce7ff2'
V3_PACKAGE = '_cellpose3'
# the inference modules; the GUI, training and CLI code stay behind
V3_MODULES = {'__init__', 'version', 'models', 'core', 'dynamics', 'transforms', 'utils',
              'metrics', 'plot', 'io', 'resnet_torch', 'segformer'}
# bump when V3_MODULES or the rewrite in _unpack_v3 changes, so old copies are not reused.
# it names the cache folder, which the docs give in full
V3_CACHE_FORMAT = 1
# what cellpose v3 needs on top of the dependencies cellpose v4 brings
V3_DEPS = ['numba']

V3_MODELS = ['cyto3', 'cyto2', 'cyto', 'nuclei', 'tissuenet_cp3', 'livecell_cp3',
             'yeast_PhC_cp3', 'yeast_BF_cp3', 'bact_phase_cp3', 'bact_fluor_cp3',
             'deepbacs_cp3', 'cyto2_cp3']
# the v3 models that come with a size model, for diameter estimation
V3_SIZE_MODELS = ['cyto3', 'cyto2', 'cyto', 'nuclei']

_SUBMODULES = ['models', 'core', 'dynamics', 'transforms', 'utils']
_MANIFEST = 'SHA256SUMS'
# seconds per network read, and retries: offline machines fail in seconds, not minutes
_PIP_OPTIONS = ['--disable-pip-version-check', '--no-input', '--timeout', '10', '--retries', '2']


def cache_dir():
    root = os.environ.get('NAPARI_CELLPOSESAM_CACHE') or Path.home() / '.cellpose' / 'napari-cellposesam'
    # absolute: it goes on sys.path, which must not depend on the working directory
    return Path(root).expanduser().absolute() / f'cellpose-{V3_VERSION}-format{V3_CACHE_FORMAT}'


def probe_model_major(path):
    """Which cellpose release can run the model file at `path`: 3, 4, or None.

    Reads only the state-dict keys (memory-mapped, no pickled code), so it takes
    milliseconds even for the 1 GB CPDINO weights.
    """
    import torch

    try:
        try:
            sd = torch.load(path, map_location='cpu', mmap=True, weights_only=True)
        except RuntimeError:  # pre-zip checkpoints cannot be memory-mapped
            sd = torch.load(path, map_location='cpu', weights_only=True)
    except Exception:
        return None
    if not isinstance(sd, dict):
        return None
    # look the keys up as cellpose does: neither release strips a DataParallel
    # 'module.' prefix before these checks, so such files are rejected by both
    if 'W2' in sd:  # the patch-embedding readout every cellpose v4 network has
        return 4
    out = getattr(sd.get('output.2.weight'), 'shape', None)
    if out:
        # a v3 CPnet; 3 outputs (flows + cellprob) segment, 1 output is a denoise net
        return 3 if out[0] == 3 else None
    return None


def model_major(model_type, custom_model=None):
    """cellpose major version for a built-in model name, or the probed custom model file."""
    if model_type == 'custom':
        if custom_model is None or not Path(custom_model).is_file():
            return None
        return probe_model_major(str(custom_model))
    return 3 if model_type in V3_MODELS else 4


def _cache_complete():
    """the unpacked copy is all there: every file its manifest (written last) lists matches"""
    package = cache_dir() / V3_PACKAGE
    try:
        lines = (package / _MANIFEST).read_text(encoding='utf-8').splitlines()
        return bool(lines) and all(
            hashlib.sha256((package / name).read_bytes()).hexdigest() == digest
            for digest, name in (line.split('  ', 1) for line in lines))
    except (OSError, ValueError):
        return False


def v3_missing():
    """What fetch_v3 still has to do: a subset of ['cellpose', *V3_DEPS], empty if ready."""
    missing = [] if _cache_complete() else ['cellpose']
    return missing + [dep for dep in V3_DEPS if importlib.util.find_spec(dep) is None]


def load(major):
    """Import and return the cellpose package for `major` (3 or 4), with its submodules loaded."""
    if major == 3:
        if v3_missing():
            raise RuntimeError(f'cellpose {V3_VERSION} is not fetched yet')
        if str(cache_dir()) not in sys.path:
            sys.path.append(str(cache_dir()))
        name = V3_PACKAGE
    else:
        name = 'cellpose'
    package = importlib.import_module(name)
    for sub in _SUBMODULES:
        importlib.import_module(f'{name}.{sub}')
    return package


def load_error(major, e):
    """what to tell the user when load(major) raised `e`, with the likely fix"""
    message = f'loading cellpose {major} failed: {e}'
    if major != 3:
        return message
    cache = str(cache_dir())
    reset = f'\ndelete {cache} so the plugin fetches it again'
    name = getattr(e, 'name', None) or ''
    if isinstance(e, ImportError) and name.split('.')[0] == V3_PACKAGE:
        return message + reset  # a module the copy should have
    frames = [f for f, _ in traceback.walk_tb(e.__traceback__)]
    in_cache = [f.f_code.co_filename.startswith(cache) for f in frames]
    if isinstance(e, ImportError):
        if not name and any(in_cache):
            # raised inside a dependency the copy imports, e.g. numba rejecting numpy
            last = max(i for i, c in enumerate(in_cache) if c)
            name = next((f.f_globals.get('__name__', '') for f in frames[last + 1:]
                         if not f.f_code.co_filename.startswith('<')), '')
        if name:
            dep = name.split('.')[0]
            return (f'cellpose 3 could not import {dep}: {e}\nreinstall or upgrade {dep}, keeping '
                    f'numpy as it is: pip install --upgrade {dep} numpy=={_pkg_version("numpy")}')
    if (isinstance(e, SyntaxError) and (e.filename or '').startswith(cache)) or (in_cache and in_cache[-1]):
        return message + reset
    return message


def _pip_error(out):
    """the gist of a failed pip run's output"""
    if re.search(r'NewConnectionError|Failed to establish a new connection|Max retries exceeded'
                 r'|ConnectTimeout|ReadTimeout|timed out|ProxyError|name resolution', out):
        return 'pip could not reach the package index: check the internet connection and proxy settings'
    if re.search(r'Errno 13|Permission denied|Access is denied', out):
        return (f'pip cannot write to this Python environment ({sys.prefix}). install the package with '
                'the tool or account that manages the environment')
    conflict = re.search(r'^\s*(\S+) \S+ depends on numpy', out, flags=re.M)
    if conflict and 'ResolutionImpossible' in out:
        return (f'no {conflict[1]} release supports numpy {_pkg_version("numpy")} yet, the numpy in this '
                f'environment. try again once {conflict[1]} supports it, or use an older numpy')
    errors = [line for line in out.splitlines() if line.startswith('ERROR:')]
    return '\n'.join(errors[-3:]) or out[-400:]


def _pip(*args):
    """run pip in this environment, raising RuntimeError with a readable message on failure"""
    if importlib.util.find_spec('pip') is None:  # e.g. a uv-created venv
        raise RuntimeError(f'this Python environment ({sys.prefix}) has no pip. install it, e.g. with '
                           '`python -m ensurepip` or `uv pip install pip`, then try again')
    # no stdin or prompts: a credential prompt would otherwise hang the fetch for good
    # utf-8 both ways, so non-ASCII output cannot hide pip's error behind a UnicodeDecodeError
    done = subprocess.run([sys.executable, '-m', 'pip', *_PIP_OPTIONS, *args],
                          capture_output=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL,
                          env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    if done.returncode != 0:
        raise RuntimeError(_pip_error(done.stderr + done.stdout))


def fetch_v3():
    """Install V3_DEPS into this environment and unpack cellpose v3 into cache_dir()."""
    missing = v3_missing()
    deps = [dep for dep in missing if dep != 'cellpose']
    if deps:
        # pin numpy: swapping it under a running napari breaks every loaded extension.
        # --no-user: never fall back to the user site, which may not be on sys.path
        _pip('install', '--no-user', '--only-binary=:all:', *deps, f'numpy=={_pkg_version("numpy")}')
    if 'cellpose' in missing:
        _unpack_v3()
    importlib.invalidate_caches()


def _missing_imports(package):
    """modules that the code in `package` imports from itself but that were not extracted"""
    extracted = {p.stem for p in package.glob('*.py')}
    if V3_MODULES - extracted:
        return V3_MODULES - extracted
    # `from . import version_str` takes a name __init__ binds, not a module
    init = ast.parse((package / '__init__.py').read_text(encoding='utf-8'))
    exported = {a.asname or a.name for node in init.body if isinstance(node, ast.ImportFrom) for a in node.names}
    missing = set()
    for path in package.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level:  # the copy is flat: `from . import X` or `from .X import ...`
                module = '.'.join(filter(None, [V3_PACKAGE, node.module]))
            else:
                module = node.module or ''
            if module == V3_PACKAGE:
                missing |= {a.name for a in node.names} - exported - extracted
            elif module.startswith(f'{V3_PACKAGE}.'):
                missing |= {module.split('.')[1]} - extracted
    return missing


def _unpack_v3():
    target = cache_dir() / V3_PACKAGE
    target.parent.mkdir(parents=True, exist_ok=True)
    # best effort: interrupted fetches leave their temporary folders behind
    for stale in target.parent.glob('tmp*'):
        try:
            if time.time() - stale.stat().st_mtime > 3600:
                shutil.rmtree(stale, ignore_errors=True)
        except OSError:
            pass
    with tempfile.TemporaryDirectory(dir=target.parent, ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        # pip honours the user's index, proxy and certificate settings
        _pip('download', '--no-deps', '--only-binary=:all:', '-d', str(tmp), f'cellpose=={V3_VERSION}')
        wheel = tmp / V3_WHEEL
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != V3_SHA256:
            raise RuntimeError(f'{V3_WHEEL} does not match its pinned sha256')
        package = tmp / V3_PACKAGE
        package.mkdir()
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                m = re.fullmatch(r'cellpose/(\w+)\.py', name)
                if m and m[1] in V3_MODULES:
                    src = z.read(name).decode('utf-8')
                    src = re.sub(r'^(\s*)from cellpose(\.| import)', rf'\1from {V3_PACKAGE}\2', src, flags=re.M)
                    # the distribution metadata belongs to the installed cellpose v4
                    src = src.replace('version("cellpose")', f'"{V3_VERSION}"')
                    if re.search(r'^\s*(from|import) cellpose\b', src, flags=re.M):
                        raise RuntimeError(f'{name} still imports the installed cellpose')
                    # bytes, not text: text mode would turn the wheel's CRLF lines into CRCRLF on Windows
                    (package / f'{m[1]}.py').write_bytes(src.encode('utf-8'))
                elif name.endswith('dist-info/LICENSE') or name.endswith('dist-info/licenses/LICENSE'):
                    (package / 'LICENSE').write_bytes(z.read(name))
        missing = _missing_imports(package)
        if missing:
            raise RuntimeError(f'the cellpose {V3_VERSION} copy lacks the modules {", ".join(sorted(missing))}')
        # written last: v3_missing() only accepts a copy whose manifest matches
        sums = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in sorted(package.iterdir())]
        (package / _MANIFEST).write_text('\n'.join(sums) + '\n', encoding='utf-8')
        for attempt in range(5):
            try:
                if target.exists() and not _cache_complete():
                    target.rename(tmp / 'incomplete')  # e.g. a partial copy; removed with tmp
                package.rename(target)  # atomic, so a half-written copy is never importable
                return
            except OSError:
                if _cache_complete():
                    return  # another napari got there first
                if attempt == 4:
                    raise
                time.sleep(0.5)  # e.g. antivirus still scanning the new files on Windows
