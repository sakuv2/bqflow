from __future__ import annotations

from pydantic import BaseModel

from bqflow.fields import Parameter
from bqflow.parameter import parse_param


class Query(BaseModel):
    name: list[str]
    sql: str
    parameters: list[Parameter]

    @property
    def bq_parameters(self):
        return [parse_param(p) for p in self.parameters]
