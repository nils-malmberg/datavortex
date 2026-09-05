from typing import Optional

from pydantic import BaseModel


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
