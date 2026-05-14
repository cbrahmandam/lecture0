import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import Manifest, ManifestItem, ManifestStatus
from app.models.schemas import (
    ManifestOut, ManifestListItem, ManifestUploadResponse,
    ApprovalRequest, RejectionRequest
)
from app.services import manifest_processor

router = APIRouter(prefix="/api/v1", tags=["manifests"])

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads/manifests"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".xml", ".edi", ".docx", ".doc"}


def get_db():
    from app.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/manifests", response_model=ManifestUploadResponse)
async def upload_manifest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    shipment_mode: str = Form("sea"),
    country_of_origin: Optional[str] = Form(None),
    notify_email: Optional[str] = Form(None),
    coo_available: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Upload a manifest document for processing."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Save file
    file_id = str(uuid.uuid4())
    dest_path = UPLOAD_DIR / f"{file_id}{suffix}"
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_type = _get_file_type(suffix)
    reference = f"IMP-{uuid.uuid4().hex[:8].upper()}"

    db_manifest = Manifest(
        reference_number=reference,
        file_name=file.filename,
        file_path=str(dest_path),
        file_type=file_type,
        status=ManifestStatus.UPLOADED,
        shipment_mode=shipment_mode,
        country_of_origin=country_of_origin,
        coo_available=coo_available,
    )
    db.add(db_manifest)
    db.commit()
    db.refresh(db_manifest)

    # Process asynchronously
    background_tasks.add_task(
        manifest_processor.process_manifest,
        db=db,
        manifest_id=db_manifest.id,
        notify_email=notify_email,
    )

    return ManifestUploadResponse(
        manifest_id=db_manifest.id,
        reference_number=reference,
        message="Manifest uploaded. Classification and duty calculation in progress.",
        status=ManifestStatus.UPLOADED,
    )


@router.get("/manifests", response_model=List[ManifestListItem])
def list_manifests(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all manifests with optional status filter."""
    query = db.query(Manifest)
    if status:
        query = query.filter(Manifest.status == status)
    return query.order_by(Manifest.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/manifests/{manifest_id}", response_model=ManifestOut)
def get_manifest(manifest_id: int, db: Session = Depends(get_db)):
    """Get full manifest details including all classified items and duty breakdown."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return manifest


@router.post("/manifests/{manifest_id}/approve")
def approve_manifest(
    manifest_id: int,
    request: ApprovalRequest,
    notify_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Approve a manifest. Optionally override HS codes for specific line items."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    if manifest.status not in (ManifestStatus.PENDING_APPROVAL, ManifestStatus.CLASSIFIED):
        raise HTTPException(
            status_code=400,
            detail=f"Manifest is in status '{manifest.status}' — cannot approve"
        )

    updated = manifest_processor.approve_manifest(
        db=db,
        manifest_id=manifest_id,
        approved_by=request.approved_by,
        item_overrides=request.item_overrides,
        notify_email=notify_email,
    )

    return {
        "message": "Manifest approved",
        "manifest_id": updated.id,
        "reference_number": updated.reference_number,
        "total_duty_inr": updated.total_duty,
        "icegate_xml_ready": bool(updated.icegate_xml_path),
    }


@router.post("/manifests/{manifest_id}/reject")
def reject_manifest(
    manifest_id: int,
    request: RejectionRequest,
    notify_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Reject a manifest with a reason."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")

    updated = manifest_processor.reject_manifest(
        db=db,
        manifest_id=manifest_id,
        rejected_by=request.rejected_by,
        reason=request.reason,
        notify_email=notify_email,
    )
    return {"message": "Manifest rejected", "manifest_id": updated.id}


@router.get("/manifests/{manifest_id}/icegate-xml")
def download_icegate_xml(manifest_id: int, db: Session = Depends(get_db)):
    """Download the generated ICEGATE EDI XML for portal upload (V2)."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    if not manifest.icegate_xml_path or not Path(manifest.icegate_xml_path).exists():
        raise HTTPException(
            status_code=404,
            detail="ICEGATE XML not yet generated. Approve the manifest first."
        )
    return FileResponse(
        path=manifest.icegate_xml_path,
        filename=f"BE_{manifest.reference_number}.xml",
        media_type="application/xml",
    )


@router.post("/manifests/{manifest_id}/reprocess")
def reprocess_manifest(
    manifest_id: int,
    background_tasks: BackgroundTasks,
    notify_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Re-run classification and duty calculation on an already-uploaded manifest."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")

    # Clear existing items
    db.query(ManifestItem).filter(ManifestItem.manifest_id == manifest_id).delete()
    manifest.status = ManifestStatus.UPLOADED
    db.commit()

    background_tasks.add_task(
        manifest_processor.process_manifest,
        db=db,
        manifest_id=manifest_id,
        notify_email=notify_email,
    )
    return {"message": "Reprocessing started", "manifest_id": manifest_id}


@router.get("/manifests/{manifest_id}/duty-summary")
def get_duty_summary(manifest_id: int, db: Session = Depends(get_db)):
    """Get duty summary breakdown for a manifest."""
    manifest = db.query(Manifest).filter(Manifest.id == manifest_id).first()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")

    items = db.query(ManifestItem).filter(ManifestItem.manifest_id == manifest_id).all()
    flagged = [i for i in items if i.needs_manual_review]

    return {
        "manifest_id": manifest_id,
        "reference_number": manifest.reference_number,
        "status": manifest.status,
        "total_items": len(items),
        "items_flagged_for_review": len(flagged),
        "fta_applicable": manifest.fta_applicable,
        "fta_name": manifest.fta_name,
        "coo_available": manifest.coo_available,
        "duty_summary": {
            "total_cif_value_usd": manifest.total_cif_value,
            "total_assessable_value_inr": manifest.total_assessable_value,
            "total_bcd_inr": manifest.total_bcd,
            "total_sws_inr": manifest.total_sws,
            "total_igst_inr": manifest.total_igst,
            "total_duty_inr": manifest.total_duty,
        },
        "flagged_items": [
            {
                "id": i.id,
                "line_number": i.line_number,
                "description": i.description,
                "itc_hs_code": i.itc_hs_code,
                "confidence": i.classification_confidence,
                "reasoning": i.classification_reasoning,
            }
            for i in flagged
        ],
    }


def _get_file_type(suffix: str) -> str:
    mapping = {
        ".pdf": "pdf", ".xlsx": "excel", ".xls": "excel",
        ".csv": "csv", ".xml": "xml", ".edi": "edi",
        ".docx": "word", ".doc": "word",
    }
    return mapping.get(suffix, "unknown")
