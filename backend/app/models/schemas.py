from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ManifestItemOut(BaseModel):
    id: int
    line_number: Optional[int]
    description: str
    quantity: Optional[float]
    unit: Optional[str]
    total_value: Optional[float]
    currency: Optional[str]
    country_of_origin: Optional[str]
    itc_hs_code: Optional[str]
    hs_description: Optional[str]
    classification_confidence: Optional[float]
    classification_reasoning: Optional[str]
    needs_manual_review: bool
    assessable_value_inr: Optional[float]
    bcd_rate: Optional[float]
    bcd_amount: Optional[float]
    sws_amount: Optional[float]
    igst_rate: Optional[float]
    igst_amount: Optional[float]
    total_duty_inr: Optional[float]
    fta_applied: bool
    fta_bcd_rate: Optional[float]
    overridden_hs_code: Optional[str]
    override_note: Optional[str]

    class Config:
        from_attributes = True


class ManifestOut(BaseModel):
    id: int
    reference_number: str
    file_name: Optional[str]
    status: str
    shipment_mode: Optional[str]
    shipper_name: Optional[str]
    shipper_country: Optional[str]
    consignee_name: Optional[str]
    port_of_loading: Optional[str]
    port_of_discharge: Optional[str]
    bill_of_lading_number: Optional[str]
    incoterms: Optional[str]
    currency: Optional[str]
    total_cif_value: Optional[float]
    country_of_origin: Optional[str]
    fta_applicable: bool
    fta_name: Optional[str]
    coo_available: bool
    total_assessable_value: Optional[float]
    total_bcd: Optional[float]
    total_sws: Optional[float]
    total_igst: Optional[float]
    total_duty: Optional[float]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    icegate_be_number: Optional[str]
    icegate_filed_at: Optional[datetime]
    created_at: datetime
    items: List[ManifestItemOut] = []

    class Config:
        from_attributes = True


class ManifestListItem(BaseModel):
    id: int
    reference_number: str
    file_name: Optional[str]
    status: str
    shipper_country: Optional[str]
    total_duty: Optional[float]
    total_cif_value: Optional[float]
    created_at: datetime
    approved_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    approved_by: str = Field(..., description="Name/email of approver")
    item_overrides: Optional[List[dict]] = Field(
        default=None,
        description="List of {item_id, hs_code, note} for any line-level corrections"
    )


class RejectionRequest(BaseModel):
    rejected_by: str
    reason: str


class ItemOverride(BaseModel):
    item_id: int
    hs_code: str
    note: Optional[str] = None


class ManifestUploadResponse(BaseModel):
    manifest_id: int
    reference_number: str
    message: str
    status: str
