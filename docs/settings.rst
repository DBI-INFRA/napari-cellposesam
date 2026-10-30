Settings
--------------------------

There are more settings for cellpose that can be accessed using the CLI or
through a jupyter notebook. See details at cellpose `docs`_.

Listed are settings available through the napari widget. Some settings only
exist for Cellpose3 or for cellpose 4 models; the widget shows the ones that
apply to the selected model. Please submit an `issue`_ if you would like a new setting
available in the widget.

Model type
~~~~~~~~~~~~~~~~~~~~~~~~

The built-in models are:

- ``cpsam_v2`` (default) and ``cpsam``: Cellpose-SAM models
- ``cpdino`` and ``cpdino-vitb``: models with a DINOv3 backbone, which need
  DINOv3 installed (see :doc:`installation`)
- ``cyto3``, ``cyto2``, ``cyto``, ``nuclei`` and the cp3 dataset-specific
  models: Cellpose3 models, which need cellpose 3. The plugin offers to
  download it the first time you run one (see :doc:`installation`)

Model weights are downloaded the first time a model is used. The Cellpose-SAM
weights are about 1.2 GB.

Select ``custom`` and set ``custom model path`` to use your own trained model.
The plugin reads the model file to tell whether it needs cellpose 3 or 4.

Channels (Cellpose3 models)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Cellpose-SAM uses all channels of the image and has no channel settings.
For Cellpose3 models the widget shows ``channel to segment`` and
``optional nuclear channel``.

Cytoplasm models (e.g. ``cyto3``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The cytoplasm models are trained on two-channel images, where
the first channel is the channel to segment, and the second channel is
an optional nuclear channel. Here are the options for each:

1. average all channels, 0=red, 1=green, 2=blue, 3 ...
2. none, 0=red, 1=green, 2=blue, 3 ...

Nucleus model (``nuclei``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The nuclear model is trained on two-channel images, where
the first channel is the channel to segment, and the second channel is
always set to an array of zeros. Therefore set the first channel to the
nuclear channel and set the second channel to none.

Diameter
~~~~~~~~~~~~~~~~~~~~~~~~

The image is rescaled by 30 / ``diameter`` before it is passed to the network,
so that cells are about 30 pixels across.

Cellpose-SAM is trained to work over a wide range of cell sizes, so the
default of 30 often works without changes. If cells are over-split, increase
the diameter; if they are over-merged, decrease it.

The Cellpose3 models are trained on images rescaled to a fixed diameter
(30 pixels for ``cyto`` models, 17 pixels for ``nuclei``) and are more
sensitive to this setting. With a Cellpose3 model, click ``compute diameter from image``
to estimate the diameter automatically. The estimation is a two-step process
using the `style` vector from the network, a 64-dimensional summary of the
input image:

1. Run the image through the cellpose network and obtain the style vector. Predict the size using a linear regression model from the style vector.
2. Resize the image based on the predicted size and run cellpose again, and produce masks. Take the final estimated size as the median diameter of the predicted masks.

For a 3D or 4D stack, the estimate comes from the Z plane on show in the viewer.

If this estimate is incorrect, set the diameter by hand.

With either version, you can also get an estimate from the image: create a
napari Shapes layer and draw circles or squares around cells, select it as
``shape layer`` and click ``compute diameter from shape layer``. The plugin
sets the diameter to the average diameter of the drawn shapes.

Resample dynamics
~~~~~~~~~~~~~~~~~~~~~~~~

The cellpose network is run on your rescaled image, where the rescaling factor is determined
by the diameter. For instance, if you have an image with 60 pixel diameter cells,
the rescaling factor is 30./60. = 0.5. After determining the flows (dX, dY, cellprob),
the model runs the dynamics. The dynamics can be run at the rescaled size
(``resample dynamics`` unchecked), or on the resampled, interpolated flows at the
true image size (``resample dynamics`` checked). Resampling creates smoother masks
when the cells are large but is slower.

Flow threshold
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Note there is nothing keeping the neural network from predicting
horizontal and vertical flows that do not correspond to any real
shapes at all. In practice, most predicted flows are consistent with
real shapes, because the network was only trained on image flows
that are consistent with real shapes, but sometimes when the network
is uncertain it may output inconsistent flows. To check that the
recovered shapes after the flow dynamics step are consistent with
real masks, we recompute the flow gradients for these putative
predicted masks, and compute the mean squared error between them and
the flows predicted by the network.

``flow_threshold`` is the maximum allowed error of the flows for each mask
(default 0.4). Increase it if cellpose is not returning as many masks as
you'd expect. Decrease it if cellpose is returning too many ill-shaped masks.
Set it to 0 to turn the check off.

Cell probability threshold
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The network predicts 3 outputs: flows in X, flows in Y, and cell "probability".
The predictions the network makes of the probability are the inputs to a sigmoid
centered at zero (1 / (1 + e^-x)),
so they vary from around -6 to +6. The pixels greater than the
``cellprob_threshold`` are used to run dynamics and determine masks. The default
is ``cellprob_threshold=0.0``. Decrease this threshold if cellpose is not returning
as many masks as you'd expect. Similarly, increase this threshold if cellpose is
returning too many masks, particularly from dim areas.

After a segmentation, click ``recompute last masks with new cellprob`` to
recompute the masks with the current thresholds without running the network
again.

Min size
~~~~~~~~~~~~~~~~~~~~~~~~

Masks with fewer pixels than ``min size (px)`` are removed (default 15).

3D settings
~~~~~~~~~~~~~~~~~~~~~~~~

See :doc:`running` for ``process stack as 3D``, ``stitch threshold slices``
and the axis selectors.

.. _docs: https://cellpose.readthedocs.io/en/latest/settings.html
.. _issue: https://github.com/DBI-INFRA/napari-cellposesam/issues
