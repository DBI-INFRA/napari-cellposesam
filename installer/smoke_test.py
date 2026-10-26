"""
check that `python -m napari_cellposesam launch` opens napari with the cellpose widget docked

Run with the Python of an install: napari starts, the check runs instead of the event loop,
and the window closes again.
"""
import sys

import napari
from napari_cellposesam import _shortcut


def check(*args, **kwargs):
    viewer = napari.current_viewer()
    docks = list(viewer.window.dock_widgets)
    viewer.close()
    if not any(name.startswith(_shortcut.WIDGET) for name in docks):
        sys.exit(f'the cellpose widget is not docked; the docks are {docks}')
    print(f'napari {napari.__version__} opened with {docks}')


napari.run = check
_shortcut.launch()
