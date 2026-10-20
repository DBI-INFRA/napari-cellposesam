"""
command line tools: `python -m napari_cellposesam fetch-cellpose3`
"""
import argparse
import sys

from . import _backends


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m napari_cellposesam')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser(
        'fetch-cellpose3',
        help=f'download cellpose {_backends.V3_VERSION} for the Cellpose3 models, and install '
             'numba if it is missing: what napari offers the first time you run one')
    parser.parse_args(argv)

    try:
        _backends.fetch_v3()
    except Exception as e:
        parser.exit(1, f'fetching cellpose 3 failed: {e}\n')
    missing = _backends.v3_missing()
    if missing:  # e.g. numba installed somewhere this python does not look
        parser.exit(1, f'fetching cellpose 3 finished, but {", ".join(missing)} is still missing\n')
    print(f'cellpose 3 is ready in {_backends.cache_dir()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
