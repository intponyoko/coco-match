from datetime import date
from types import UnionType
from typing import Any, Iterable, get_args, get_origin, get_type_hints

import pandas as pd
import pandera.pandas as pa


# Base
class BaseModel(pa.DataFrameModel):
    @classmethod
    def columns(cls) -> list[str]:
        return list(cls.to_schema().columns)

    @classmethod
    def data_frame(cls, rows: Iterable[dict]) -> pd.DataFrame:
        return cls.validate(pd.DataFrame(list(rows), columns=cls.columns()))

    @classmethod
    def row_json_schema(cls) -> dict[str, Any]:
        hints = get_type_hints(cls)
        properties = {
            name: cls._json_schema_for_annotation(annotation)
            for name, annotation in hints.items()
            if name != "Config"
        }
        required = list(properties.keys())
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    @classmethod
    def _json_schema_for_annotation(cls, annotation: Any) -> dict[str, Any]:
        origin = get_origin(annotation)
        if origin in (list, tuple):
            args = get_args(annotation)
            item_annotation = args[0] if args else Any
            return {
                "type": "array",
                "items": cls._json_schema_for_annotation(item_annotation),
            }
        if origin in (dict,):
            return {"type": "object"}
        if origin in (UnionType,):
            return cls._json_schema_for_union(get_args(annotation))
        if origin is not None and str(origin) == "typing.Union":
            return cls._json_schema_for_union(get_args(annotation))
        if annotation is str:
            return {"type": "string"}
        if annotation is int:
            return {"type": "integer"}
        if annotation is float:
            return {"type": "number"}
        if annotation is bool:
            return {"type": "boolean"}
        if annotation is date:
            return {"type": "string", "format": "date"}
        return {"type": "object"}

    @classmethod
    def _json_schema_for_union(cls, args: tuple[Any, ...]) -> dict[str, Any]:
        non_null_args = [arg for arg in args if arg is not type(None)]
        nullable = len(non_null_args) != len(args)
        if len(non_null_args) == 1:
            schema = cls._json_schema_for_annotation(non_null_args[0])
            if nullable:
                schema = {**schema, "nullable": True}
            return schema
        return {"type": "object", "nullable": nullable}

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        coerce = True


class BaseAxis(BaseModel):
    code: str

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        unique = ["code"]


# Time Axis
class FiscalPeriod(BaseAxis):
    # Use the Python date type here because type checkers treat pa.Date as a
    # runtime Pandera dtype, not as a valid annotation type.
    start: date
    end: date


# HR Axis
class Department(BaseAxis):
    name: str


class Title(BaseAxis):
    name: str
    price: int


class Staff(BaseAxis):
    name: str
    department_code: str
    title_code: str


# Skill Axis
class Skill(BaseAxis):
    name: str
    max_level: int


class Role(BaseAxis):
    name: str


class RoleSkill(BaseModel):
    role_code: str
    skill_code: str
    skill_level: int
    required: bool

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        unique = ["role_code", "skill_code"]


# PJ Axis
class Industry(BaseAxis):
    name: str


class Account(BaseAxis):
    name: str
    industry_code: str
    segment: str
    revenue_potential: int


class Solution(BaseAxis):
    name: str
