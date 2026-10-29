"""
check that the installed napari opens with the napari-cellposesam widget docked, as the shortcut starts it

Run with the Python of an install: napari starts, the check runs instead of the event loop,
and the window closes again.
"""

import sys

import napari
import napari_launcher

PLUGIN = 'napari-cellposesam'
WIDGET = 'cellpose'


def check(*args, **kwargs):
    viewer = napari.current_viewer()
    docks = list(viewer.window.dock_widgets)
    viewer.close()
    if not docks or (WIDGET and WIDGET != '__all__' and not any(name.startswith(WIDGET) for name in docks)):
        sys.exit(f'the {WIDGET or PLUGIN} widget is not docked; the docks are {docks}')
    print(f'napari {napari.__version__} opened with {docks}')


napari.run = check
napari_launcher.launch([(PLUGIN, WIDGET) if WIDGET else (PLUGIN,)])
