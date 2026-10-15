napari-cellposesam
===============================================================

napari-cellposesam is a napari plugin for cell segmentation with cellpose,
including Cellpose-SAM (cellpose v4). It also works with cellpose v3.

It is a fork of `cellpose-napari`_, the original plugin by Carsen Stringer.
The source code is on `GitHub`_.

.. image:: _static/gui.PNG
    :width: 1200px
    :align: center
    :alt: plugin

Please see the cellpose `documentation`_ for more information on the
algorithm and the settings.

If you use this plugin please cite the cellpose paper, and the Cellpose-SAM
paper if you use the ``cpsam`` models (see the cellpose `repo`_ for the reference):
::

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


.. _documentation: https://cellpose.readthedocs.io
.. _repo: https://github.com/MouseLand/cellpose
.. _cellpose-napari: https://github.com/MouseLand/cellpose-napari
.. _GitHub: https://github.com/jeskowagner/napari-cellposesam


.. toctree::
   :maxdepth: 3
   :caption: Basics:

   installation
   running
   settings
