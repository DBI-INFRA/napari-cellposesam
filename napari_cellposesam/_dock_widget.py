"""
cellpose dock widget — runs cellpose v4 models, and cellpose v3 models on cellpose v3

Each segmentation picks its cellpose release from the selected model (see _backends).
"""
from typing import Any

import functools
import numpy as np
import logging
import threading

from . import _backends

logger = logging.getLogger(__name__)

cp_strings = ['_cp_masks_', '_cp_outlines_', '_cp_flows_', '_cp_cellprob_']

# torch's MPS backend crashes (double free) when two threads run kernels at once, so
# workers that run cellpose take turns, also across widgets in the same napari
_cellpose_lock = threading.Lock()


def _one_at_a_time(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        with _cellpose_lock:
            return func(*args, **kwargs)
    return wrapped


DINOV3_URL = 'git+https://github.com/facebookresearch/dinov3'


def _dinov3_status(pretrained_model):
    """Can cellpose build a CPDINO network for this model? 'ok', 'missing' or 'stale'.
    """
    import importlib.util

    if not str(pretrained_model).startswith('cpdino'):
        return 'ok'

    from cellpose import vit  # cellpose v4 only; v3 has no cpdino models to reach this

    if hasattr(vit, 'dinov3_vitl16'):
        return 'ok'
    return 'missing' if importlib.util.find_spec('dinov3') is None else 'stale'


_main_channel_choices = [('average all channels', 0), ('0=red', 1), ('1=green', 2), ('2=blue', 3),
                          ('3', 4), ('4', 5), ('5', 6), ('6', 7), ('7', 8), ('8', 9)]
_nuclear_channel_choices = [('none', 0), ('0=red', 1), ('1=green', 2), ('2=blue', 3),
                             ('3', 4), ('4', 5), ('5', 6), ('6', 7), ('7', 8), ('8', 9)]


def widget_wrapper():
    from napari import Viewer
    from napari.layers import Image, Shapes
    from magicgui import magicgui
    from napari.qt.threading import thread_worker
    from napari.utils.notifications import show_error, show_info
    # importing cellpose costs a few seconds (it pulls in torch), but the first
    # segmentation would pay that anyway, and it keeps the model list in step
    # with whatever cellpose is installed
    from cellpose.models import MODEL_DIR, MODEL_NAMES
    try:
        from torch import no_grad
    except ImportError:
        def no_grad():
            def _deco(func):
                return func
            return _deco

    @thread_worker
    @_one_at_a_time
    @no_grad()
    def run_cellpose(major, image, diameter, resample, cellprob_threshold, flow_threshold,
                     min_size, do_3D, stitch_threshold,
                     model_type=None, custom_model=None, channels=None, channel_axis=None,
                     z_axis=None):
        # here, not on the GUI thread: loading cellpose 3 takes seconds of numba compiles
        try:
            cp = _backends.load(major)
        except Exception as e:
            return _backends.load_error(major, e)  # a message for the GUI thread to show
        models = cp.models

        if major == 4:
            import inspect

            pretrained_model = custom_model if model_type == 'custom' else model_type
            device, gpu = cp.core.assign_device(gpu=True)
            model_kwargs = dict(gpu=gpu, device=device, pretrained_model=pretrained_model)
            # bf16 is ~8x slower than fp32 on CPUs without native bf16 support
            if 'use_bfloat16' in inspect.signature(models.CellposeModel).parameters:
                model_kwargs['use_bfloat16'] = device.type != 'cpu'
            CP = models.CellposeModel(**model_kwargs)
        elif model_type == 'custom':
            CP = models.CellposeModel(pretrained_model=custom_model, gpu=True)
        else:
            CP = models.CellposeModel(model_type=model_type, gpu=True)

        if major == 4:
            eval_kwargs = dict(
                diameter=diameter,
                resample=resample,
                cellprob_threshold=cellprob_threshold,
                flow_threshold=flow_threshold,
                min_size=min_size,
                do_3D=do_3D,
                stitch_threshold=stitch_threshold,
            )
            if channel_axis is not None:
                eval_kwargs['channel_axis'] = channel_axis
            if z_axis is not None:
                eval_kwargs['z_axis'] = z_axis
        else:
            eval_kwargs = dict(
                diameter=diameter,
                resample=resample,
                cellprob_threshold=cellprob_threshold,
                flow_threshold=flow_threshold,
                min_size=min_size,
                do_3D=do_3D,
                stitch_threshold=stitch_threshold,
                channels=channels,
                channel_axis=channel_axis,
            )

        masks, flows_orig, _ = CP.eval(image, **eval_kwargs)
        del CP
        if not do_3D and stitch_threshold == 0 and masks.ndim > 2:
            flows = [[flows_orig[0][i],
                      flows_orig[1][:, i],
                      flows_orig[2][i],
                      flows_orig[3][:, i]] for i in range(masks.shape[0])]
            masks = list(masks)
            flows_orig = flows
        return cp, masks, flows_orig

    @thread_worker
    @_one_at_a_time
    def compute_diameter(image, channels, model_type):
        try:
            cp = _backends.load(3)
        except Exception as e:
            return _backends.load_error(3, e)
        model_type0 = model_type if model_type in _backends.V3_SIZE_MODELS else "cyto3"
        CP = cp.models.Cellpose(model_type=model_type0, gpu=True)
        diam = CP.sz.eval(image, channels=channels, channel_axis=-1)[0]
        diam = np.around(diam, 2)
        del CP
        return diam

    @thread_worker
    def pip_install_dinov3():
        import importlib

        try:
            # --no-user: never fall back to the user site, which may not be on sys.path
            _backends._pip('install', '--no-user', DINOV3_URL)
        except Exception as e:
            return str(e)
        importlib.invalidate_caches()

    def offer_dinov3_install(model_type):
        """Prompt to install DINOv3, which is not on PyPI and so cannot be a dependency."""
        from qtpy.QtWidgets import QMessageBox

        if widget._installing_dinov3:
            show_info('DINOv3 is still being installed')
            return
        box = QMessageBox(
            QMessageBox.Icon.Question, 'Install DINOv3?',
            f'The {model_type} model needs the DINOv3 package, which is not on PyPI and '
            f'so is not installed with napari-cellposesam.\n\nInstall it now from\n{DINOV3_URL}\n\n'
            'napari must be restarted afterwards.',
            parent=widget.native)
        install = box.addButton('Install', QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)  # Enter should not install a package by accident
        box.exec()
        if box.clickedButton() is not install:
            return
        show_info('installing DINOv3, this may take a few minutes...')
        widget._installing_dinov3 = True
        install_worker = pip_install_dinov3()
        install_worker.returned.connect(report_dinov3_install)
        install_worker.errored.connect(lambda e: report_dinov3_install(str(e) or repr(e)))
        install_worker.start()

    def report_dinov3_install(error):
        widget._installing_dinov3 = False
        if error:
            show_error(f'installing DINOv3 failed: {error}')
        else:
            show_info('DINOv3 installed. restart napari to use the cpdino models.')

    @thread_worker
    def fetch_cellpose3():
        try:
            _backends.fetch_v3()
        except Exception as e:
            return str(e)

    def offer_cellpose3_fetch(model_type, then):
        """Prompt to fetch cellpose v3 for a v3 model, then call `then` once it is ready."""
        from qtpy.QtWidgets import QMessageBox

        if widget._fetching:
            show_info('cellpose 3 is still being fetched')
            return
        missing = _backends.v3_missing()
        deps = [dep for dep in missing if dep != 'cellpose']
        text = (f'The {model_type} model needs cellpose 3, but napari-cellposesam comes with '
                'cellpose 4.\n\n')
        if 'cellpose' in missing:
            text += f'The plugin will download cellpose {_backends.V3_VERSION} into a private folder.'
            if deps:
                text += f' It will also install {", ".join(deps)} into this Python environment.'
        else:  # the cache is shared between environments, the dependencies are not
            text += (f'cellpose {_backends.V3_VERSION} is already downloaded, but it needs '
                     f'{", ".join(deps)}, which the plugin will install into this Python environment.')
        box = QMessageBox(QMessageBox.Icon.Question, 'Fetch cellpose 3?', text, parent=widget.native)
        fetch = box.addButton('Fetch', QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() is not fetch:
            return
        show_info('fetching cellpose 3...')
        widget._fetching = True
        fetch_worker = fetch_cellpose3()
        fetch_worker.returned.connect(lambda error: report_cellpose3_fetch(error, then))
        fetch_worker.errored.connect(lambda e: report_cellpose3_fetch(str(e) or repr(e), then))
        fetch_worker.start()

    def report_cellpose3_fetch(error, then):
        widget._fetching = False
        if error:
            show_error(f'fetching cellpose 3 failed: {error}')
            return
        # e.g. numba installed somewhere this python does not look
        missing = _backends.v3_missing()
        if missing:
            show_error(f'fetching cellpose 3 finished, but {", ".join(missing)} is still missing')
            return
        show_info('cellpose 3 is ready')
        then()

    @thread_worker
    @_one_at_a_time
    def compute_masks(cp, major, masks_orig, flows_orig, cellprob_threshold, flow_threshold):
        flow_threshold = (31.0 - flow_threshold) / 10.
        if flow_threshold == 0.0:
            logger.debug('flow_threshold=0 => no masks thrown out due to model mismatch')
        logger.debug(f'computing masks with cellprob_threshold={cellprob_threshold}, flow_threshold={flow_threshold}')
        kwargs = dict(cellprob_threshold=cellprob_threshold,
                      flow_threshold=flow_threshold)
        if major == 3:
            kwargs['resize'] = (masks_orig.shape[-2], masks_orig.shape[-1])
        # both the pinned cellpose 3.1.1.3 and cellpose v4 return the masks alone
        return cp.dynamics.resize_and_compute_masks(flows_orig[1], cellprob=flows_orig[2], **kwargs)

    # -1 is a sentinel meaning "not specified" for z_axis and channel_axis.
    # This lets a single ComboBox serve both 3D (optional) and 4D (required) images.
    _z_axis_3d_choices = [('none', -1), ('0', 0), ('1', 1), ('2', 2)]
    _channel_axis_3d_choices = [('none (ZYX)', -1), ('0', 0), ('1', 1), ('2', 2)]

    _shared_kwargs = dict(
        call_button='run segmentation',
        layout='vertical',
        diameter=dict(widget_type='LineEdit', label='diameter', value=30,
                      tooltip='approximate diameter of cells to be segmented'),
        compute_diameter_shape=dict(widget_type='PushButton', text='compute diameter from shape layer',
                                    tooltip='create shape layer with circles and/or squares, select above, '
                                            'and diameter will be estimated from it'),
        cellprob_threshold=dict(widget_type='FloatSlider', name='cellprob_threshold', value=0.0,
                                min=-8.0, max=8.0, step=0.2,
                                tooltip='cell probability threshold (set lower to get more cells and larger cells)'),
        flow_threshold=dict(widget_type='FloatSlider', name='flow_threshold', value=0.4,
                            min=0.0, max=3.0, step=0.05,
                            tooltip='threshold on gradient match to accept a mask '
                                    '(set higher to get more cells, or to zero to turn off)'),
        min_size=dict(widget_type='SpinBox', label='min size (px)', value=15, min=1,
                      tooltip='minimum area per mask; smaller objects are removed'),
        compute_masks_button=dict(widget_type='PushButton',
                                  text='recompute last masks with new cellprob', enabled=False),
        resample_dynamics=dict(widget_type='CheckBox', text='resample dynamics', value=False,
                               tooltip='if False, mask estimation with dynamics run on resized image with diameter=30; '
                                       'if True, flows are resized to original image size before dynamics and mask '
                                       'estimation (turn on for more smooth masks)'),
        process_3D=dict(widget_type='CheckBox', text='process stack as 3D', value=False,
                        tooltip='use default 3D processing where flows in X, Y, and Z are computed '
                                'and dynamics run in 3D to create masks'),
        stitch_threshold_3D=dict(widget_type='LineEdit', label='stitch threshold slices', value=0,
                                 tooltip='across time or Z, stitch together masks with IoU threshold of '
                                         '"stitch threshold" to create 3D segmentation'),
        clear_previous_segmentations=dict(widget_type='CheckBox', text='clear previous results', value=True),
    )

    # z_axis and channel_axis go immediately after process_3D
    _mgui_kwargs = {}
    for k, v in _shared_kwargs.items():
        _mgui_kwargs[k] = v
        if k == 'process_3D':
            _mgui_kwargs['z_axis'] = dict(
                widget_type='ComboBox', label='z axis', choices=[0, 1, 2, 3], value=0,
                visible=False, tooltip='which axis represents Z in the 4D image')
            _mgui_kwargs['channel_axis'] = dict(
                widget_type='ComboBox', label='channel axis', choices=_channel_axis_3d_choices,
                value=-1, visible=False,
                tooltip='which axis represents channels; "none" treats all axes as spatial (ZYX)')
    _mgui_kwargs.update(
        model_type=dict(widget_type='ComboBox', label='model type',
                        choices=[*MODEL_NAMES, *_backends.V3_MODELS, 'custom'],
                        value=MODEL_NAMES[0],
                        tooltip='built-in cellpose model to segment with, or <em>custom</em> '
                                'to load your own model from a file. Cellpose3 models fetch '
                                'cellpose 3 the first time they run'),
        custom_model=dict(widget_type='FileEdit', label='custom model path: ', visible=False,
                          tooltip='file path of the custom model to segment with'),
        # cellpose v3 only, shown while a v3 model is selected
        main_channel=dict(widget_type='ComboBox', label='channel to segment', visible=False,
                          choices=_main_channel_choices, value=0, tooltip='choose channel with cells'),
        optional_nuclear_channel=dict(widget_type='ComboBox', label='optional nuclear channel',
                                      visible=False, choices=_nuclear_channel_choices, value=0,
                                      tooltip='optional, if available, choose channel with nuclei of cells'),
        compute_diameter_button=dict(widget_type='PushButton', text='compute diameter from image',
                                     visible=False,
                                     tooltip='cellpose model will estimate diameter from image using '
                                             'specified channels'),
    )

    def widget(
        viewer: Viewer,
        image_layer: Image,
        model_type,
        custom_model,
        main_channel,
        optional_nuclear_channel,
        diameter,
        shape_layer: Shapes,
        compute_diameter_shape,
        compute_diameter_button,
        cellprob_threshold,
        flow_threshold,
        min_size,
        compute_masks_button,
        resample_dynamics,
        process_3D,
        z_axis,
        channel_axis,
        stitch_threshold_3D,
        clear_previous_segmentations,
    ) -> None:

        if not hasattr(widget, 'cellpose_layers'):
            widget.cellpose_layers = []

        if model_type == 'custom' and not custom_model.resolve().is_file():
            show_error('model type is "custom" but no custom model file is selected')
            return
        major = _backends.model_major(model_type, custom_model.resolve())
        if major is None:
            show_error(f'{custom_model} is not a cellpose 3 or cellpose 4 segmentation model')
            return
        if major == 3 and _backends.v3_missing():
            offer_cellpose3_fetch(model_type, then=widget)
            return
        if major == 4:
            # before the status: a half-done install already looks 'stale'
            if widget._installing_dinov3 and str(model_type).startswith('cpdino'):
                show_info('DINOv3 is still being installed')
                return
            dinov3 = _dinov3_status(model_type)
            if dinov3 == 'missing':
                offer_dinov3_install(model_type)
                return
            if dinov3 == 'stale':
                show_error(f'the {model_type} model needs DINOv3, which is installed but '
                           'arrived after cellpose was loaded. restart napari and try again.')
                return

        def _new_layers(cp, masks, flows_orig):
            import cv2

            if masks.ndim == 2:
                resize_image = cp.transforms.resize_image
                flows = resize_image(flows_orig[0], masks.shape[-2], masks.shape[-1],
                                     interpolation=cv2.INTER_NEAREST).astype(np.uint8)
                cellprob = resize_image(flows_orig[2], masks.shape[-2], masks.shape[-1],
                                        no_channels=True).squeeze()
            else:
                # 3D: cellpose returns flows at the original resolution; resize_image
                # would collapse the Z axis, so use the arrays directly.
                flows = flows_orig[0].astype(np.uint8)
                cellprob = flows_orig[2]
            outlines = cp.utils.masks_to_outlines(masks) * masks
            # one mask per channel, so the results line up with the image layer
            widget._repeat_channels = widget._n_channels > 0 and masks.ndim == image_layer.ndim - 1
            if widget._repeat_channels:
                ax = widget._channel_axis
                n = widget._n_channels
                masks = np.repeat(np.expand_dims(masks, axis=ax), n, axis=ax)
                outlines = np.repeat(np.expand_dims(outlines, axis=ax), n, axis=ax)
                flows = np.repeat(np.expand_dims(flows, axis=ax), n, axis=ax)
                cellprob = np.repeat(np.expand_dims(cellprob, axis=ax), n, axis=ax)

            widget.flows_orig = flows_orig
            widget.masks_orig = masks
            widget._cp, widget._major = cp, major
            widget.iseg = '_' + '%03d' % len(widget.cellpose_layers)

            physical_scale = image_layer.scale[-3:] if len(image_layer.scale) > 3 else image_layer.scale
            name = image_layer.name
            layers = [
                viewer.add_image(flows, name=name + '_cp_flows' + widget.iseg,
                                 visible=False, rgb=True, scale=physical_scale),
                viewer.add_image(cellprob, name=name + '_cp_cellprob' + widget.iseg,
                                 visible=False, scale=physical_scale),
                viewer.add_labels(outlines, name=name + '_cp_outlines' + widget.iseg,
                                  visible=False, scale=physical_scale),
                viewer.add_labels(masks, name=name + '_cp_masks' + widget.iseg,
                                  visible=False, scale=physical_scale),
            ]
            widget.cellpose_layers.append(layers)

        def _new_segmentation(segmentation):
            if isinstance(segmentation, str):  # cellpose failed to load
                show_error(segmentation)
                return
            cp, masks, flows_orig = segmentation
            # only now, so a failed run keeps the previous results
            if clear_previous_segmentations:
                layer_names = [layer.name for layer in viewer.layers]
                for layer_name in layer_names:
                    if any(cp_string in layer_name for cp_string in cp_strings):
                        viewer.layers.remove(viewer.layers[layer_name])
                widget.cellpose_layers = []
            try:
                if isinstance(masks, list):  # a stack segmented slice by slice
                    for mask, flow_orig in zip(masks, flows_orig):
                        _new_layers(cp, mask, flow_orig)
                else:
                    _new_layers(cp, masks, flows_orig)

                for layer in viewer.layers:
                    layer.visible = False
                viewer.layers[-1].visible = True
                image_layer.visible = True
                if not float(stitch_threshold_3D):
                    widget.compute_masks_button.enabled = True
                # follows the model that made the stored flows, not the selected one
                widget.compute_masks_button.text = ('recompute last masks with new cellprob'
                                                    + (' + model match' if major == 3 else ''))
            except Exception as e:
                logger.error(e)
            widget.call_button.enabled = True

        # -1 is the sentinel meaning "not specified" for both axis selectors
        _channel_axis = channel_axis if channel_axis >= 0 else None
        _z_axis = z_axis if z_axis >= 0 else None

        image = image_layer.data
        widget._n_channels = 0
        widget._channel_axis = None
        # a 3D stack with a channel axis is one 2D image with channels
        is_stack = image_layer.ndim > 2 and not (
            major == 4 and image_layer.ndim == 3 and not image_layer.rgb and _channel_axis is not None)

        if image_layer.ndim == 4 and not image_layer.rgb:
            if major == 4:
                widget._channel_axis = _channel_axis
                if _channel_axis is not None:
                    widget._n_channels = image.shape[_channel_axis]
            else:
                chan = np.nonzero([a == 'c' for a in viewer.dims.axis_labels])[0]
                if len(chan) > 0:
                    chan = int(chan[0])
                    widget._channel_axis = chan
                    widget._n_channels = image.shape[chan]
        elif image_layer.ndim == 3 and not image_layer.rgb:
            if major == 4:
                widget._channel_axis = _channel_axis
                if _channel_axis is not None:
                    widget._n_channels = image.shape[_channel_axis]
            else:
                image = image[:, :, :, np.newaxis]
        elif image_layer.rgb:
            widget._channel_axis = -1

        run_kwargs = dict(
            major=major,
            image=image,
            diameter=float(diameter),
            resample=resample_dynamics,
            cellprob_threshold=cellprob_threshold,
            flow_threshold=flow_threshold,
            min_size=min_size,
            do_3D=(process_3D and float(stitch_threshold_3D) == 0 and is_stack),
            stitch_threshold=float(stitch_threshold_3D) if is_stack else 0.0,
        )
        if major == 4:
            run_kwargs.update(
                model_type=model_type,
                custom_model=str(custom_model.resolve()),
            )
            if image_layer.ndim == 4 and not image_layer.rgb:
                run_kwargs['z_axis'] = z_axis
                run_kwargs['channel_axis'] = _channel_axis
            elif image_layer.ndim == 3 and not image_layer.rgb:
                if _z_axis is not None and is_stack:
                    run_kwargs['z_axis'] = _z_axis
                if _channel_axis is not None:
                    run_kwargs['channel_axis'] = _channel_axis
        else:
            run_kwargs.update(
                model_type=model_type,
                custom_model=str(custom_model.resolve()),
                channels=[max(0, main_channel), max(0, optional_nuclear_channel)],
                channel_axis=widget._channel_axis,
            )

        if major == 4 and model_type in MODEL_NAMES and not (MODEL_DIR / model_type).exists():
            show_info(f'downloading the {model_type} model weights: this is a large '
                      'one-time download, and segmentation starts once it finishes')

        cp_worker = run_cellpose(**run_kwargs)
        cp_worker.returned.connect(_new_segmentation)
        cp_worker.start()

    widget = magicgui(widget, **_mgui_kwargs)
    widget._fetching = False  # a cellpose 3 fetch is in flight
    widget._installing_dinov3 = False

    def update_masks(masks):
        outlines = widget._cp.utils.masks_to_outlines(masks) * masks
        if widget._repeat_channels:
            ax = widget._channel_axis
            n = widget._n_channels
            masks = np.repeat(np.expand_dims(masks, axis=ax), n, axis=ax)
            outlines = np.repeat(np.expand_dims(outlines, axis=ax), n, axis=ax)

        widget.viewer.value.layers[widget.image_layer.value.name + '_cp_masks' + widget.iseg].data = masks
        outline_str = widget.image_layer.value.name + '_cp_outlines' + widget.iseg
        if outline_str in widget.viewer.value.layers:
            widget.viewer.value.layers[outline_str].data = outlines
        widget.masks_orig = masks
        logger.debug('masks updated')

    def _selected_major():
        """cellpose major of the selected model; a custom model without a usable file lays out as v4"""
        return _backends.model_major(widget.model_type.value, widget.custom_model.value) or 4

    def _is_stack(image_layer):
        return image_layer is not None and image_layer.ndim in (3, 4) and not image_layer.rgb

    def _show_axes():
        """show the z/channel axis pickers for stacks under v4 models; v3 reads napari's axis labels"""
        shown = _is_stack(widget.image_layer.value) and _selected_major() == 4
        widget.z_axis.visible = shown
        widget.channel_axis.visible = shown

    def _labelled_axes(image_layer):
        """the layer's z and channel axes from its axis labels, None where unlabelled"""
        axis_labels = image_layer.axis_labels
        z_val = np.nonzero([a == 'z' for a in axis_labels])[0]
        chan = np.nonzero([a == 'c' for a in axis_labels])[0]
        return (int(z_val[0]) if len(z_val) > 0 else None,
                int(chan[0]) if len(chan) > 0 else None)

    def _axis_choices(image_layer):
        """z and channel axis choices for the layer"""
        if image_layer is None or image_layer.ndim != 4:
            return _z_axis_3d_choices, _channel_axis_3d_choices
        z_val, chan = _labelled_axes(image_layer)
        all_axes = list(range(image_layer.ndim))
        z_choices = [i for i in all_axes if i != chan] if chan is not None else all_axes
        c_choices = [i for i in all_axes if i != z_val] if z_val is not None else all_axes
        return z_choices, c_choices

    # callables, so napari's reset_choices on every layer change rebuilds them for the
    # selected layer instead of restoring the choices the pickers were created with
    widget.z_axis.choices = lambda _: _axis_choices(widget.image_layer.value)[0]
    widget.channel_axis.choices = lambda _: _axis_choices(widget.image_layer.value)[1]

    def _is_2d_with_channels(image_layer):
        return _is_stack(image_layer) and image_layer.ndim == 3 and widget.channel_axis.value >= 0

    def _reset_axes(image_layer):
        """fill the axis pickers from the layer's axis labels, whichever model is selected,
        so they are right whenever a v4 model shows them"""
        if not _is_stack(image_layer):
            return
        widget.z_axis.reset_choices()
        widget.channel_axis.reset_choices()
        z_val, chan = _labelled_axes(image_layer)
        if image_layer.ndim == 4:
            z_choices, c_choices = widget.z_axis.choices, widget.channel_axis.choices
            widget.z_axis.value = z_val if z_val in z_choices else z_choices[0]
            widget.channel_axis.value = chan if chan in c_choices else c_choices[0]
        else:
            # a labelled channel axis without a z axis makes a 2D image with channels
            default_z = z_val if z_val is not None else (-1 if chan is not None else 0)
            widget.z_axis.value = default_z
            widget.channel_axis.value = chan if chan is not None else -1

    @widget.image_layer.changed.connect
    def check_dims(image_layer):
        _reset_axes(image_layer)
        widget.process_3D.value = _is_stack(image_layer) and not _is_2d_with_channels(image_layer)
        _show_axes()

    # a 3D layer has either a z axis (ZYX) or a channel axis (2D with channels), not both
    @widget.z_axis.changed.connect
    def _z_excludes_channels(z_val):
        layer = widget.image_layer.value
        if _is_stack(layer) and layer.ndim == 3 and z_val >= 0:
            widget.channel_axis.value = -1

    @widget.channel_axis.changed.connect
    def _channels_exclude_z(chan):
        layer = widget.image_layer.value
        if _is_stack(layer) and layer.ndim == 3 and chan >= 0:
            widget.z_axis.value = -1
            widget.process_3D.value = False

    def _update_model_controls(*_):
        widget.custom_model.visible = widget.model_type.value == 'custom'
        v3 = _selected_major() == 3
        for name in ('main_channel', 'optional_nuclear_channel', 'compute_diameter_button'):
            getattr(widget, name).visible = v3
        _show_axes()  # only visibility: the values stay as the user left them

    widget.model_type.changed.connect(_update_model_controls)
    widget.custom_model.changed.connect(_update_model_controls)

    if widget.image_layer.value is not None:
        check_dims(widget.image_layer.value)

    @widget.compute_masks_button.changed.connect
    def _compute_masks(e: Any):
        mask_worker = compute_masks(widget._cp, widget._major, widget.masks_orig,
                                    widget.flows_orig,
                                    widget.cellprob_threshold.value,
                                    widget.flow_threshold.value)
        mask_worker.returned.connect(update_masks)
        mask_worker.start()

    def _report_diameter(diam):
        if isinstance(diam, str):  # cellpose 3 failed to load
            show_error(diam)
            return
        widget.diameter.value = diam
        logger.debug(f'computed diameter = {diam}')

    @widget.compute_diameter_shape.changed.connect
    def _compute_diameter_shape(e: Any):
        if widget.shape_layer.value is None:
            logger.error('no shape layer selected')
            return
        diam = 0
        k = 0
        for d in widget.shape_layer.value.data:
            if len(d) == 4:
                diam += np.ptp(d, axis=0)[-2:].sum()
                k += 2
        diam /= k
        diam *= (27 / 30)
        if k > 0:
            _report_diameter(diam)
        else:
            logger.error('no square or circle shapes created')

    @widget.compute_diameter_button.changed.connect
    def _compute_diameter(e: Any = None):
        model_type = widget.model_type.value
        if model_type == 'custom':
            logger.error('cannot compute diameter for custom model')
            return
        if _backends.v3_missing():
            offer_cellpose3_fetch(model_type, then=_compute_diameter)
            return
        channels = [max(0, widget.main_channel.value), max(0, widget.optional_nuclear_channel.value)]
        image = widget.image_layer.value.data
        diam_worker = compute_diameter(image, channels, model_type)
        diam_worker.returned.connect(_report_diameter)
        diam_worker.start()

    return widget
