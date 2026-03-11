from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RuleCreate(BaseModel):
    name:        str
    description: Optional[str] = None
    clause_id:   int
    severity:    str
    logic_json:  dict                      # JSONB — send as a JSON object, not a string
    version:     str = "1.0"


class RuleUpdate(BaseModel):
    name:        Optional[str]  = None
    description: Optional[str]  = None
    severity:    Optional[str]  = None
    logic_json:  Optional[dict] = None    # JSONB
    status:      Optional[str]  = None


class RuleOut(BaseModel):
    id:          int
    name:        str
    description: Optional[str]
    severity:    str
    status:      str
    version:     str
    logic_json:  dict                     # returned as a JSON object
    clause_id:   int
    created_at:  datetime
    model_config = {"from_attributes": True}
