import os
from math import isclose
from typing import Callable

import napari
import numpy as np
import pytest
import torch
from napari_cellposesam import _backends

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
    assert len(viewer.window.dock_widgets) == 1

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


def test_compute_diameter(qtbot, viewer_widget, cellpose3):
    viewer, widget = viewer_widget
    viewer.open_sample(PLUGIN_NAME, 'rgb_2D')
    widget.model_type.value = 'cyto3'  # diameter estimation is cellpose v3 only

    assert widget.diameter.value == "30"
    with qtbot.waitSignal(widget.diameter.changed, timeout=60_000) as blocker:
        widget.compute_diameter_button.changed(None)

    # local on Windows with CPU/GPU 46.0
    assert isclose(float(widget.diameter.value), 46, abs_tol=0.3)


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
    # cellpose v3 takes its axes from napari's axis labels
    assert widget.z_axis.native.isHidden()

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
