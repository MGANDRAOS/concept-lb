from pydantic import BaseModel
from typing import List, Dict


class RiskFlag(BaseModel):
    code: str
    severity: str
    title: str
    message: str


class RiskReport(BaseModel):
    risk_level: str
    risk_score: int
    dimension_scores: Dict[str, float]
    flags: List[RiskFlag]