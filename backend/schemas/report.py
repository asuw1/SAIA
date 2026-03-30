from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ReportRequest(BaseModel):
    title: str
    framework: str = "ALL"                 # NCA | SAMA | CST | IA | ALL
    date_from: datetime
    date_to: datetime
    export_format: str = "pdf"             # pdf | csv | json


class ReportOut(BaseModel):
    id: int
    title: str
    framework: Optional[str]
    date_from: datetime
    date_to: datetime
    export_format: str
    events_count: int
    violations_count: int
    created_at: datetime
    model_config = {"from_attributes": True}
