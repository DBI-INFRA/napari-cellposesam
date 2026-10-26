"""
command line tools: `python -m napari_cellposesam fetch-cellpose3 | fetch-cpsam | launch | shortcut`
"""
import argparse
import sys

from . import _backends


def _fetch_cellpose3(parser, args):
    try:
        _backends.fetch_v3()
    except Exception as e:
        parser.exit(1, f'fetching cellpose 3 failed: {e}\n')
    missing = _backends.v3_missing()
    if missing:  # e.g. numba installed somewhere this python does not look
        parser.exit(1, f'fetching cellpose 3 finished, but {", ".join(missing)} is still missing\n')
    print(f'cellpose 3 is ready in {_backends.cache_dir()}')
    return 0


def _fetch_cpsam(parser, args):
    from cellpose import models

    try:
        path = models.cache_model_path('cpsam')
    except Exception as e:
        parser.exit(1, f'downloading the Cellpose-SAM model failed: {e}\n')
    print(f'the Cellpose-SAM model is in {path}')
    return 0


def _launch(parser, args):
    from . import _shortcut

    return _shortcut.launch(args.paths)


def _shortcut_command(parser, args):
    from . import _shortcut

    if args.remove:
        for path in _shortcut.remove():
            print(f'removed {path}')
        return 0
    try:
        paths = _shortcut.create(desktop=not args.no_desktop)
    except Exception as e:
        parser.exit(1, f'creating the shortcut failed: {e}\n')
    for path in paths:
        print(f'created {path}')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m napari_cellposesam')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser(
        'fetch-cellpose3',
        help=f'download cellpose {_backends.V3_VERSION} for the Cellpose3 models, and install '
             'numba if it is missing: what napari offers the first time you run one'
    ).set_defaults(run=_fetch_cellpose3)
    commands.add_parser(
        'fetch-cpsam', help='download the Cellpose-SAM model, which cellpose otherwise downloads the first time '
                            'you run it'
    ).set_defaults(run=_fetch_cpsam)
    launch = commands.add_parser('launch', help='start napari with the cellpose widget open')
    launch.add_argument('paths', nargs='*', help='images to open')
    launch.set_defaults(run=_launch)
    shortcut = commands.add_parser(
        'shortcut', help='add an app menu and desktop shortcut that starts napari with the cellpose widget, '
                         'using this Python environment')
    shortcut.add_argument('--no-desktop', action='store_true', help='only add the app menu entry')
    shortcut.add_argument('--remove', action='store_true', help='delete the shortcuts instead')
    shortcut.set_defaults(run=_shortcut_command)
    args = parser.parse_args(argv)
    return args.run(parser, args)


if __name__ == '__main__':
    sys.exit(main())
