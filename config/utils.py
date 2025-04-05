import os
from typing import List, Union


def makefile(filepath: Union[str, List[str]]):
    paths = [filepath] if isinstance(filepath, str) else filepath

    for path in paths:
        if not os.path.isfile(path):
            dir_path = os.path.dirname(path)
            if os.path.isdir(dir_path):
                open(path, "w").close()
                print(f"{os.path.basename(path)} created.")
            else:
                print(f"Directory for '{path}' does not exist. Skipping file creation.")
        else:
            pass
