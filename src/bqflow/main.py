import json
import logging
from pathlib import Path
from typing import Optional

import click
from abq import QueryException

from bqflow import env
from bqflow.client import Client
from bqflow.fields import Workflow
from bqflow.load import read_workflow
from bqflow.procon import ProCon

logging.basicConfig(level=logging.CRITICAL)


@click.command()
@click.argument("file_path")
@click.option("--project", "-P", help="プロジェクトID")
@click.option("--output", "-o", help="アウトプットパス")
@click.option("--entrypoint", help="entrypoint上書き")
def cmd(
    file_path: str,
    project: Optional[str],
    output: Optional[str],
    entrypoint: Optional[str],
):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"{file_path}は存在しません")

    if project is None:
        project = read_project_id_from_credential()
    if project is None:
        raise RuntimeError("credentialからproject_idが見つかりませんでした. -Pオプションで指定してください")

    if path.suffix == ".sql":
        try:
            run_query(path, project_id=project, output=output)
        except QueryException as e:
            print(e)
            return exit(1)
    elif path.suffix in [".yml", ".yaml"]:
        wf = read_workflow(path)
        if entrypoint is not None:
            wf.entrypoint = entrypoint
        execute_workflow(wf, project)


def read_project_id_from_credential():
    with open(env.GOOGLE_APPLICATION_CREDENTIALS, "r") as f:
        dic = json.load(f)
        return dic.get("project_id")


def run_query(path: Path, project_id: Optional[str], output: Optional[str]):
    client = Client(project_id)
    client.execute_query(Path(path), output=Path(output))


def execute_workflow(wf: Workflow, project: str):
    procon = ProCon(wf=wf, project_name=project, max_size=10)
    reports = procon.run()
    print(reports)
