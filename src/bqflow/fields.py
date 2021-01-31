"""yamlに書けるfieldの設定

以下を参考にしている
https://argoproj.github.io/argo/fields/#workflowstep
"""

from collections import Counter
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, root_validator, validator

Primitive = Literal[
    "STRING",
    "BYTES",
    "NUMERIC",
    "INT64",
    "FLOAT64",
    "DATE",
    "DATETIME",
    "TIMESTAMP",
    "TIME",
    "BOOL",
    "GEOGRAPHY",
]

Array = Literal[
    "ARRAY<STRING>",
    "ARRAY<BYTES>",
    "ARRAY<NUMERIC>",
    "ARRAY<INT64>",
    "ARRAY<FLOAT64>",
    "ARRAY<DATE>",
    "ARRAY<DATETIME>",
    "ARRAY<TIMESTAMP>",
    "ARRAY<TIME>",
    "ARRAY<BOOL>",
    "ARRAY<GEOGRAPHY>",
    "ARRAY<STRUCT>",
]


class ExtraForbid(BaseModel):
    class Config:
        extra = "forbid"


class Parameter(ExtraForbid):
    name: str
    default: Optional[str]
    type: Optional[Union[Primitive, Array, Literal["STRUCT"]]]
    value: Any


class Argument(ExtraForbid):
    parameters: list[Parameter] = []


class Inputs(ExtraForbid):
    parameters: list[Parameter] = []


class DAGTask(ExtraForbid):
    name: str
    template: Optional[str]
    dependencies: list[str] = []
    arguments: Argument = Argument()


class DAGTemplate(ExtraForbid):
    tasks: list[DAGTask]


class Step(ExtraForbid):
    name: str
    template: Optional[str]
    arguments: Argument = Argument()


class Template(ExtraForbid):
    name: str
    script: Optional[Path]
    run: Optional[str]
    inputs: Inputs = Inputs()
    steps: Optional[list[list[Step]]]
    dag: Optional[DAGTemplate]

    @property
    def type(self) -> Literal["steps", "dag", "script", "run"]:
        if self.script is not None:
            return "script"
        if self.steps is not None:
            return "steps"
        if self.dag is not None:
            return "dag"
        if self.run is not None:
            return "run"
        raise TypeError("Templateがscript, steps, dagのいずれでもありません")

    @root_validator
    def validate_type(cls, values):
        name = values.get("name")
        conds = [
            values.get("steps") is None,
            values.get("dag") is None,
            values.get("script") is None,
            values.get("run") is None,
        ]
        if not conds.count(False):
            raise ValueError(f"script, steps, dagのいずれかひとつを指定してください [Teplate: {name}]")
        return values


class Workflow(ExtraForbid):
    """ワークフロー定義yamlのデータ構造

    制約:
        - templateに存在しないnameをentrypointで指定してはならない
        - templatesのnameはユニークでなければならない
        - stepまたはdagで存在しないtemplate nameを指定してはならない
    """

    entrypoint: str
    arguments: Argument = Argument()
    templates: list[Template] = []

    @root_validator
    def check_entrypoint(cls, values):
        entrypoint, templates = values.get("entrypoint"), values.get("templates")
        if entrypoint not in [t.name for t in templates]:
            raise ValueError(f"templatesに存在しないnameがentrypointで指定されました {entrypoint}")
        return values

    @validator("templates")
    def unique_name(tmps: list[Template]):
        names = [v.name for v in tmps]
        unames = set([k for k, v in Counter(names).items() if v > 1])
        if len(unames) > 0:
            raise ValueError(f"templatesのnameに重複があります {unames}")

        refs = []
        for tmp in tmps:
            if tmp.steps is not None:
                for step in tmp.steps:
                    refs += [s.template for s in step if s.template is not None]
            elif tmp.dag is not None:
                refs += [t.template for t in tmp.dag.tasks if t.template is not None]

        sub = set(refs) - set(names)
        if len(sub) > 0:
            raise ValueError(f"templatesに存在しないtemplateがstepまたはtaskで参照されています {sub}")

        return tmps

    def get_template(self, name: str) -> Template:
        """nameに一致するtemplateを返す

        Args:
            name (str): template名

        Returns:
            Template: テンプレート
        """
        return next(filter(lambda x: x.name == name, self.templates), None)

    def get_entrypoint(self) -> Template:
        return self.get_template(self.entrypoint)
