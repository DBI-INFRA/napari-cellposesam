# napari-cellposesam <img src="docs/_static/favicon.ico" width="50" title="cellpose" alt="cellpose" align="right" vspace = "50">

[![Documentation Status](https://readthedocs.org/projects/napari-cellposesam/badge/?version=latest)](https://napari-cellposesam.readthedocs.io/en/latest/)
[![tests](https://github.com/jeskowagner/napari-cellposesam/actions/workflows/test_and_deploy.yml/badge.svg)](https://github.com/jeskowagner/napari-cellposesam/actions)
[![PyPI version](https://img.shields.io/pypi/v/napari-cellposesam)](https://pypi.org/project/napari-cellposesam/)
[![Python version](https://img.shields.io/pypi/pyversions/napari-cellposesam)](https://pypi.org/project/napari-cellposesam/)
[![License](https://img.shields.io/pypi/l/napari-cellposesam.svg?color=green)](https://github.com/jeskowagner/napari-cellposesam/raw/main/LICENSE)
[![website](https://img.shields.io/website?url=https%3A%2F%2Fwww.cellpose.org)](https://www.cellpose.org)

A [napari] plugin for cell segmentation with [cellpose], including Cellpose-SAM (cellpose v4).

This is a fork of [MouseLand/cellpose-napari](https://github.com/MouseLand/cellpose-napari), the original plugin by Carsen Stringer. It adds:

- support for cellpose v4 and the Cellpose-SAM (`cpsam`) models, while still working with cellpose v3
- z/channel axis selection for 3D and 4D images
- compatibility with new napari versions

The cellpose code was written by Carsen Stringer and Marius Pachitariu. To learn about Cellpose, read the [**paper**](https://t.co/kBMXmPp3Yn?amp=1) or watch this [**talk**](https://t.co/JChCsTD0SK?amp=1).

For problems with this plugin, open an [issue](https://github.com/jeskowagner/napari-cellposesam/issues). For problems with cellpose itself, open an [issue](https://github.com/MouseLand/cellpose/issues) on the cellpose repo.

If you use this plugin, please cite the [cellpose paper](https://www.nature.com/articles/s41592-020-01018-x), and the Cellpose-SAM paper if you use the `cpsam` models (see the [cellpose repo](https://github.com/MouseLand/cellpose) for the reference):

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

### GPU

cellpose runs on CPU, NVIDIA GPUs (CUDA) and Apple silicon (MPS). For CUDA, install a CUDA build of torch following the [PyTorch instructions](https://pytorch.org/get-started/locally/) before or after installing the plugin. The plugin uses the GPU automatically if torch can see one.

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

[napari]: https://github.com/napari/napari
[cellpose]: https://github.com/MouseLand/cellpose
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
