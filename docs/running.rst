Running plugin
-------------------------------

You can drag and drop a variety of images into napari. 
You can also open a folder of images to process together 
(or sequentially). See napari `image`_ documentation for more 
advanced image loading.

2D images
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is an example of the plugin running on the 2D sample image.

.. image:: _static/napari_main_demo_fast_small.gif
    :width: 1200px
    :align: center
    :alt: 3D_demo

Batch processing in 2D
~~~~~~~~~~~~~~~~~~~~~~~~~~

Cellpose will process all images in an opened folder with the same settings 
and return masks for each image with the name ``folder_name_fileid``. You can 
export all the images in the napari File menu.

Here is an example of the plugin running on a folder of 2D data.

.. image:: _static/napari_batch_demo_fast_small.gif
    :width: 1200px
    :align: center
    :alt: time_series_demo


3D segmentation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Cellpose can segment 3D and 4D stacks. ``process stack as 3D`` is checked
automatically when you select a 3D or 4D image; uncheck it to segment each
slice in 2D instead.

With cellpose v4, the widget shows ``z axis`` and ``channel axis`` selectors
for 3D and 4D images. If the napari layer has axis labels ``z`` and ``c``,
they are used as defaults. For a 3D image, set ``channel axis`` to
``none (ZYX)`` if all three axes are spatial. With cellpose v3, label the
channel axis of a 4D image with ``c`` instead.

If the 3D segmentation is not working well and there is inhomogeneity in Z, try stitching 
masks using the ``stitch threshold slices`` option
instead of checking ``process stack as 3D``. In this setting, 
cellpose will create masks in 2D on each XY slice and then stitch them across 
slices if the IoU between the mask on the current slice and the next slice is 
greater than or equal to the ``stitch threshold slices``. 

Here is an example of the plugin running on the 3D sample image.

.. image:: _static/napari_3d_demo_fast_small.gif
    :width: 1200px
    :align: center
    :alt: 3D_demo

Time segmentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Stitching can also be applied in time by setting ``stitch threshold slices``>0.

Here is an example of the plugin running on cell tracking challenge data.

.. image:: _static/napari_time_demo_fast_small.gif
    :width: 1200px
    :align: center
    :alt: time_series_demo


.. _image: https://napari.org/stable/howtos/layers/image.html
