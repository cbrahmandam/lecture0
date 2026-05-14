#!/usr/bin/env python3
"""
V1 Test Runner — India Customs Manifest Processor
Usage:
  python test_v1.py path/to/your/manifest.pdf
  python test_v1.py path/to/manifest.xlsx --country "China" --mode sea
  ANTHROPIC_API_KEY=sk-ant-... python test_v1.py manifest.pdf
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


def check_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or not key.startswith("sk-ant"):
        print("\n❌  ANTHROPIC_API_KEY not set or invalid.")
        print("\nTo set it:")
        print('  export ANTHROPIC_API_KEY="sk-ant-api03-..."')
        print("  (or add it to .env in this directory)\n")
        sys.exit(1)
    print(f"✓  API key loaded ({key[:16]}...)")


def run_test(file_path: str, country: str = None, mode: str = "sea", coo: bool = False):
    from app.services.document_parser import parse_document
    from app.services.hs_classifier import classify_manifest_items
    from app.services.duty_calculator import calculate_manifest_duty

    path = Path(file_path)
    if not path.exists():
        print(f"❌  File not found: {file_path}")
        sys.exit(1)

    ext = path.suffix.lower()
    type_map = {".pdf": "pdf", ".xlsx": "excel", ".xls": "excel", ".csv": "csv",
                ".xml": "xml", ".edi": "edi", ".docx": "word", ".doc": "word"}
    file_type = type_map.get(ext, "pdf")

    print(f"\n{'='*60}")
    print(f"  INDIA CUSTOMS MANIFEST PROCESSOR — V1 TEST")
    print(f"{'='*60}")
    print(f"  File   : {path.name}")
    print(f"  Type   : {file_type.upper()}")
    print(f"  Mode   : {mode.upper()}")
    print(f"  Origin : {country or 'Not specified'}")
    print(f"  COO    : {'Yes (FTA rates will apply)' if coo else 'No'}")
    print(f"{'='*60}\n")

    # Step 1: Parse
    print("Step 1/3 — Parsing document...")
    parsed = parse_document(file_path, file_type)

    if parsed.parse_errors:
        print(f"  ⚠ Parse warnings: {parsed.parse_errors}")

    # Print header info
    header_fields = {
        "Shipper": parsed.shipper_name,
        "Consignee": parsed.consignee_name,
        "B/L Number": parsed.bill_of_lading_number,
        "Port of Loading": parsed.port_of_loading,
        "Port of Discharge": parsed.port_of_discharge,
        "Incoterms": parsed.incoterms,
        "Country of Origin": parsed.country_of_origin or country,
        "Total CIF Value": parsed.total_cif_value,
    }
    print("  Extracted header:")
    for k, v in header_fields.items():
        if v:
            print(f"    {k:<22}: {v}")

    effective_country = country or parsed.country_of_origin or parsed.shipper_country

    if not parsed.items:
        print("\n⚠  No line items extracted from document.")
        print("  The parser could not find structured line items.")
        print("  This can happen with complex scanned PDFs or unusual layouts.")
        print("  Raw text extracted (first 500 chars):")
        print(f"  {parsed.raw_text[:500]}")
        sys.exit(0)

    print(f"\n  ✓ {len(parsed.items)} line item(s) extracted\n")

    # Step 2: Classify
    print(f"Step 2/3 — Classifying {len(parsed.items)} items with Claude AI...")
    print("  (This calls the Claude API — may take 10–30 seconds)\n")

    items_for_cls = [
        {
            "description": item.description,
            "country_of_origin": item.country_of_origin or effective_country,
            "quantity": item.quantity,
            "unit": item.unit,
        }
        for item in parsed.items
    ]

    classifications = classify_manifest_items(items_for_cls)

    # Step 3: Duty
    print("Step 3/3 — Calculating customs duty...\n")
    items_for_duty = []
    for item, cls in zip(parsed.items, classifications):
        if cls.itc_hs_code:
            items_for_duty.append({
                "itc_hs_code": cls.itc_hs_code,
                "description": item.description,
                "cif_value_usd": item.total_value or 0.0,
                "country_of_origin": item.country_of_origin or effective_country,
            })

    duty_results = calculate_manifest_duty(
        items=items_for_duty,
        country_of_origin=effective_country,
        coo_available=coo,
    )

    # ─── RESULTS ──────────────────────────────────────────────
    print(f"{'='*60}")
    print("  CLASSIFICATION RESULTS")
    print(f"{'='*60}")

    all_confident = True
    low_confidence_items = []

    for i, (item, cls, duty) in enumerate(zip(parsed.items, classifications, duty_results["items"]), 1):
        confidence_pct = int((cls.confidence or 0) * 100)
        flag = "⚠ REVIEW" if cls.needs_manual_review else "✓"
        conf_bar = _bar(cls.confidence or 0)

        if cls.needs_manual_review:
            all_confident = False
            low_confidence_items.append(i)

        print(f"\n  Item {i}: {item.description[:60]}")
        print(f"    ITC-HS Code  : {cls.itc_hs_code or 'UNCLASSIFIED'}")
        print(f"    HS Desc      : {(cls.hs_description or '')[:55]}")
        print(f"    Confidence   : {conf_bar} {confidence_pct}%  {flag}")
        print(f"    Reasoning    : {(cls.reasoning or '')[:80]}")
        if cls.special_notes:
            print(f"    ⚑ Notes      : {cls.special_notes}")
        print(f"    BCD          : {duty.bcd_rate:.1f}%  → ₹ {duty.bcd_amount_inr:,.0f}")
        print(f"    SWS          : 10% of BCD → ₹ {duty.sws_amount_inr:,.0f}")
        print(f"    IGST         : {duty.igst_rate:.0f}%  → ₹ {duty.igst_amount_inr:,.0f}")
        if duty.fta_applied:
            print(f"    FTA ({duty.fta_name}) : BCD reduced from MFN → {duty.fta_bcd_rate}%")
        print(f"    ──────────────────────────────")
        print(f"    TOTAL DUTY   : ₹ {duty.total_duty_inr:,.2f}")

    # Summary
    s = duty_results["summary"]
    print(f"\n{'='*60}")
    print("  DUTY SUMMARY")
    print(f"{'='*60}")
    print(f"  Total CIF Value          : USD {s['total_cif_usd']:>12,.2f}")
    print(f"  Total Assessable Value   : INR {s['total_assessable_value_inr']:>12,.2f}")
    print(f"  Basic Customs Duty (BCD) : INR {s['total_bcd_inr']:>12,.2f}")
    print(f"  Social Welfare Surcharge : INR {s['total_sws_inr']:>12,.2f}")
    print(f"  IGST                     : INR {s['total_igst_inr']:>12,.2f}")
    print(f"  ─────────────────────────────────────────")
    print(f"  TOTAL DUTY PAYABLE       : INR {s['total_duty_inr']:>12,.2f}")
    if s['fta_applied_items']:
        print(f"\n  ✓ FTA preferential rates applied to {s['fta_applied_items']} item(s)")

    # Confidence summary
    classified = [c for c in classifications if c.itc_hs_code]
    avg_conf = sum(c.confidence or 0 for c in classified) / len(classified) if classified else 0
    print(f"\n{'='*60}")
    print("  CLASSIFICATION CONFIDENCE REPORT")
    print(f"{'='*60}")
    print(f"  Items classified         : {len(classified)} / {len(parsed.items)}")
    print(f"  Average confidence       : {int(avg_conf*100)}%")
    print(f"  Items needing review     : {len(low_confidence_items)}")
    if avg_conf >= 0.90:
        verdict = "✓ ABOVE 90% TARGET"
    elif avg_conf >= 0.85:
        verdict = "⚠ BETWEEN 85-90% — REVIEW FLAGGED ITEMS"
    else:
        verdict = "✗ BELOW 85% — MANUAL REVIEW REQUIRED"
    print(f"  Verdict                  : {verdict}")

    if low_confidence_items:
        print(f"\n  Items flagged (lines {low_confidence_items}):")
        print("  → These will appear highlighted in the web UI")
        print("  → You can override their HS codes before approving")

    print(f"\n{'='*60}\n")

    if avg_conf >= 0.85:
        print("  Next step: Start the web app to review and approve.")
        print("  Run: docker compose up --build")
        print("  Open: http://localhost:3000\n")
    else:
        print("  Recommendation: Review item descriptions and add more detail.")
        print("  More specific descriptions → higher confidence classification.\n")


def _bar(confidence: float) -> str:
    filled = int(confidence * 10)
    return "[" + "█" * filled + "░" * (10 - filled) + "]"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test India Customs V1 manifest processor")
    parser.add_argument("file", help="Path to manifest file (PDF, Excel, XML, Word, CSV)")
    parser.add_argument("--country", "-c", help="Country of origin (e.g. China, Thailand, UAE)")
    parser.add_argument("--mode", "-m", default="sea", choices=["sea", "air"], help="Shipment mode")
    parser.add_argument("--coo", action="store_true", help="Certificate of Origin available (enables FTA rates)")
    args = parser.parse_args()

    check_api_key()
    run_test(args.file, country=args.country, mode=args.mode, coo=args.coo)
