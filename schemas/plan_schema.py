from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


BlockType = Literal["paragraph", "bullets", "table", "callout", "image", "menu_items"]


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"]
    text: str


class BulletsBlock(BaseModel):
    type: Literal["bullets"]
    items: List[str] = Field(min_length=1)


class TableBlock(BaseModel):
    type: Literal["table"]
    columns: List[str] = Field(min_length=1)
    rows: List[List[str]] = Field(min_length=1)


class CalloutBlock(BaseModel):
    type: Literal["callout"]
    title: str
    text: str


class ImageBlock(BaseModel):
    type: Literal["image"]
    url: str
    caption: Optional[str] = None
    alt_text: str


class MenuItem(BaseModel):
    name: str
    description: str

class MenuItemsBlock(BaseModel):
    type: Literal["menu_items"]
    category: str
    items: List[MenuItem]


Block = Union[ParagraphBlock, BulletsBlock, TableBlock, CalloutBlock, ImageBlock, MenuItemsBlock]


class Section(BaseModel):
    id: str
    title: str
    blocks: List[Block] = Field(min_length=1)


class PlanMeta(BaseModel):
    concept_name: str
    country: str
    currency: str
    language: str
    blueprint_version: str
    created_at: str


class AssumptionRow(BaseModel):
    label: str
    value: str
    explanation: str


class FinalPlan(BaseModel):
    plan_meta: PlanMeta
    sections: List[Section] = Field(min_length=1)
    assumptions_table: List[AssumptionRow] = Field(min_length=1)
    disclaimer: str
    risk_report: Optional[Dict[str, Any]] = None
    derived_financials: Optional[Dict[str, Any]] = None
    token_usage: Optional[Dict[str, Any]] = None