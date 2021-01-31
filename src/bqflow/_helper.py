import math
from pathlib import Path
from typing import Optional, TypeVar


def convert_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def mkdir_if_not_exists(path: Path):
    if path.parent.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)


T = TypeVar("T")


def ifnull(x: Optional[T], default: T) -> T:
    return x if x is not None else default
