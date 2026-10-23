Running plugin
-------------------------------

You can drag and drop a variety of images into napari. See the napari
`image`_ documentation for more advanced image loading.

2D images
~~~~~~~~~~~~~~~~~~~~~~~~~~

Select an image layer, pick a model and click ``run segmentation``. The
plugin adds masks, outlines, cell probability and flow layers. To try it out,
open a sample image from File > Open Sample > napari-cellposesam.

.. image:: _static/gui.png
    :width: 1200px
    :align: center
    :alt: napari-cellposesam segmenting the 2D sample image

2D images with channels in separate layers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Cellpose can use several channels of an image. If your channels are open as
separate layers, select them and choose Merge to Stack from the layer context
menu. Select the merged layer and set ``channel axis`` to ``0``, which sets
``z axis`` to ``none`` and unchecks ``process stack as 3D``. Cellpose then
segments the layer as one 2D image with channels and adds one set of result
layers. A layer whose axis labels already mark a ``c`` axis gets these settings
automatically. This needs a cellpose 4 model.

Batch processing in 2D
~~~~~~~~~~~~~~~~~~~~~~~~~~

To process several same-sized 2D images together, open them with
File > Open Files as Stack, which loads them into one layer. Uncheck ``process stack as 3D`` and cellpose segments each image in 2D with
the same settings, adding a separate set of result layers per image. You can
export the results from the napari File menu.

3D segmentation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Cellpose can segment 3D and 4D stacks. ``process stack as 3D`` is checked
automatically when you select a 3D or 4D image; uncheck it to segment each
slice in 2D instead.

With cellpose 4 models, the widget shows ``z axis`` and ``channel axis`` selectors
for 3D and 4D images. If the napari layer has axis labels ``z`` and ``c``,
they are used as defaults. For a 3D image, set ``channel axis`` to
``none (ZYX)`` if all three axes are spatial; a channel axis makes it a 2D image
with channels (see above). With Cellpose3 models, label the
channel axis of a 4D image with ``c`` instead.

For 3D segmentation the plugin takes the voxel spacing from the layer's scale,
which many readers set from the file and which you can set in the napari console,
e.g. ``viewer.layers['stack'].scale = (2, 0.5, 0.5)``. If Z is sampled differently
from Y and X, the plugin passes the ratio to cellpose as ``anisotropy``, and cellpose
resamples Z to match before segmenting.

If the 3D segmentation is not working well and there is inhomogeneity in Z, try stitching 
masks using the ``stitch threshold slices`` option
instead of checking ``process stack as 3D``. In this setting, 
cellpose will create masks in 2D on each XY slice and then stitch them across 
slices if the IoU between the mask on the current slice and the next slice is 
greater than or equal to the ``stitch threshold slices``. 

A 3D sample is available under File > Open Sample > napari-cellposesam.

Time segmentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Stitching can also be applied in time by setting ``stitch threshold slices``>0.

.. _image: https://napari.org/stable/howtos/layers/image.html
