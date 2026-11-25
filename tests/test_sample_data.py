import pathlib
import zipfile

from napari_cellposesam import _sample_data

SAMPLES = ('data/2D/rgb_2D_tif.tif', 'data/3D/rgb_3D.tif')


def test_missing_data_folder_is_extracted_again(tmp_path, monkeypatch):
    def no_download(*args):
        raise AssertionError('the zip is there, nothing should download')

    monkeypatch.setattr(pathlib.Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('cellpose.utils.download_url_to_file', no_download)
    (tmp_path / '.cellpose').mkdir()
    with zipfile.ZipFile(tmp_path / '.cellpose' / 'data.zip', 'w') as zip_file:
        for name in SAMPLES:
            zip_file.writestr(name, b'')

    data_dir = _sample_data._get_data_dir()
    assert data_dir == tmp_path / '.cellpose' / 'data'
    assert all((tmp_path / '.cellpose' / name).exists() for name in SAMPLES)
