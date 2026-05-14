"""
Indian Customs Duty Calculator.
Formula (CBIC standard):
  Assessable Value (AV) = CIF value × exchange_rate + 1% landing charges
  BCD = AV × bcd_rate
  SWS = BCD × 10%
  IGST = (AV + BCD + SWS) × igst_rate
  Total Duty = BCD + SWS + IGST  (+AIDC if applicable)
"""
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TARIFF_DATA_PATH = Path(__file__).parent.parent / "data" / "duty_rates.json"
FTA_DATA_PATH = Path(__file__).parent.parent / "data" / "fta_rates.json"

with open(TARIFF_DATA_PATH) as f:
    TARIFF_DATA = json.load(f)

with open(FTA_DATA_PATH) as f:
    FTA_DATA = json.load(f)

SWS_RATE = 0.10  # Social Welfare Surcharge: 10% of BCD
LANDING_CHARGE_RATE = 0.01  # 1% of CIF value

# AIDC applies to select agri/chemical items - chapter 27 & 08 primarily
AIDC_CHAPTERS = {"27", "08", "15", "17", "23"}


@dataclass
class DutyBreakdown:
    itc_hs_code: str
    description: str
    cif_value_usd: float
    exchange_rate_inr: float
    cif_value_inr: float
    landing_charges_inr: float
    assessable_value_inr: float
    bcd_rate: float
    bcd_amount_inr: float
    sws_amount_inr: float
    igst_rate: float
    igst_amount_inr: float
    aidc_rate: float = 0.0
    aidc_amount_inr: float = 0.0
    total_duty_inr: float = 0.0
    fta_name: Optional[str] = None
    fta_bcd_rate: Optional[float] = None
    fta_applied: bool = False
    notes: list[str] = field(default_factory=list)


def calculate_item_duty(
    itc_hs_code: str,
    description: str,
    cif_value_usd: float,
    country_of_origin: Optional[str] = None,
    exchange_rate_inr: float = 83.5,  # Default USD/INR; update from live rate in production
    coo_available: bool = False,
) -> DutyBreakdown:
    """
    Calculate full duty breakdown for a single line item.
    """
    rates = _get_duty_rates(itc_hs_code)
    bcd_rate = rates["bcd"] / 100.0
    igst_rate = rates["igst"] / 100.0
    aidc_rate = rates.get("aidc", 0.0) / 100.0

    # FTA check
    fta_name = None
    fta_bcd_rate = None
    fta_applied = False

    if country_of_origin and coo_available:
        fta = _get_fta_for_country(country_of_origin)
        if fta:
            fta_rate = _get_fta_rate(fta, itc_hs_code)
            if fta_rate is not None and fta_rate / 100.0 < bcd_rate:
                fta_name = fta
                fta_bcd_rate = fta_rate
                bcd_rate = fta_rate / 100.0
                fta_applied = True

    # Duty computation
    cif_inr = cif_value_usd * exchange_rate_inr
    landing = cif_inr * LANDING_CHARGE_RATE
    av = cif_inr + landing

    bcd = round(av * bcd_rate, 2)
    sws = round(bcd * SWS_RATE, 2)

    chapter = itc_hs_code[:2]
    if chapter in AIDC_CHAPTERS and aidc_rate == 0.0:
        aidc_rate = _get_aidc_rate(itc_hs_code)

    aidc = round(av * aidc_rate, 2)
    igst_base = av + bcd + sws + aidc
    igst = round(igst_base * igst_rate, 2)
    total = round(bcd + sws + aidc + igst, 2)

    notes = []
    if fta_applied:
        notes.append(f"FTA {fta_name} preferential BCD rate applied ({fta_bcd_rate}%)")
    if rates.get("add_applicable"):
        notes.append("Anti-Dumping Duty may apply — check CBIC ADD notifications for this HS code and country")
    if rates.get("safeguard"):
        notes.append("Safeguard duty applicable — check current CBIC notifications")

    return DutyBreakdown(
        itc_hs_code=itc_hs_code,
        description=description,
        cif_value_usd=cif_value_usd,
        exchange_rate_inr=exchange_rate_inr,
        cif_value_inr=round(cif_inr, 2),
        landing_charges_inr=round(landing, 2),
        assessable_value_inr=round(av, 2),
        bcd_rate=bcd_rate * 100,
        bcd_amount_inr=bcd,
        sws_amount_inr=sws,
        igst_rate=igst_rate * 100,
        igst_amount_inr=igst,
        aidc_rate=aidc_rate * 100,
        aidc_amount_inr=aidc,
        total_duty_inr=total,
        fta_name=fta_name,
        fta_bcd_rate=fta_bcd_rate,
        fta_applied=fta_applied,
        notes=notes,
    )


def calculate_manifest_duty(
    items: list[dict],
    country_of_origin: Optional[str] = None,
    exchange_rate_inr: float = 83.5,
    coo_available: bool = False,
) -> dict:
    """
    Calculate duty for all items in a manifest.
    items: list of dicts with keys: itc_hs_code, description, cif_value_usd
    Returns: {items: [DutyBreakdown], summary: {...}}
    """
    results = []
    for item in items:
        origin = item.get("country_of_origin") or country_of_origin
        breakdown = calculate_item_duty(
            itc_hs_code=item["itc_hs_code"],
            description=item.get("description", ""),
            cif_value_usd=item.get("cif_value_usd", 0.0),
            country_of_origin=origin,
            exchange_rate_inr=exchange_rate_inr,
            coo_available=coo_available,
        )
        results.append(breakdown)

    summary = {
        "total_cif_usd": round(sum(r.cif_value_usd for r in results), 2),
        "total_cif_inr": round(sum(r.cif_value_inr for r in results), 2),
        "total_assessable_value_inr": round(sum(r.assessable_value_inr for r in results), 2),
        "total_bcd_inr": round(sum(r.bcd_amount_inr for r in results), 2),
        "total_sws_inr": round(sum(r.sws_amount_inr for r in results), 2),
        "total_igst_inr": round(sum(r.igst_amount_inr for r in results), 2),
        "total_aidc_inr": round(sum(r.aidc_amount_inr for r in results), 2),
        "total_duty_inr": round(sum(r.total_duty_inr for r in results), 2),
        "exchange_rate": exchange_rate_inr,
        "fta_applied_items": sum(1 for r in results if r.fta_applied),
    }

    return {"items": results, "summary": summary}


def _get_duty_rates(itc_hs_code: str) -> dict:
    """
    Look up BCD and IGST rates for an ITC-HS code.
    Tries: 8-digit → 6-digit → 4-digit → chapter defaults.
    """
    chapter = itc_hs_code[:2]
    chapter_data = TARIFF_DATA.get(chapter)

    if not chapter_data:
        return {"bcd": 10.0, "igst": 18.0}  # Safe fallback

    subcats = chapter_data.get("subcategories", {})

    # Try progressively shorter lookups
    for length in (8, 6, 4):
        key = itc_hs_code[:length]
        if key in subcats:
            sub = subcats[key]
            return {
                "bcd": sub["bcd"],
                "igst": sub["igst"],
                "aidc": sub.get("aidc", 0.0),
                "add_applicable": sub.get("add_applicable", False),
                "safeguard": sub.get("safeguard", False),
            }

    return {
        "bcd": chapter_data.get("default_bcd", 10.0),
        "igst": chapter_data.get("default_igst", 18.0),
    }


def _get_fta_for_country(country: str) -> Optional[str]:
    country_map = FTA_DATA.get("country_fta_map", {})
    country_clean = country.strip().title()
    return country_map.get(country_clean) or country_map.get(country)


def _get_fta_rate(fta_name: str, itc_hs_code: str) -> Optional[float]:
    fta_rates = FTA_DATA.get(fta_name, {})
    for length in (8, 6, 4, 2):
        key = itc_hs_code[:length]
        if key in fta_rates:
            entry = fta_rates[key]
            if isinstance(entry, dict):
                return entry.get("bcd")
    return None


def _get_aidc_rate(itc_hs_code: str) -> float:
    """Agriculture Infrastructure Development Cess rates."""
    aidc_map = {
        "0801": 100.0, "0802": 100.0,  # Cashews, almonds
        "2709": 0.0,  # Crude oil - separate cess
        "2710": 2.5,  # Petrol/diesel
        "15": 5.0,    # Edible oils chapter
        "17": 100.0,  # Sugar
    }
    for key in (itc_hs_code[:4], itc_hs_code[:2]):
        if key in aidc_map:
            return aidc_map[key] / 100.0
    return 0.0
