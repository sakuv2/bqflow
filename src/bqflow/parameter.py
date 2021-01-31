from typing import Union

from google.cloud.bigquery import ArrayQueryParameter, ScalarQueryParameter, StructQueryParameter

from bqflow.fields import Parameter

BQParameter = Union[ArrayQueryParameter, ScalarQueryParameter, StructQueryParameter]


def parse_param(param: Parameter) -> BQParameter:
    value = param.value
    if isinstance(value, list):
        if param.type == "STRUCT":
            return StructQueryParameter(param.name, *[parse_param(Parameter(**p)) for p in value])
        elif param.type == "ARRAY<STRUCT>":
            value = [
                StructQueryParameter("_", *[parse_param(Parameter(**p)) for p in v]) for v in value
            ]
        array_type = param.type.strip("ARRAY<").strip(">")
        return ArrayQueryParameter(param.name, array_type, value)
    else:
        return ScalarQueryParameter(param.name, param.type, param.value)
