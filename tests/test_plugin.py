import logging
import os
from math import isclose
from typing import Callable

import napari
import numpy as np
import pytest
import torch
from napari_cellposesam import _backends
from napari_cellposesam._dock_widget import _anisotropy

PLUGIN_NAME = "napari-cellposesam"
WIDGET_NAME = "cellpose"

@pytest.fixture(autouse=True)
def force_cpu_on_CI(monkeypatch):
    # https://github.com/pytorch/pytorch/issues/75912
    if os.getenv('CI'):
        monkeypatch.setattr("cellpose.core.use_gpu", lambda *_, **__: False)


@pytest.fixture(scope='session')
def _fetched_cellpose3(tmp_path_factory):
    """cellpose v3, fetched once per session into a cache of its own"""
    with pytest.MonkeyPatch.context() as mp:
        from napari_cellposesam.__main__ import main

        mp.setenv('NAPARI_CELLPOSESAM_CACHE', str(tmp_path_factory.mktemp('cache')))
        assert main(['fetch-cellpose3']) == 0
        yield _backends.load(3)


@pytest.fixture
def cellpose3(_fetched_cellpose3, monkeypatch):
    if os.getenv('CI'):
        monkeypatch.setattr(_fetched_cellpose3.core, 'use_gpu', lambda *_, **__: False)
    return _fetched_cellpose3


@pytest.fixture
def viewer_widget(make_napari_viewer: Callable[..., napari.Viewer]):
    viewer = make_napari_viewer()
    _, widget = viewer.window.add_plugin_dock_widget(
        plugin_name=PLUGIN_NAME, widget_name=WIDGET_NAME
    )
    return viewer, widget


@pytest.fixture
def accept_prompts(monkeypatch):
    """click the accept button of every QMessageBox; returns the texts shown"""
    from qtpy.QtWidgets import QMessageBox

    prompts = []

    def accept(box):
        prompts.append(box.text())
        next(b for b in box.buttons() if box.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole).click()

    monkeypatch.setattr(QMessageBox, 'exec', accept)
    return prompts


# pin the models: the mask counts are model-specific, and which built-in model
# cellpose defaults to changes between releases
@pytest.mark.parametrize('model_type, n_masks', [('cpsam', 37), ('cyto3', 41)])
def test_basic_function(qtbot, viewer_widget, request, model_type, n_masks):
    if model_type in _backends.V3_MODELS:
        request.getfixturevalue('cellpose3')
    viewer, widget = viewer_widget
    from qtpy.QtWidgets import QDockWidget

    # the widget sits in a dock of the viewer; Window.dock_widgets is new in napari 0.7
    dock = widget.native
    while dock is not None and not isinstance(dock, QDockWidget):
        dock = dock.parentWidget()
    assert dock is not None

    viewer.open_sample(PLUGIN_NAME, 'rgb_2D')

    widget.model_type.value = model_type
    widget()  # run segmentation with all other parameters left at their defaults

    def check_widget():
        assert widget.cellpose_layers

    qtbot.waitUntil(check_widget, timeout=360_000)
    assert len(viewer.layers) == 5
    assert "cp_masks" in viewer.layers[-1].name
    assert viewer.layers[-1].data.max() == n_masks

    # recompute from the stored flows, with the cellpose that made them
    widget.model_type.value = 'cyto3' if model_type == 'cpsam' else 'cpsam'
    masks = viewer.layers[-1]
    old = masks.data
    widget.compute_masks_button.native.click()
    qtbot.waitUntil(lambda: masks.data is not old, timeout=60_000)
    assert masks.data.shape == old.shape
    assert masks.data.max() > 0


@pytest.mark.parametrize('model_type', ['cpsam', 'cyto3'])
def test_recompute_masks_matches_run(qtbot, viewer_widget, request, model_type):
    """recomputing with new thresholds gives what a full run with them gives"""
    if model_type in _backends.V3_MODELS:
        request.getfixturevalue('cellpose3')
    viewer, widget = viewer_widget
    viewer.open_sample(PLUGIN_NAME, 'rgb_2D')
    widget.model_type.value = model_type

    def run():
        old = widget.masks_orig if hasattr(widget, 'masks_orig') else None
        widget()
        qtbot.waitUntil(lambda: getattr(widget, 'masks_orig', None) is not old, timeout=360_000)
        return viewer.layers[-1].data

    default = run()
    # stricter on both counts, so fewer masks than the defaults give
    widget.flow_threshold.value = 0.1
    widget.min_size.value = 900

    old = widget.masks_orig
    widget.compute_masks_button.native.click()
    qtbot.waitUntil(lambda: widget.masks_orig is not old, timeout=60_000)
    recomputed = viewer.layers[-1].data.copy()
    assert 0 < recomputed.max() < default.max()

    np.testing.assert_array_equal(recomputed, run())


def test_compute_diameter(qtbot, viewer_widget, cellpose3):
    viewer, widget = viewer_widget
    viewer.open_sample(PLUGIN_NAME, 'rgb_2D')
    widget.model_type.value = 'cyto3'  # diameter estimation is cellpose v3 only

    assert widget.diameter.value == "30"
    with qtbot.waitSignal(widget.diameter.changed, timeout=60_000) as blocker:
        widget.compute_diameter_button.changed(None)

    # local on Windows with CPU/GPU 46.0
    assert isclose(float(widget.diameter.value), 46, abs_tol=0.3)


@pytest.mark.parametrize('channels', [False, True])
def test_compute_diameter_of_stack(qtbot, viewer_widget, cellpose3, channels):
    """a stack's diameter is that of the plane on show"""
    viewer, widget = viewer_widget
    [sample] = viewer.open_sample(PLUGIN_NAME, 'rgb_3D')
    zcyx = sample.data[20:30]
    viewer.layers.clear()
    widget.model_type.value = 'cyto3'
    widget.main_channel.value = 2  # 1=green

    def diameter(layer, **axes):
        widget.image_layer.value = layer
        for name, value in axes.items():
            getattr(widget, name).value = value
        widget.diameter.value = '30'
        with qtbot.waitSignal(widget.diameter.changed, timeout=120_000):
            widget.compute_diameter_button.changed(None)
        return float(widget.diameter.value)

    plane = 6
    if channels:
        stack = viewer.add_image(zcyx, scale=(2, 1, 1, 1))
        flat = viewer.add_image(zcyx[plane])
        axes, flat_axes = {'z_axis': 0, 'channel_axis': 1}, {'channel_axis': 0}
    else:
        stack = viewer.add_image(zcyx[:, 1], scale=(2, 1, 1))
        flat = viewer.add_image(zcyx[plane, 1])
        axes, flat_axes = {'z_axis': 0}, {}
    viewer.dims.set_point(viewer.dims.ndim - stack.ndim, plane * 2)
    of_stack = diameter(stack, **axes)
    assert of_stack != 30
    assert of_stack == diameter(flat, **flat_axes)


def test_widget_defaults(viewer_widget):
    _, widget = viewer_widget
    assert widget.diameter.value == "30"
    assert widget.cellprob_threshold.value == pytest.approx(0.0)
    assert widget.flow_threshold.value == pytest.approx(0.4)
    assert widget.min_size.value == 15
    assert widget.resample_dynamics.value == False
    assert widget.process_3D.value == False
    assert widget.stitch_threshold_3D.value == "0"
    assert widget.clear_previous_segmentations.value == True
    assert widget.compute_masks_button.enabled == False
    assert widget.z_axis.native.isHidden()
    assert widget.channel_axis.native.isHidden()
    assert widget.main_channel.native.isHidden()  # the default model is a v4 one
    assert widget.custom_model.native.isHidden()


def test_controls_follow_model(viewer_widget):
    viewer, widget = viewer_widget
    widget.image_layer.value = viewer.add_image(np.zeros((5, 64, 64)), name='stack')
    v3_only = [widget.main_channel, widget.optional_nuclear_channel, widget.compute_diameter_button]

    widget.model_type.value = 'cyto3'
    assert not any(w.native.isHidden() for w in v3_only)
    assert not widget.z_axis.native.isHidden()

    widget.model_type.value = 'cpsam'
    assert all(w.native.isHidden() for w in v3_only)
    assert not widget.z_axis.native.isHidden()


def test_axes_survive_model_change(viewer_widget):
    viewer, widget = viewer_widget
    widget.image_layer.value = viewer.add_image(np.zeros((5, 64, 64)), name='stack')
    widget.channel_axis.value = 0
    widget.model_type.value = 'cyto3'  # hides the axis pickers
    widget.model_type.value = 'cpsam'
    assert widget.channel_axis.value == 0


def test_axis_choices_survive_layer_changes(viewer_widget):
    viewer, widget = viewer_widget
    widget.image_layer.value = viewer.add_image(np.zeros((3, 64, 64)), name='stack')
    widget.channel_axis.value = 0
    viewer.add_image(np.zeros((64, 64)), name='other')  # napari resets the widget's choices
    assert widget.image_layer.value.name == 'stack'
    assert -1 in widget.z_axis.choices
    assert widget.z_axis.value == -1
    assert widget.channel_axis.value == 0


def test_3d_axes_exclude_each_other(viewer_widget):
    viewer, widget = viewer_widget
    widget.image_layer.value = viewer.add_image(np.zeros((3, 64, 64)), name='stack')
    assert widget.process_3D.value == True
    widget.channel_axis.value = 0
    assert widget.z_axis.value == -1
    assert widget.process_3D.value == False
    widget.z_axis.value = 0
    assert widget.channel_axis.value == -1

    # a labelled channel axis is picked up on selection
    layer = viewer.add_image(np.zeros((3, 64, 64)), name='labelled')
    layer.axis_labels = ('c', 'y', 'x')
    widget.image_layer.value = layer
    assert widget.channel_axis.value == 0
    assert widget.z_axis.value == -1
    assert widget.process_3D.value == False


@pytest.mark.parametrize('shape, chan, z', [((2, 8, 32, 32), 0, 1), ((8, 2, 32, 32), 1, 0)])
def test_unlabelled_4d_axes_differ(viewer_widget, shape, chan, z):
    viewer, widget = viewer_widget
    widget.image_layer.value = viewer.add_image(np.zeros(shape), name='stack')
    assert (widget.channel_axis.value, widget.z_axis.value) == (chan, z)


@pytest.mark.parametrize('model_type', ['cpsam', 'cyto3'])
@pytest.mark.parametrize('process_3D', [True, False])
def test_rgb_stack(qtbot, viewer_widget, recording_model, model_type, process_3D):
    viewer, widget = viewer_widget
    model = recording_model(model_type)
    layer = viewer.add_image(np.zeros((8, 32, 32, 3)), name='stack', rgb=True, scale=(2, 1, 1))
    masks = _segment(qtbot, viewer, widget, model_type, layer, process_3D=process_3D)
    assert masks.data.shape == layer.data.shape[:-1]
    [kwargs] = model.calls
    assert kwargs['anisotropy'] == (2.0 if process_3D else None)


@pytest.fixture
def shown_errors(monkeypatch):
    """the messages of the errors the widget shows"""
    import napari.utils.notifications

    errors = []
    monkeypatch.setattr(napari.utils.notifications, 'show_error', errors.append)
    return errors


@pytest.mark.parametrize('shape, axes', [
    ((8, 32, 32), {'z_axis': -1, 'channel_axis': -1}),
    ((2, 8, 32, 32), {'z_axis': 1, 'channel_axis': 1}),
])
def test_unusable_axes(shown_errors, viewer_widget, recording_model, shape, axes):
    viewer, widget = viewer_widget
    model = recording_model('cpsam')
    widget.image_layer.value = viewer.add_image(np.zeros(shape), name='stack')
    for name, value in axes.items():
        getattr(widget, name).value = value
    widget()
    assert len(shown_errors) == 1
    assert not model.calls


def test_merged_channels(qtbot, viewer_widget):
    """channels in separate layers, merged to a stack, segment as one 2D image"""
    from napari.layers._layer_actions import _merge_stack

    viewer, widget = viewer_widget
    [rgb] = viewer.open_sample(PLUGIN_NAME, 'rgb_2D')
    viewer.layers.clear()
    for i in range(3):
        viewer.add_image(rgb.data[..., i], name=f'ch{i}')
    viewer.layers.select_all()
    _merge_stack(viewer.layers)
    [stack] = viewer.layers
    assert stack.data.shape[0] == 3

    widget.model_type.value = 'cpsam'
    widget.image_layer.value = stack
    widget.channel_axis.value = 0
    widget()

    qtbot.waitUntil(lambda: bool(widget.cellpose_layers), timeout=360_000)
    assert len(widget.cellpose_layers) == 1  # not one per channel
    masks = viewer.layers[-1]
    assert masks.data.shape == stack.data.shape  # one mask per channel
    assert masks.data.max() == 37  # as for the same image loaded as RGB

    old = masks.data
    widget.compute_masks_button.native.click()
    qtbot.waitUntil(lambda: masks.data is not old, timeout=60_000)
    assert masks.data.shape == old.shape


@pytest.fixture
def recording_model(monkeypatch, request):
    """swaps the model of a model type's cellpose for a stand-in that runs no network: it lays
    out the image as that cellpose does, finds one cell filling the first Z plane, and records
    what eval gets"""
    def record(model_type):
        cp = request.getfixturevalue('cellpose3') if model_type in _backends.V3_MODELS else _backends.load(4)

        class Model:
            calls = []
            device = torch.device('cpu')

            def __init__(self, **_):
                pass

            def eval(self, image, **kwargs):
                self.calls.append(kwargs)
                convert = dict(channel_axis=kwargs['channel_axis'], z_axis=kwargs['z_axis'],
                               do_3D=kwargs['do_3D'] or kwargs['stitch_threshold'] > 0)
                if 'channels' in kwargs:
                    convert.update(channels=kwargs['channels'], nchan=2)
                shape = cp.transforms.convert_image(image, **convert).shape[:-1]  # channels last
                masks = np.zeros(shape, np.uint16)
                masks[0] = 1
                # without resampled dynamics, cellpose returns 3D flows at the Z size the network ran at
                flow_shape = (int(shape[0] * (kwargs['anisotropy'] or 1)), *shape[1:]) if kwargs['do_3D'] else shape
                n_flows = 3 if kwargs['do_3D'] else 2
                cellprob = np.full(flow_shape, -10.0)  # no cells, should masks be recomputed
                return masks, [np.zeros((*flow_shape, 3)), np.zeros((n_flows, *flow_shape)), cellprob], None

        monkeypatch.setattr(cp.models, 'CellposeModel', Model)
        return Model
    return record


def _segment(qtbot, viewer, widget, model_type, layer, **values):
    """segment `layer` with `values` set in the widget; returns the masks layer"""
    widget.model_type.value = model_type
    widget.image_layer.value = layer
    for name, value in values.items():
        getattr(widget, name).value = value
    widget()
    qtbot.waitUntil(lambda: bool(getattr(widget, 'cellpose_layers', None)), timeout=60_000)
    return viewer.layers[f'{layer.name}_cp_masks_000']


@pytest.mark.parametrize('model_type, shape, scale, axes, stitch, anisotropy', [
    ('cpsam', (8, 32, 32), (2, 0.5, 0.5), {}, '0', 4.0),
    # Z need not come first
    ('cpsam', (32, 32, 8), (0.5, 0.5, 2), {'z_axis': 2}, '0', 4.0),
    ('cpsam', (2, 8, 32, 32), (1, 3, 0.5, 0.5), {'z_axis': 1, 'channel_axis': 0}, '0', 6.0),
    ('cyto3', (32, 32, 8), (0.5, 0.5, 2), {'z_axis': 2}, '0', 4.0),
    # cellpose keeps its default for isotropic layers, and when stitching 2D slices
    ('cpsam', (8, 32, 32), (0.5, 0.5, 0.5), {}, '0', None),
    ('cpsam', (8, 32, 32), (2, 0.5, 0.5), {}, '0.5', None),
])
def test_anisotropy_from_scale(qtbot, viewer_widget, recording_model,
                               model_type, shape, scale, axes, stitch, anisotropy):
    viewer, widget = viewer_widget
    model = recording_model(model_type)
    layer = viewer.add_image(np.zeros(shape), name='stack', scale=scale)
    masks = _segment(qtbot, viewer, widget, model_type, layer, stitch_threshold_3D=stitch, **axes)

    [kwargs] = model.calls
    assert kwargs['do_3D'] == (stitch == '0')
    assert kwargs['anisotropy'] == anisotropy
    # the flows line up with the masks, whatever Z size the network ran at
    cellprob = viewer.layers['stack_cp_cellprob_000']
    np.testing.assert_allclose(cellprob.data.shape * cellprob.scale, masks.data.shape * masks.scale)


@pytest.mark.parametrize('model_type', ['cpsam', 'cyto3'])
@pytest.mark.parametrize('shape, axes', [
    ((4, 32, 32), {'z_axis': 0}),
    ((32, 4, 32), {'z_axis': 1}),
    ((4, 2, 32, 32), {'z_axis': 0, 'channel_axis': 1}),
])
def test_planes(qtbot, viewer_widget, recording_model, model_type, shape, axes):
    """a stack segmented plane by plane in 2D gives one stack of results"""
    viewer, widget = viewer_widget
    recording_model(model_type)
    layer = viewer.add_image(np.zeros(shape), name='stack')
    masks = _segment(qtbot, viewer, widget, model_type, layer, process_3D=False, **axes)
    assert len(widget.cellpose_layers) == 1

    old = masks.data
    widget.compute_masks_button.native.click()
    qtbot.waitUntil(lambda: masks.data is not old, timeout=60_000)
    assert masks.data.shape == old.shape
    assert masks.data.max() == 0  # the stand-in's flows hold no cells


@pytest.mark.parametrize('model_type', ['cpsam', 'cyto3'])
@pytest.mark.parametrize('shape, scale, axes, z', [
    ((32, 32, 8), (0.5, 0.6, 2), {'z_axis': 2}, 2),
    ((32, 8, 32), (0.5, 2, 0.6), {'z_axis': 1, 'process_3D': False}, 1),
    ((2, 8, 32, 32), (1, 2, 0.5, 0.6), {'z_axis': 1, 'channel_axis': 0}, 1),
    ((8, 2, 32, 32), (2, 1, 0.5, 0.6), {'z_axis': 0, 'channel_axis': 1}, 0),
    ((3, 32, 32), (1, 0.5, 0.6), {'channel_axis': 0}, None),  # 2D with channels
])
def test_results_line_up_with_layer(qtbot, viewer_widget, recording_model, model_type, shape, scale, axes, z):
    viewer, widget = viewer_widget
    recording_model(model_type)
    layer = viewer.add_image(np.zeros(shape), name='stack', scale=scale)
    masks = _segment(qtbot, viewer, widget, model_type, layer, **axes)
    assert masks.data.shape == layer.data.shape
    np.testing.assert_array_equal(masks.scale, layer.scale)
    if z is not None:  # the stand-in's cell fills the first Z plane
        assert np.take(masks.data, 0, axis=z).all()
        assert not np.take(masks.data, 1, axis=z).any()

    old = masks.data
    widget.compute_masks_button.native.click()
    qtbot.waitUntil(lambda: masks.data is not old, timeout=60_000)
    assert masks.data.shape == layer.data.shape


def test_recompute_masks_of_last_run(qtbot, viewer_widget, recording_model):
    """recomputing updates the last run's layers, whichever layer is selected since"""
    viewer, widget = viewer_widget
    recording_model('cpsam')
    layer = viewer.add_image(np.zeros((32, 32)), name='image')
    masks = _segment(qtbot, viewer, widget, 'cpsam', layer)
    widget.image_layer.value = viewer.layers['image_cp_flows_000']

    old = masks.data
    widget.compute_masks_button.native.click()
    qtbot.waitUntil(lambda: masks.data is not old, timeout=60_000)
    assert masks.data.max() == 0  # the stand-in's flows hold no cells
    assert viewer.layers['image_cp_outlines_000'].data.max() == 0


@pytest.mark.parametrize('model_type', ['cpsam', 'cyto3'])
def test_recompute_masks_in_3d(qtbot, viewer_widget, recording_model, model_type):
    """masks recompute from 3D flows, which the network ran at twice the Z size here"""
    viewer, widget = viewer_widget
    recording_model(model_type)
    layer = viewer.add_image(np.zeros((4, 32, 32)), name='stack', scale=(2, 1, 1))
    masks = _segment(qtbot, viewer, widget, model_type, layer, z_axis=0, process_3D=True)
    assert widget.flows_orig[2].shape == (8, 32, 32)

    old = masks.data
    widget.compute_masks_button.native.click()
    qtbot.waitUntil(lambda: masks.data is not old, timeout=60_000)
    assert masks.data.shape == old.shape
    assert masks.data.max() == 0  # the stand-in's flows hold no cells


def test_anisotropy_with_uneven_yx(caplog):
    with caplog.at_level(logging.WARNING, logger='napari_cellposesam._dock_widget'):
        assert _anisotropy((2, 0.5, 1.5), z_axis=0) == 2.0  # against the mean of Y and X
    assert 'Y by 0.5 and X by 1.5' in caplog.text


def test_anisotropy_of_flipped_axes():
    assert _anisotropy((-2, 0.5, -0.5), z_axis=0) == 4.0


def _fake_model(path, **tensors):
    torch.save({k: torch.zeros(shape) for k, shape in tensors.items()}, path)
    return path


def test_probe_model_major(tmp_path):
    probe = _backends.probe_model_major
    assert probe(_fake_model(tmp_path / 'v4', W2=(192, 3, 8, 8))) == 4
    assert probe(_fake_model(tmp_path / 'v3', **{'output.2.weight': (3, 32, 1, 1)})) == 3
    # a v3 denoise net has one output and cannot segment
    assert probe(_fake_model(tmp_path / 'dn', **{'output.2.weight': (1, 32, 1, 1)})) is None
    (tmp_path / 'junk').write_bytes(b'not a model')
    assert probe(tmp_path / 'junk') is None


def test_custom_model_picks_version(viewer_widget, tmp_path):
    _, widget = viewer_widget
    widget.model_type.value = 'custom'
    assert not widget.custom_model.native.isHidden()
    widget.custom_model.value = _fake_model(tmp_path / 'v3', **{'output.2.weight': (3, 32, 1, 1)})
    assert not widget.main_channel.native.isHidden()
    widget.custom_model.value = _fake_model(tmp_path / 'v4', W2=(192, 3, 8, 8))
    assert widget.main_channel.native.isHidden()
    # a leftover path does not apply to a built-in model
    widget.model_type.value = 'cyto3'
    assert widget.custom_model.native.isHidden()
    assert not widget.main_channel.native.isHidden()


def test_dimensionality_detection(viewer_widget):
    viewer, widget = viewer_widget

    layer_3d = viewer.add_image(np.zeros((5, 64, 64)), name='stack')
    widget.image_layer.value = layer_3d
    assert widget.process_3D.value == True
    # isVisible() requires all parents to be visible; isHidden() checks the widget's own flag
    assert not widget.z_axis.native.isHidden()
    assert not widget.channel_axis.native.isHidden()

    layer_2d = viewer.add_image(np.zeros((64, 64)), name='flat')
    widget.image_layer.value = layer_2d
    assert widget.process_3D.value == False
    assert widget.z_axis.native.isHidden()
    assert widget.channel_axis.native.isHidden()


def test_diameter_from_shape(viewer_widget):
    viewer, widget = viewer_widget

    # 30×30 square: ptp=[30,30], sum=60 → diam = (60/2) * (27/30) = 27.0
    rect = np.array([[0, 0], [0, 30], [30, 30], [30, 0]], dtype=float)
    shape_layer = viewer.add_shapes([rect], shape_type='rectangle')
    widget.shape_layer.value = shape_layer

    widget.compute_diameter_shape.changed(None)

    assert float(widget.diameter.value) == pytest.approx(27.0)


def test_cellpose3_fetched_on_first_use(qtbot, viewer_widget, cellpose3, tmp_path, monkeypatch, accept_prompts):
    monkeypatch.setenv('NAPARI_CELLPOSESAM_CACHE', str(tmp_path))  # nothing fetched here yet
    viewer, widget = viewer_widget
    viewer.open_sample(PLUGIN_NAME, 'rgb_2D')
    widget.model_type.value = 'cyto3'

    widget()  # prompts, fetches, then runs the segmentation it was asked for
    qtbot.waitUntil(lambda: bool(getattr(widget, 'cellpose_layers', None)), timeout=360_000)
    assert len(accept_prompts) == 1 and 'download cellpose 3' in accept_prompts[0]
    assert _backends.v3_missing() == []
    assert viewer.layers[-1].data.max() == 41
