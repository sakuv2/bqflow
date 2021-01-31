from pathlib import Path

import yaml

from bqflow.fields import Workflow


def read_workflow(path: Path):
    with open(path, "r") as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
    return Workflow.parse_obj(data)
