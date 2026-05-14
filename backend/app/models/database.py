from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class ManifestStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FILED = "filed"
    FILING_FAILED = "filing_failed"


class ShipmentMode(str, enum.Enum):
    SEA = "sea"
    AIR = "air"
    COURIER = "courier"


class Manifest(Base):
    __tablename__ = "manifests"

    id = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String(100), unique=True, index=True)
    file_name = Column(String(255))
    file_path = Column(String(500))
    file_type = Column(String(20))  # pdf, excel, xml, word
    status = Column(String(50), default=ManifestStatus.UPLOADED)
    shipment_mode = Column(String(20))

    # Consignment details (extracted)
    shipper_name = Column(String(255))
    shipper_country = Column(String(100))
    consignee_name = Column(String(255))
    consignee_iec = Column(String(20))
    port_of_loading = Column(String(100))
    port_of_discharge = Column(String(100))
    bill_of_lading_number = Column(String(100))
    bill_of_lading_date = Column(String(20))
    incoterms = Column(String(10))
    currency = Column(String(10), default="USD")
    total_cif_value = Column(Float)
    country_of_origin = Column(String(100))

    # FTA
    fta_applicable = Column(Boolean, default=False)
    fta_name = Column(String(50))
    coo_available = Column(Boolean, default=False)  # Certificate of Origin

    # Duty summary
    total_assessable_value = Column(Float)
    total_bcd = Column(Float)
    total_sws = Column(Float)
    total_igst = Column(Float)
    total_duty = Column(Float)

    # Approval
    approved_by = Column(String(255))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    approval_token = Column(String(100), unique=True)

    # ICEGATE V2
    icegate_be_number = Column(String(50))
    icegate_filed_at = Column(DateTime)
    icegate_xml_path = Column(String(500))

    # Processing metadata
    processing_errors = Column(JSON)
    raw_extracted_text = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship("ManifestItem", back_populates="manifest", cascade="all, delete-orphan")


class ManifestItem(Base):
    __tablename__ = "manifest_items"

    id = Column(Integer, primary_key=True, index=True)
    manifest_id = Column(Integer, ForeignKey("manifests.id"), nullable=False)

    # Item details from manifest
    line_number = Column(Integer)
    description = Column(Text)
    quantity = Column(Float)
    unit = Column(String(20))
    unit_price = Column(Float)
    total_value = Column(Float)
    currency = Column(String(10), default="USD")
    weight_kg = Column(Float)
    country_of_origin = Column(String(100))
    marks_numbers = Column(String(255))

    # HS Classification
    itc_hs_code = Column(String(10))  # 8-digit ITC-HS code
    hs_description = Column(Text)
    classification_confidence = Column(Float)  # 0.0 to 1.0
    classification_reasoning = Column(Text)
    needs_manual_review = Column(Boolean, default=False)

    # Duty calculation
    assessable_value_inr = Column(Float)
    exchange_rate = Column(Float)
    bcd_rate = Column(Float)
    bcd_amount = Column(Float)
    sws_amount = Column(Float)
    igst_rate = Column(Float)
    igst_amount = Column(Float)
    aidc_rate = Column(Float, default=0.0)
    aidc_amount = Column(Float, default=0.0)
    total_duty_inr = Column(Float)

    # FTA
    fta_bcd_rate = Column(Float)
    fta_applied = Column(Boolean, default=False)

    # Manual override
    overridden_hs_code = Column(String(10))
    overridden_by = Column(String(255))
    override_note = Column(Text)

    created_at = Column(DateTime, server_default=func.now())

    manifest = relationship("Manifest", back_populates="items")
