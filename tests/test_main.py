import pytest
from napari_cellposesam.__main__ import main


def test_fetch_cpsam(monkeypatch, capsys):
    from cellpose import models

    monkeypatch.setattr(models, 'cache_model_path', lambda name: f'/models/{name}')
    assert main(['fetch-cpsam']) == 0
    assert capsys.readouterr().out == 'the Cellpose-SAM model is in /models/cpsam\n'

    def offline(name):
        raise OSError('no network')

    monkeypatch.setattr(models, 'cache_model_path', offline)
    with pytest.raises(SystemExit) as exit_:
        main(['fetch-cpsam'])
    assert exit_.value.code == 1
    assert 'no network' in capsys.readouterr().err
