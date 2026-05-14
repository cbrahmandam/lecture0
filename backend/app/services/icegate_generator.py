"""
V2: ICEGATE EDI XML Bill of Entry Generator.
Generates BE XML in the format accepted by ICEGATE portal for upload.
Spec: ICEGATE EDI Message Implementation Guide (MIG) for Bill of Entry (BE) - Sea/Air.

Filing options:
  Option A (current): Generate XML → user uploads manually to ICEGATE portal
  Option B (future):  Register as ICEGATE EDI user → use ICEGATE API for fully automated filing
"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring


def generate_bill_of_entry_xml(manifest: dict, items: list[dict]) -> str:
    """
    Generate a Bill of Entry XML for ICEGATE portal upload.

    manifest dict keys: reference_number, shipper_name, consignee_name, consignee_iec,
        consignee_gstin, port_of_loading, port_of_discharge, bill_of_lading_number,
        bill_of_lading_date, incoterms, currency, total_cif_value, country_of_origin,
        shipment_mode, fta_name, coo_available

    items list dict keys: itc_hs_code, description, quantity, unit, total_value,
        assessable_value_inr, bcd_rate, bcd_amount, sws_amount, igst_rate, igst_amount,
        total_duty_inr, country_of_origin
    """
    root = Element("BillOfEntry")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("version", "1.0")
    root.set("generatedAt", datetime.utcnow().isoformat() + "Z")
    root.set("generator", "IndiaCustomsManifestProcessor/1.0")

    # Header
    header = SubElement(root, "Header")
    _add(header, "MessageType", "BE")
    _add(header, "MessageDate", datetime.utcnow().strftime("%d/%m/%Y"))
    _add(header, "ReferenceNumber", manifest.get("reference_number", ""))
    _add(header, "BEType", "H")  # H=Home Consumption, W=Warehousing
    _add(header, "ShipmentMode", "S" if manifest.get("shipment_mode") == "sea" else "A")
    _add(header, "PortCode", _port_to_code(manifest.get("port_of_discharge", "")))

    # Importer details
    importer = SubElement(root, "Importer")
    _add(importer, "Name", manifest.get("consignee_name", ""))
    _add(importer, "IECCode", manifest.get("consignee_iec") or os.environ.get("DEFAULT_IEC", ""))
    _add(importer, "GSTIN", manifest.get("consignee_gstin") or os.environ.get("DEFAULT_GSTIN", ""))
    _add(importer, "PAN", manifest.get("consignee_pan") or os.environ.get("DEFAULT_PAN", ""))

    # Exporter / Shipper
    exporter = SubElement(root, "Exporter")
    _add(exporter, "Name", manifest.get("shipper_name", ""))
    _add(exporter, "Country", manifest.get("shipper_country", ""))

    # Consignment details
    consignment = SubElement(root, "Consignment")
    _add(consignment, "BillOfLadingNumber", manifest.get("bill_of_lading_number", ""))
    _add(consignment, "BillOfLadingDate", _format_date(manifest.get("bill_of_lading_date")))
    _add(consignment, "PortOfLoading", manifest.get("port_of_loading", ""))
    _add(consignment, "PortOfDischarge", manifest.get("port_of_discharge", ""))
    _add(consignment, "CountryOfOrigin", manifest.get("country_of_origin", ""))
    _add(consignment, "Incoterms", manifest.get("incoterms", "CIF"))
    _add(consignment, "InvoiceCurrency", manifest.get("currency", "USD"))
    _add(consignment, "TotalCIFValue", str(round(manifest.get("total_cif_value", 0), 2)))

    # FTA / COO
    if manifest.get("fta_name"):
        fta_el = SubElement(consignment, "FTADetails")
        _add(fta_el, "FTAName", manifest["fta_name"])
        _add(fta_el, "COOAvailable", "Y" if manifest.get("coo_available") else "N")
        _add(fta_el, "Notification", _get_fta_notification(manifest["fta_name"]))

    # Duty summary
    duty_summary = SubElement(root, "DutySummary")
    _add(duty_summary, "TotalAssessableValueINR", str(round(manifest.get("total_assessable_value", 0), 2)))
    _add(duty_summary, "TotalBCDINR", str(round(manifest.get("total_bcd", 0), 2)))
    _add(duty_summary, "TotalSWSINR", str(round(manifest.get("total_sws", 0), 2)))
    _add(duty_summary, "TotalIGSTINR", str(round(manifest.get("total_igst", 0), 2)))
    _add(duty_summary, "TotalDutyINR", str(round(manifest.get("total_duty", 0), 2)))

    # Line items
    items_el = SubElement(root, "Items")
    for i, item in enumerate(items, 1):
        effective_hs = item.get("overridden_hs_code") or item.get("itc_hs_code", "")
        item_el = SubElement(items_el, "Item")
        item_el.set("lineNumber", str(i))

        _add(item_el, "SerialNumber", str(i))
        _add(item_el, "ITCHSCode", effective_hs)
        _add(item_el, "Description", item.get("description", ""))
        _add(item_el, "Quantity", str(item.get("quantity", 0)))
        _add(item_el, "Unit", item.get("unit", "NOS"))
        _add(item_el, "CIFValueUSD", str(round(item.get("total_value", 0), 2)))
        _add(item_el, "CountryOfOrigin", item.get("country_of_origin", manifest.get("country_of_origin", "")))

        duty_el = SubElement(item_el, "DutyDetails")
        _add(duty_el, "AssessableValueINR", str(round(item.get("assessable_value_inr", 0), 2)))
        _add(duty_el, "BCDRate", str(item.get("bcd_rate", 0)))
        _add(duty_el, "BCDAmountINR", str(round(item.get("bcd_amount", 0), 2)))
        _add(duty_el, "SWSAmountINR", str(round(item.get("sws_amount", 0), 2)))
        _add(duty_el, "IGSTRate", str(item.get("igst_rate", 0)))
        _add(duty_el, "IGSTAmountINR", str(round(item.get("igst_amount", 0), 2)))
        _add(duty_el, "TotalDutyINR", str(round(item.get("total_duty_inr", 0), 2)))

        if item.get("fta_applied"):
            _add(duty_el, "FTAApplied", "Y")
            _add(duty_el, "FTABCDRate", str(item.get("fta_bcd_rate", 0)))

    # Filing instructions comment
    instructions = SubElement(root, "FilingInstructions")
    _add(instructions, "Step1", "Log in to ICEGATE portal at https://www.icegate.gov.in")
    _add(instructions, "Step2", "Navigate to: Services > Bill of Entry > Upload EDI BE")
    _add(instructions, "Step3", "Upload this XML file")
    _add(instructions, "Step4", "Verify pre-filled data and submit")
    _add(instructions, "Step5", "Note the BE Number assigned by the system")
    _add(instructions, "Note", "Ensure IEC, GSTIN, and PAN in Importer section are correct before upload")

    # Pretty-print XML
    xml_str = tostring(root, encoding="unicode")
    return minidom.parseString(xml_str).toprettyxml(indent="  ")


def save_icegate_xml(xml_content: str, manifest_id: int, upload_dir: str = "uploads/icegate") -> str:
    """Save ICEGATE XML to disk and return the file path."""
    path = Path(upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    filename = f"BE_{manifest_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xml"
    file_path = path / filename
    file_path.write_text(xml_content, encoding="utf-8")
    return str(file_path)


def _add(parent: Element, tag: str, text: str) -> Element:
    el = SubElement(parent, tag)
    el.text = text
    return el


def _port_to_code(port_name: str) -> str:
    """Map common port names to ICEGATE port codes."""
    port_map = {
        "nhava sheva": "INNSA",
        "nsict": "INNSA",
        "jnpt": "INNSA",
        "mumbai": "INBOM",
        "chennai": "INMAA",
        "kolkata": "INCCU",
        "delhi": "INDEL",
        "icd tughlakabad": "INDEL",
        "bangalore": "INBLR",
        "hyderabad": "INHYD",
        "ahmedabad": "INAMD",
        "cochin": "INCOK",
        "kochi": "INCOK",
        "mundra": "INMUN",
        "pipavav": "INPAV",
    }
    if not port_name:
        return "INNSA"
    return port_map.get(port_name.lower().strip(), port_name.upper()[:6])


def _format_date(date_str: Optional[str]) -> str:
    if not date_str:
        return datetime.utcnow().strftime("%d/%m/%Y")
    # Try to normalise to DD/MM/YYYY
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return date_str


def _get_fta_notification(fta_name: str) -> str:
    notifications = {
        "AIFTA": "Notification No. 46/2011-Customs dated 01.06.2011 (ASEAN-India FTA)",
        "INDIA_UAE_CEPA": "Notification No. 24/2022-Customs dated 30.04.2022 (India-UAE CEPA)",
        "INDIA_JAPAN_CEPA": "Notification No. 69/2011-Customs dated 01.08.2011 (India-Japan CEPA)",
        "INDIA_KOREA_CEPA": "Notification No. 113/2009-Customs dated 29.09.2009 (India-Korea CEPA)",
    }
    return notifications.get(fta_name, fta_name)
