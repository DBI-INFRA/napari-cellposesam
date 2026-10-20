# napari-cellposesam <img src="docs/_static/favicon.ico" width="50" title="cellpose" alt="cellpose" align="right" vspace = "50">

[![Documentation Status](https://readthedocs.org/projects/napari-cellposesam/badge/?version=latest)](https://napari-cellposesam.readthedocs.io/en/latest/)
[![tests](https://github.com/jeskowagner/napari-cellposesam/actions/workflows/test_and_deploy.yml/badge.svg)](https://github.com/jeskowagner/napari-cellposesam/actions)
[![PyPI version](https://img.shields.io/pypi/v/napari-cellposesam)](https://pypi.org/project/napari-cellposesam/)
[![Python version](https://img.shields.io/pypi/pyversions/napari-cellposesam)](https://pypi.org/project/napari-cellposesam/)
[![License](https://img.shields.io/pypi/l/napari-cellposesam.svg?color=green)](https://github.com/jeskowagner/napari-cellposesam/raw/main/LICENSE)
[![website](https://img.shields.io/website?url=https%3A%2F%2Fwww.cellpose.org)](https://www.cellpose.org)

A [napari] plugin for cell segmentation with [cellpose], including Cellpose-SAM (cellpose 4).

This is a fork of [MouseLand/cellpose-napari](https://github.com/MouseLand/cellpose-napari), the original plugin by Carsen Stringer. It adds:

- support for Cellpose-SAM (`cpsam`) and Cellpose3 models in the same
  environment and UI
- z/channel axis selection for 3D and 4D images
- compatibility with new napari versions

The cellpose code was written by Carsen Stringer and Marius Pachitariu. To learn about Cellpose, read the [**paper**](https://t.co/kBMXmPp3Yn?amp=1) or watch this [**talk**](https://t.co/JChCsTD0SK?amp=1).

For problems with this plugin, open an [issue](https://github.com/jeskowagner/napari-cellposesam/issues). For problems with cellpose itself, open an [issue](https://github.com/MouseLand/cellpose/issues) on the cellpose repo.

If you use this plugin, please cite the [cellpose paper](https://www.nature.com/articles/s41592-020-01018-x), the Cellpose3 paper if you use the Cellpose3 models, and the Cellpose-SAM paper if you use the `cpsam` models (see the [cellpose repo](https://github.com/MouseLand/cellpose) for the references):

```bibtex
@article{stringer2021cellpose,
  title={Cellpose: a generalist algorithm for cellular segmentation},
  author={Stringer, Carsen and Wang, Tim and Michaelos, Michalis and Pachitariu, Marius},
  journal={Nature Methods},
  volume={18},
  number={1},
  pages={100--106},
  year={2021},
  publisher={Nature Publishing Group}
}
```

![napari-cellposesam segmenting the 2D sample image](https://raw.githubusercontent.com/jeskowagner/napari-cellposesam/main/docs/_static/gui.png)

## Installation

Requires Python 3.11 or newer. We recommend a fresh environment, e.g. with conda:

```
conda create -n napari-cellposesam python=3.12
conda activate napari-cellposesam
```

Install napari and the plugin with pip:

```
pip install "napari[all]" napari-cellposesam
```

Or install the plugin from the napari plugin manager (Plugins > Install/Uninstall Plugins).

To install the latest development version from GitHub:

```
pip install git+https://github.com/jeskowagner/napari-cellposesam
```

If you have issues installing cellpose, see the [cellpose installation docs](https://cellpose.readthedocs.io/en/latest/installation.html).

### Cellpose3 models

The plugin installs cellpose 4, which provides the Cellpose-SAM and CPDINO models. The Cellpose3 models (`cyto3`, `nuclei`, etc.) are in the same model list. They need cellpose 3, which the plugin offers to download the first time you run one. It downloads cellpose 3.1.1.3 into a private folder without touching the installed cellpose, and installs [numba](https://numba.pydata.org) if it is missing. The plugin then picks the right cellpose version for each model, including custom models.

The private copy is in `~/.cellpose/napari-cellposesam/cellpose-3.1.1.3-format1/_cellpose3` (`~` is your user folder, also on Windows). To keep it elsewhere, set the environment variable `NAPARI_CELLPOSESAM_CACHE` to a folder that then takes the place of `~/.cellpose/napari-cellposesam`. To reset it, delete `~/.cellpose/napari-cellposesam` (or the folder `NAPARI_CELLPOSESAM_CACHE` names): the plugin offers to download cellpose 3 again the next time you run a Cellpose3 model.

To run the same download ahead of time, so that napari never prompts:

```
python -m napari_cellposesam fetch-cellpose3
```

The download goes to the home folder of whoever runs the command. For an environment shared by several users, set `NAPARI_CELLPOSESAM_CACHE` to a shared folder, both when running the command and for everyone who uses the environment. Users only need read access to it.

Both need internet access and pip in the environment. If the environment has no pip, as in some uv-created ones, the plugin asks you to install it first.

Don't install `cellpose-napari` next to this plugin. It lists the Cellpose3
models, but with cellpose 4 installed it ignores the selected model and runs
Cellpose-SAM, thus breaking it.

### GPU

cellpose runs on CPU, NVIDIA GPUs (CUDA) and Apple silicon (MPS). The plugin uses a GPU automatically if torch can see one, for both the cellpose 4 and the Cellpose3 models.

- **Apple silicon:** nothing to do, the torch from PyPI supports MPS.
- **NVIDIA on Linux:** the torch from PyPI is a CUDA build, so it usually works as installed.
- **NVIDIA on Windows:** the torch from PyPI is CPU-only. Reinstall torch and torchvision together from the PyTorch index, with the CUDA version the [PyTorch selector](https://pytorch.org/get-started/locally/) gives for your driver, e.g.:

  ```
  pip install --force-reinstall --no-deps torch torchvision --index-url https://download.pytorch.org/whl/cu126
  ```

Check that torch sees the GPU:

```
python -c "import torch; print('cuda', torch.cuda.is_available(), 'mps', torch.backends.mps.is_available())"
```

### Optional: CPDINO models

The CPDINO models need [DINOv3](https://github.com/facebookresearch/dinov3), which is not on PyPI and so is not installed automatically. The plugin offers to install it when you run segmentation with a CPDINO model, or install it yourself:

```
pip install git+https://github.com/facebookresearch/dinov3
```

Without it, cellpose logs a `Could not import CPDINO` warning on startup. This is harmless if you don't use those models.

### Upgrading

```
pip install --upgrade napari-cellposesam cellpose
```

If you installed a CUDA build of torch, upgrade torch the same way you installed it, or pip may replace it with the CPU-only build.

Coming from 0.1.x with a separate cellpose 3 environment (`cellpose<4`): from 0.2.0 that environment is no longer needed, since one environment runs both the Cellpose3 and the cellpose 4 models. Upgrading it with the command above moves it to cellpose 4, and the plugin downloads cellpose 3 the first time you run a Cellpose3 model.

## Usage

Open napari with the plugin docked:

```
napari -w napari-cellposesam
```

Sample data is available under File > Open Sample > napari-cellposesam.

Detailed usage is described in the [documentation](https://napari-cellposesam.readthedocs.io/).

## Contributing

Contributions are welcome. For development, clone the repo and install it in editable mode with the test dependencies:

```
pip install -e ".[testing]"
pytest
```

## License

Distributed under the terms of the [BSD-3] license, "napari-cellposesam" is free and open source software.

## Dependencies

napari-cellposesam relies on:
- [napari](https://napari.org)
- [magicgui](https://napari.org/magicgui/)
- [cellpose], which in turn uses [torch](https://pytorch.org/), [numpy](https://numpy.org/), [scipy](https://scipy.org/), [opencv](https://opencv.org/) and others
- [numba](https://numba.pydata.org), which the plugin installs the first time you run a Cellpose3 model

[napari]: https://github.com/napari/napari
[cellpose]: https://github.com/MouseLand/cellpose
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
