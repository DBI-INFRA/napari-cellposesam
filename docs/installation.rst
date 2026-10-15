Installation
------------------------------

napari-cellposesam requires Python 3.11 or newer. We recommend installing it
into a fresh environment, e.g. with conda:

::

   conda create -n napari-cellposesam python=3.12
   conda activate napari-cellposesam
   pip install "napari[all]" napari-cellposesam

You can also install the plugin from inside napari with the plugin manager
(Plugins > Install/Uninstall Plugins).

To install the latest development version from GitHub:

::

   pip install git+https://github.com/jeskowagner/napari-cellposesam

For full napari install instructions, see the napari `install`_ docs.
For full cellpose install instructions, see the cellpose `installation docs`_.

GPU
~~~~~~~~~~~~~~~~~~~~~~~

cellpose runs on CPU, NVIDIA GPUs (CUDA) and Apple silicon (MPS). The plugin
uses a GPU automatically if torch can see one. For CUDA, install a CUDA build
of torch following the `PyTorch`_ instructions.

On CPU the plugin runs Cellpose-SAM in fp32, which is much faster than bf16
on CPUs without native bf16 support. On GPU it uses bf16.

CPDINO models
~~~~~~~~~~~~~~~~~~~~~~~

The CPDINO models need `DINOv3`_, which is not on PyPI and so is not installed
automatically. The plugin offers to install it when you run segmentation with
a CPDINO model, or you can install it yourself:

::

   pip install git+https://github.com/facebookresearch/dinov3

If DINOv3 was installed while napari was running, restart napari before
using a CPDINO model. Without DINOv3, cellpose logs a
``Could not import CPDINO`` warning on startup, which is harmless if you
don't use those models.

Common issues
~~~~~~~~~~~~~~~~~~~~~~~

If you have errors related to OpenMP and libiomp5, then try

::

   conda install nomkl

If you receive the error: ``ImportError: _arpack DLL load failed``, then try
uninstalling and reinstalling scipy:

::

   pip uninstall scipy
   pip install scipy

If installation fails or the plugin doesn't load, please open an `issue`_.

.. _install: https://napari.org/stable/tutorials/fundamentals/installation.html
.. _installation docs: https://cellpose.readthedocs.io/en/latest/installation.html
.. _PyTorch: https://pytorch.org/get-started/locally/
.. _DINOv3: https://github.com/facebookresearch/dinov3
.. _issue: https://github.com/jeskowagner/napari-cellposesam/issues
