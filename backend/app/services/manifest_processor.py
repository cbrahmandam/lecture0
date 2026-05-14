"""
Main manifest processing pipeline.
Orchestrates: parse → classify → calculate duty → store → notify.
"""
import logging
import os
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.database import Manifest, ManifestItem, ManifestStatus
from app.services import document_parser, hs_classifier, duty_calculator, email_service
from app.services.icegate_generator import generate_bill_of_entry_xml, save_icegate_xml

logger = logging.getLogger(__name__)

APPROVAL_NOTIFY_EMAIL = os.environ.get("APPROVAL_NOTIFY_EMAIL", "")
DEFAULT_EXCHANGE_RATE = float(os.environ.get("USD_INR_RATE", "83.5"))


def process_manifest(
    db: Session,
    manifest_id: int,
    notify_email: Optional[str] = None,
) -> Manifest:
    """Full processing pipeline for a manifest."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise ValueError(f"Manifest {manifest_id} not found")

    try:
        manifest.status = ManifestStatus.PROCESSING
        db.commit()

        # Step 1: Parse document
        logger.info(f"[{manifest_id}] Parsing document: {manifest.file_path}")
        parsed = document_parser.parse_document(manifest.file_path, manifest.file_type)

        # Update manifest header from parsed data
        manifest.raw_extracted_text = parsed.raw_text[:10000]  # cap storage
        manifest.shipper_name = manifest.shipper_name or parsed.shipper_name
        manifest.shipper_country = manifest.shipper_country or parsed.shipper_country
        manifest.consignee_name = manifest.consignee_name or parsed.consignee_name
        manifest.consignee_iec = manifest.consignee_iec or parsed.consignee_iec
        manifest.port_of_loading = manifest.port_of_loading or parsed.port_of_loading
        manifest.port_of_discharge = manifest.port_of_discharge or parsed.port_of_discharge
        manifest.bill_of_lading_number = manifest.bill_of_lading_number or parsed.bill_of_lading_number
        manifest.bill_of_lading_date = manifest.bill_of_lading_date or parsed.bill_of_lading_date
        manifest.incoterms = manifest.incoterms or parsed.incoterms
        manifest.total_cif_value = manifest.total_cif_value or parsed.total_cif_value
        manifest.country_of_origin = manifest.country_of_origin or parsed.country_of_origin
        manifest.processing_errors = parsed.parse_errors or []
        db.commit()

        if not parsed.items:
            logger.warning(f"[{manifest_id}] No items parsed from document")
            manifest.status = ManifestStatus.CLASSIFIED
            manifest.processing_errors = (manifest.processing_errors or []) + [
                "No line items could be extracted. Please add items manually."
            ]
            db.commit()
            return manifest

        # Step 2: Classify all items with Claude AI (batch call)
        logger.info(f"[{manifest_id}] Classifying {len(parsed.items)} items")
        items_for_classification = [
            {
                "description": item.description,
                "country_of_origin": item.country_of_origin or manifest.country_of_origin,
                "quantity": item.quantity,
                "unit": item.unit,
            }
            for item in parsed.items
        ]
        classifications = hs_classifier.classify_manifest_items(items_for_classification)

        # Step 3: Calculate duties
        country = manifest.country_of_origin or parsed.shipper_country
        coo_available = manifest.coo_available or False

        items_for_duty = []
        for item, cls in zip(parsed.items, classifications):
            if cls.itc_hs_code:
                items_for_duty.append({
                    "itc_hs_code": cls.itc_hs_code,
                    "description": item.description,
                    "cif_value_usd": item.total_value or 0.0,
                    "country_of_origin": item.country_of_origin or country,
                })

        duty_results = duty_calculator.calculate_manifest_duty(
            items=items_for_duty,
            country_of_origin=country,
            exchange_rate_inr=DEFAULT_EXCHANGE_RATE,
            coo_available=coo_available,
        )

        # Step 4: Persist items to DB
        for i, (item, cls, duty) in enumerate(
            zip(parsed.items, classifications, duty_results["items"])
        ):
            db_item = ManifestItem(
                manifest_id=manifest_id,
                line_number=item.line_number or (i + 1),
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                total_value=item.total_value,
                currency=item.currency,
                weight_kg=item.weight_kg,
                country_of_origin=item.country_of_origin or country,
                marks_numbers=item.marks_numbers,
                itc_hs_code=cls.itc_hs_code,
                hs_description=cls.hs_description,
                classification_confidence=cls.confidence,
                classification_reasoning=cls.reasoning,
                needs_manual_review=cls.needs_manual_review,
                assessable_value_inr=duty.assessable_value_inr,
                exchange_rate=DEFAULT_EXCHANGE_RATE,
                bcd_rate=duty.bcd_rate,
                bcd_amount=duty.bcd_amount_inr,
                sws_amount=duty.sws_amount_inr,
                igst_rate=duty.igst_rate,
                igst_amount=duty.igst_amount_inr,
                aidc_rate=duty.aidc_rate,
                aidc_amount=duty.aidc_amount_inr,
                total_duty_inr=duty.total_duty_inr,
                fta_bcd_rate=duty.fta_bcd_rate,
                fta_applied=duty.fta_applied,
            )
            db.add(db_item)

        # Update manifest summary
        summary = duty_results["summary"]
        manifest.total_assessable_value = summary["total_assessable_value_inr"]
        manifest.total_bcd = summary["total_bcd_inr"]
        manifest.total_sws = summary["total_sws_inr"]
        manifest.total_igst = summary["total_igst_inr"]
        manifest.total_duty = summary["total_duty_inr"]

        # FTA detection
        fta_map = duty_calculator.FTA_DATA.get("country_fta_map", {})
        if country:
            fta_name = fta_map.get(country.strip().title()) or fta_map.get(country)
            if fta_name:
                manifest.fta_applicable = True
                manifest.fta_name = fta_name

        # Generate approval token
        manifest.approval_token = secrets.token_urlsafe(32)
        manifest.status = ManifestStatus.PENDING_APPROVAL
        db.commit()

        # Step 5: Send email notification
        items_needing_review = sum(1 for c in classifications if c.needs_manual_review)
        email_to = notify_email or APPROVAL_NOTIFY_EMAIL
        if email_to:
            email_service.send_approval_request(
                to_email=email_to,
                manifest_reference=manifest.reference_number,
                manifest_id=manifest.id,
                approval_token=manifest.approval_token,
                summary=summary,
                items_needing_review=items_needing_review,
            )

        logger.info(f"[{manifest_id}] Processing complete — pending approval")
        return manifest

    except Exception as e:
        logger.exception(f"[{manifest_id}] Processing failed: {e}")
        manifest.status = ManifestStatus.UPLOADED  # Reset for retry
        manifest.processing_errors = (manifest.processing_errors or []) + [str(e)]
        db.commit()
        raise


def approve_manifest(
    db: Session,
    manifest_id: int,
    approved_by: str,
    item_overrides: Optional[list] = None,
    notify_email: Optional[str] = None,
) -> Manifest:
    """Approve a manifest, apply any HS code overrides, and generate ICEGATE XML."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise ValueError(f"Manifest {manifest_id} not found")

    # Apply per-item HS code overrides if provided
    if item_overrides:
        for override in item_overrides:
            item = db.query(ManifestItem).filter(ManifestItem.id == override["item_id"]).first()
            if item:
                item.overridden_hs_code = override.get("hs_code")
                item.overridden_by = approved_by
                item.override_note = override.get("note", "")
                # Recalculate duty for overridden item
                _recalculate_item_duty(item, manifest.country_of_origin, manifest.coo_available)

    manifest.status = ManifestStatus.APPROVED
    manifest.approved_by = approved_by
    manifest.approved_at = datetime.utcnow()
    db.commit()

    # Generate ICEGATE EDI XML
    _generate_and_save_icegate_xml(db, manifest)

    email_to = notify_email or APPROVAL_NOTIFY_EMAIL
    if email_to:
        email_service.send_approval_confirmation(
            to_email=email_to,
            manifest_reference=manifest.reference_number,
            manifest_id=manifest.id,
            approved_by=approved_by,
            total_duty_inr=manifest.total_duty or 0,
        )

    return manifest


def reject_manifest(
    db: Session,
    manifest_id: int,
    rejected_by: str,
    reason: str,
    notify_email: Optional[str] = None,
) -> Manifest:
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise ValueError(f"Manifest {manifest_id} not found")

    manifest.status = ManifestStatus.REJECTED
    manifest.rejection_reason = reason
    db.commit()

    email_to = notify_email or APPROVAL_NOTIFY_EMAIL
    if email_to:
        email_service.send_rejection_notification(
            to_email=email_to,
            manifest_reference=manifest.reference_number,
            rejected_by=rejected_by,
            reason=reason,
        )

    return manifest


def _recalculate_item_duty(item: ManifestItem, country: Optional[str], coo_available: bool) -> None:
    effective_hs = item.overridden_hs_code or item.itc_hs_code
    if not effective_hs:
        return
    breakdown = duty_calculator.calculate_item_duty(
        itc_hs_code=effective_hs,
        description=item.description or "",
        cif_value_usd=item.total_value or 0.0,
        country_of_origin=item.country_of_origin or country,
        exchange_rate_inr=item.exchange_rate or DEFAULT_EXCHANGE_RATE,
        coo_available=coo_available,
    )
    item.assessable_value_inr = breakdown.assessable_value_inr
    item.bcd_rate = breakdown.bcd_rate
    item.bcd_amount = breakdown.bcd_amount_inr
    item.sws_amount = breakdown.sws_amount_inr
    item.igst_rate = breakdown.igst_rate
    item.igst_amount = breakdown.igst_amount_inr
    item.total_duty_inr = breakdown.total_duty_inr
    item.fta_applied = breakdown.fta_applied
    item.fta_bcd_rate = breakdown.fta_bcd_rate


def _generate_and_save_icegate_xml(db: Session, manifest: Manifest) -> None:
    items = db.query(ManifestItem).filter(ManifestItem.manifest_id == manifest.id).all()
    manifest_dict = {
        "reference_number": manifest.reference_number,
        "shipper_name": manifest.shipper_name,
        "shipper_country": manifest.shipper_country,
        "consignee_name": manifest.consignee_name,
        "consignee_iec": manifest.consignee_iec,
        "port_of_loading": manifest.port_of_loading,
        "port_of_discharge": manifest.port_of_discharge,
        "bill_of_lading_number": manifest.bill_of_lading_number,
        "bill_of_lading_date": manifest.bill_of_lading_date,
        "incoterms": manifest.incoterms,
        "currency": manifest.currency,
        "total_cif_value": manifest.total_cif_value,
        "country_of_origin": manifest.country_of_origin,
        "shipment_mode": manifest.shipment_mode,
        "fta_name": manifest.fta_name,
        "coo_available": manifest.coo_available,
        "total_assessable_value": manifest.total_assessable_value,
        "total_bcd": manifest.total_bcd,
        "total_sws": manifest.total_sws,
        "total_igst": manifest.total_igst,
        "total_duty": manifest.total_duty,
    }
    items_list = [
        {
            "itc_hs_code": it.itc_hs_code,
            "overridden_hs_code": it.overridden_hs_code,
            "description": it.description,
            "quantity": it.quantity,
            "unit": it.unit,
            "total_value": it.total_value,
            "country_of_origin": it.country_of_origin,
            "assessable_value_inr": it.assessable_value_inr,
            "bcd_rate": it.bcd_rate,
            "bcd_amount": it.bcd_amount,
            "sws_amount": it.sws_amount,
            "igst_rate": it.igst_rate,
            "igst_amount": it.igst_amount,
            "total_duty_inr": it.total_duty_inr,
            "fta_applied": it.fta_applied,
            "fta_bcd_rate": it.fta_bcd_rate,
        }
        for it in items
    ]

    xml_content = generate_bill_of_entry_xml(manifest_dict, items_list)
    xml_path = save_icegate_xml(xml_content, manifest.id)
    manifest.icegate_xml_path = xml_path
    db.commit()
