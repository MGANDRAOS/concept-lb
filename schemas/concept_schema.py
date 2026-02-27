from typing import List, Literal, Optional
from pydantic import BaseModel, Field


NeighborhoodType = Literal["mall", "street", "residential", "business", "seaside"]
ServiceModel = Literal["dine_in", "qsr", "hybrid"]
PricePositioning = Literal["affordable", "mid", "premium"]
BeverageDirection = Literal["coffee_focus", "mocktails", "full_bar", "juice_bar"]
OwnershipStructure = Literal["solo", "partners"]
BudgetTier = Literal["starter", "mid", "premium"]
ExperienceLevel = Literal["new", "some", "expert"]
Language = Literal["en"]  # MVP: English only


class InferenceLogItem(BaseModel):
    field: str
    inferred: bool = True
    rationale: str


class ConceptObject(BaseModel):
    language: Language = "en"

    concept_name: str
    one_liner: str
    cuisine_type: str
    service_model: ServiceModel
    differentiator: str

    country: str = "Lebanon"
    city: str
    neighborhood_type: NeighborhoodType

    size_sqm: float = Field(..., ge=1)
    seating_capacity: int = Field(..., ge=0)

    alcohol_flag: bool

    target_audience: List[str]
    price_positioning: PricePositioning
    meal_periods: List[str]  # keep flexible: ["morning","lunch","dinner","late_night"]

    competitors: List[str] = Field(default_factory=list)
    competitive_edge: str

    brand_personality_keywords: List[str] = Field(default_factory=list)
    interior_mood_keywords: List[str] = Field(default_factory=list)

    beverage_direction: BeverageDirection
    delivery_flag: bool

    operating_hours: str

    founder_background: str
    ownership_structure: OwnershipStructure
    budget_tier: BudgetTier
    experience_level: ExperienceLevel


class NormalizationResult(BaseModel):
    concept: ConceptObject
    inference_log: List[InferenceLogItem] = Field(default_factory=list)