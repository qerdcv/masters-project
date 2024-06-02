import os
import pathlib

TMP_PATH = '/tmp'

# create directory in the /tmp (mostly for cache purposes)
def make_temp_dir(name) -> pathlib.Path:
    path = pathlib.Path(os.path.join(TMP_PATH, name))
    if path.exists():
        return path

    os.mkdir(path)
    return path
