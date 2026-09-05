from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    session_id: str
    separator: str


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    file_kind: str
    encoding: str
    detected_separator: Optional[str] = None
    available_separators: list[str] = []
    raw_preview: list[str] = []
    already_parsed: bool = False


class ParseResponse(BaseModel):
    session_id: str
    separator: Optional[str]
    n_rows: int
    n_columns: int
    columns: list[str]
    column_types: dict[str, str]


# --- Visualisations (Phase 2) ------------------------------------------------

Plot1DType = Literal["histogram", "box", "violin", "kde", "bar", "pie"]
Plot2DType = Literal["scatter", "line", "heatmap", "hexbin", "bar_grouped", "bubble"]
Plot3DType = Literal["scatter3d", "surface"]


class Plot1DRequest(BaseModel):
    session_id: str
    column: str
    plot_type: Plot1DType
    group_by: Optional[str] = None
    bins: int = 20
    title: Optional[str] = None


class Plot2DRequest(BaseModel):
    session_id: str
    plot_type: Plot2DType
    x: Optional[str] = None
    y: Optional[str] = None
    color_by: Optional[str] = None
    size_by: Optional[str] = None
    columns: Optional[list[str]] = None  # utilisé par 'heatmap' (sous-ensemble de colonnes numériques)
    bins: int = 30  # utilisé par 'hexbin'
    title: Optional[str] = None


class Plot3DRequest(BaseModel):
    session_id: str
    plot_type: Plot3DType
    x: str
    y: str
    z: str
    color_by: Optional[str] = None
    title: Optional[str] = None


class ExportPlotRequest(BaseModel):
    session_id: str
    kind: Literal["1d", "2d", "3d"]
    params: dict
    format: Literal["png", "svg", "html"]
    width: int = 900
    height: int = 600


# --- Filtrage & Colonnes calculées (Phase 3) ---------------------------------

class FilterCondition(BaseModel):
    type: Literal["condition"] = "condition"
    column: str
    operator: str
    value: Optional[Any] = None


class FilterGroup(BaseModel):
    type: Literal["group"] = "group"
    logic: Literal["AND", "OR"] = "AND"
    conditions: list["FilterNode"] = []


FilterNode = Annotated[Union[FilterCondition, FilterGroup], Field(discriminator="type")]
FilterGroup.model_rebuild()


class ApplyFilterRequest(BaseModel):
    filter: Optional[FilterNode] = None


class CreateColumnRequest(BaseModel):
    name: str
    formula: str
    overwrite: bool = False
    preview_only: bool = False
    preview_rows: int = 10
