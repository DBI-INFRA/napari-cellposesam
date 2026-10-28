Installation
------------------------------

Installer
~~~~~~~~~~~~~~~~~~~~~~~

The installer sets up napari and the plugin in a folder of their own, with the
PyTorch build that fits your GPU (NVIDIA, AMD on Linux, Apple silicon, or
CPU), and adds a desktop and app menu shortcut. It needs no Python or conda,
but needs an internet connection while it runs.

On Windows, download ``napari-cellposesam-setup.exe`` from the `releases`_, or
run in PowerShell:

::

   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/installer/install.ps1 | iex"

The setup is not code-signed, so Windows may show "Windows protected your PC"
when you start it: click **More info**, then **Run anyway**. The PowerShell
command installs the same without that warning.

On macOS and Linux, run in a terminal:

::

   curl -LsSf https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/installer/install.sh | sh

The installer offers to download the Cellpose-SAM model right away (a tick
box in the Windows setup, a question in the terminal); otherwise napari
downloads it the first time you segment. The model goes to
``~/.cellpose/models``, where any cellpose install finds it, so uninstalling
keeps it.

Run it again to update. To uninstall, use the Windows Apps settings if you
installed with the setup, or run:

::

   # macOS, Linux
   curl -LsSf https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/installer/install.sh | sh -s -- --uninstall
   # Windows PowerShell
   $env:NAPARI_CELLPOSESAM_UNINSTALL = 1; irm https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/installer/install.ps1 | iex

The top of each script lists the environment variables that set the install
folder, the plugin version and the PyTorch build.

To add the same shortcut for napari-cellposesam in an environment of your own,
run ``python -m napari_cellposesam shortcut`` in it.

pip
~~~~~~~~~~~~~~~~~~~~~~~

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

Cellpose3 models
~~~~~~~~~~~~~~~~~~~~~~~

The plugin installs cellpose 4, which provides the Cellpose-SAM and CPDINO
models. The Cellpose3 models (``cyto3``, ``nuclei``, etc.) are in the same
model list. They need cellpose 3, which the plugin offers to download the
first time you run one. It downloads cellpose 3.1.1.3 into a private folder
without touching the installed cellpose, and installs `numba`_ if it is
missing. The plugin then picks the right cellpose version for each model,
including custom models.

The private copy is in
``~/.cellpose/napari-cellposesam/cellpose-3.1.1.3-format1/_cellpose3``
(``~`` is your user folder, also on Windows). To keep it elsewhere, set the
environment variable ``NAPARI_CELLPOSESAM_CACHE`` to a folder that then takes
the place of ``~/.cellpose/napari-cellposesam``. To reset it, delete
``~/.cellpose/napari-cellposesam`` (or the folder ``NAPARI_CELLPOSESAM_CACHE``
names): the plugin offers to download cellpose 3 again the next time you run
a Cellpose3 model.

To run the same download ahead of time, so that napari never prompts:

::

   python -m napari_cellposesam fetch-cellpose3

The download goes to the home folder of whoever runs the command. For an
environment shared by several users, set ``NAPARI_CELLPOSESAM_CACHE`` to a
shared folder, both when running the command and for everyone who uses the
environment. Users only need read access to it.

Both need internet access and pip in the environment. If the environment has
no pip, as in some uv-created ones, the plugin asks you to install it first.

Don't install ``cellpose-napari`` next to this plugin. It lists the Cellpose3
models, but with cellpose 4 installed it ignores the selected model and runs
Cellpose-SAM, thus breaking it.

GPU
~~~~~~~~~~~~~~~~~~~~~~~

cellpose runs on CPU, NVIDIA GPUs (CUDA) and Apple silicon (MPS). The plugin
uses a GPU automatically if torch can see one, for both the cellpose 4 and
the Cellpose3 models.

- Apple silicon: nothing to do, the torch from PyPI supports MPS.
- NVIDIA on Linux: the torch from PyPI is a CUDA build, so it usually works
  as installed.
- NVIDIA on Windows: the torch from PyPI is CPU-only. Reinstall torch and
  torchvision together from the PyTorch index, with the CUDA version the
  `PyTorch`_ selector gives for your driver, e.g.:

::

   pip install --force-reinstall --no-deps torch torchvision --index-url https://download.pytorch.org/whl/cu126

Check that torch sees the GPU:

::

   python -c "import torch; print('cuda', torch.cuda.is_available(), 'mps', torch.backends.mps.is_available())"

When upgrading, upgrade torch the same way you installed it, or pip may
replace a CUDA build with the CPU-only one.

On CPU the plugin runs the cellpose 4 models in fp32, which is much faster
than bf16 on CPUs without native bf16 support. On GPU it uses bf16. The
Cellpose3 models always run in fp32.

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

.. _releases: https://github.com/jeskowagner/napari-cellposesam/releases
.. _install: https://napari.org/stable/tutorials/fundamentals/installation.html
.. _installation docs: https://cellpose.readthedocs.io/en/latest/installation.html
.. _PyTorch: https://pytorch.org/get-started/locally/
.. _DINOv3: https://github.com/facebookresearch/dinov3
.. _numba: https://numba.pydata.org
.. _issue: https://github.com/jeskowagner/napari-cellposesam/issues
