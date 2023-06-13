import os
import shutil

from src.privateer import cli
from src.privateer.config import PrivateerConfig


def test_backup():
    cfg = PrivateerConfig("config")
    test = cfg.get_host("test")
    made_dir = False
    if not os.path.exists(test.path):
        os.mkdir(test.path)
        made_dir = True
    try:
        res = cli.main(["backup", "config", "--to=test"])
        assert res == "Backed up targets 'orderly_volume', 'another_volume' to host 'test'"
        assert os.path.isfile(os.path.join(test.path, "orderly_volume.tar"))
        assert os.path.isfile(os.path.join(test.path, "another_volume.tar"))
    finally:
        if made_dir:
            shutil.rmtree(test.path)