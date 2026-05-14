"""
Multi-format manifest document parser.
Extracts structured consignment and line-item data from PDF, Excel, XML, and Word files.
"""
import io
import re
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ParsedItem:
    def __init__(self):
        self.line_number: Optional[int] = None
        self.description: str = ""
        self.quantity: Optional[float] = None
        self.unit: Optional[str] = None
        self.unit_price: Optional[float] = None
        self.total_value: Optional[float] = None
        self.currency: str = "USD"
        self.weight_kg: Optional[float] = None
        self.country_of_origin: Optional[str] = None
        self.marks_numbers: Optional[str] = None


class ParsedManifest:
    def __init__(self):
        self.raw_text: str = ""
        self.shipper_name: Optional[str] = None
        self.shipper_country: Optional[str] = None
        self.consignee_name: Optional[str] = None
        self.consignee_iec: Optional[str] = None
        self.port_of_loading: Optional[str] = None
        self.port_of_discharge: Optional[str] = None
        self.bill_of_lading_number: Optional[str] = None
        self.bill_of_lading_date: Optional[str] = None
        self.incoterms: Optional[str] = None
        self.currency: str = "USD"
        self.total_cif_value: Optional[float] = None
        self.country_of_origin: Optional[str] = None
        self.items: list[ParsedItem] = []
        self.parse_errors: list[str] = []


def parse_document(file_path: str, file_type: str) -> ParsedManifest:
    """Route to appropriate parser based on file type."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if file_type == "pdf" or ext == ".pdf":
        return _parse_pdf(file_path)
    elif file_type in ("excel", "xlsx", "xls", "csv") or ext in (".xlsx", ".xls", ".csv"):
        return _parse_excel(file_path)
    elif file_type in ("xml", "edi") or ext in (".xml", ".edi", ".edifact"):
        return _parse_xml(file_path)
    elif file_type in ("word", "docx", "doc") or ext in (".docx", ".doc"):
        return _parse_word(file_path)
    else:
        manifest = ParsedManifest()
        manifest.parse_errors.append(f"Unsupported file type: {file_type or ext}")
        return manifest


def _parse_pdf(file_path: str) -> ParsedManifest:
    manifest = ParsedManifest()
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        if text_parts:
            manifest.raw_text = "\n".join(text_parts)
        else:
            # Scanned PDF — fall back to OCR
            manifest.raw_text = _ocr_pdf(file_path)

    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}, trying OCR")
        try:
            manifest.raw_text = _ocr_pdf(file_path)
        except Exception as ocr_err:
            manifest.parse_errors.append(f"PDF parse failed: {ocr_err}")

    if manifest.raw_text:
        _extract_header_from_text(manifest, manifest.raw_text)
        _extract_items_from_text(manifest, manifest.raw_text)

    return manifest


def _ocr_pdf(file_path: str) -> str:
    """OCR a scanned PDF using pdf2image + pytesseract."""
    from pdf2image import convert_from_path
    import pytesseract

    pages = convert_from_path(file_path, dpi=300)
    texts = []
    for page_img in pages:
        text = pytesseract.image_to_string(page_img, lang="eng")
        texts.append(text)
    return "\n".join(texts)


def _parse_excel(file_path: str) -> ParsedManifest:
    manifest = ParsedManifest()
    try:
        path = Path(file_path)
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path, header=None)

        # Convert entire sheet to text for header extraction
        manifest.raw_text = df.to_string()

        # Try to find header row heuristically
        header_row = _find_excel_header_row(df)
        if header_row is not None:
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        else:
            # Assume first row is header
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)

        df.columns = [str(c).strip().lower() for c in df.columns]

        col_map = _map_excel_columns(df.columns.tolist())

        for idx, row in df.iterrows():
            item = ParsedItem()
            item.line_number = idx + 1

            if col_map.get("description"):
                item.description = str(row.get(col_map["description"], "")).strip()
            if col_map.get("quantity"):
                item.quantity = _to_float(row.get(col_map["quantity"]))
            if col_map.get("unit"):
                item.unit = str(row.get(col_map["unit"], "")).strip()
            if col_map.get("unit_price"):
                item.unit_price = _to_float(row.get(col_map["unit_price"]))
            if col_map.get("total_value"):
                item.total_value = _to_float(row.get(col_map["total_value"]))
            elif item.quantity and item.unit_price:
                item.total_value = round(item.quantity * item.unit_price, 2)
            if col_map.get("weight"):
                item.weight_kg = _to_float(row.get(col_map["weight"]))
            if col_map.get("origin"):
                item.country_of_origin = str(row.get(col_map["origin"], "")).strip()
            if col_map.get("currency"):
                item.currency = str(row.get(col_map["currency"], "USD")).strip() or "USD"

            if item.description and item.description not in ("nan", "None", ""):
                manifest.items.append(item)

        _extract_header_from_text(manifest, manifest.raw_text)

    except Exception as e:
        manifest.parse_errors.append(f"Excel parse failed: {e}")
        logger.exception("Excel parse error")

    return manifest


def _find_excel_header_row(df: pd.DataFrame) -> Optional[int]:
    """Find the row that looks like column headers."""
    header_keywords = {"description", "qty", "quantity", "value", "amount", "weight", "origin", "hs", "item"}
    for i, row in df.iterrows():
        row_lower = {str(v).lower() for v in row.values if pd.notna(v)}
        if len(row_lower & header_keywords) >= 2:
            return i
    return None


def _map_excel_columns(columns: list[str]) -> dict:
    """Map raw column names to semantic field names."""
    mapping = {}
    for col in columns:
        col_l = col.lower()
        if any(k in col_l for k in ["desc", "product", "commodity", "goods", "item name"]):
            mapping["description"] = col
        elif any(k in col_l for k in ["qty", "quantity", "pcs", "nos", "units"]):
            mapping["quantity"] = col
        elif any(k in col_l for k in ["unit price", "unit rate", "price per", "rate"]):
            mapping["unit_price"] = col
        elif any(k in col_l for k in ["total", "amount", "value", "fob", "cif"]):
            mapping["total_value"] = col
        elif any(k in col_l for k in ["weight", "wt", "gross", "net weight"]):
            mapping["weight"] = col
        elif any(k in col_l for k in ["origin", "country of origin", "coo", "made in"]):
            mapping["origin"] = col
        elif any(k in col_l for k in ["unit", "uom", "measure"]) and "unit price" not in col_l:
            mapping["unit"] = col
        elif any(k in col_l for k in ["currency", "curr"]):
            mapping["currency"] = col
    return mapping


def _parse_xml(file_path: str) -> ParsedManifest:
    manifest = ParsedManifest()
    try:
        from lxml import etree

        tree = etree.parse(file_path)
        root = tree.getroot()
        manifest.raw_text = etree.tostring(root, pretty_print=True, encoding="unicode")

        # Extract using common XML tag patterns (UN/EDIFACT, BAPLIE, custom)
        ns = {"": root.nsmap.get(None, "")} if root.nsmap.get(None) else {}

        def find_text(tags: list[str]) -> Optional[str]:
            for tag in tags:
                els = root.findall(f".//{tag}") or root.findall(f".//{{{root.nsmap.get(None, '')}}}{tag}")
                if els and els[0].text:
                    return els[0].text.strip()
            return None

        manifest.shipper_name = find_text(["Shipper", "ShipperName", "Exporter", "ExporterName", "Seller"])
        manifest.consignee_name = find_text(["Consignee", "ConsigneeName", "Importer", "ImporterName", "Buyer"])
        manifest.bill_of_lading_number = find_text(["BLNumber", "BillOfLadingNumber", "AWBNumber", "DocumentNumber"])
        manifest.port_of_loading = find_text(["PortOfLoading", "LoadPort", "Origin", "DeparturePort"])
        manifest.port_of_discharge = find_text(["PortOfDischarge", "DischargePort", "Destination", "ArrivalPort"])

        # Try to find line items
        item_tags = ["LineItem", "Item", "GoodsItem", "CargoItem", "Product"]
        for tag in item_tags:
            items_els = root.findall(f".//{tag}")
            if items_els:
                for i, el in enumerate(items_els):
                    item = ParsedItem()
                    item.line_number = i + 1

                    def el_text(t: list[str]) -> Optional[str]:
                        for tt in t:
                            found = el.find(f".//{tt}")
                            if found is not None and found.text:
                                return found.text.strip()
                        return None

                    item.description = el_text(["Description", "GoodsDescription", "CommodityName", "Name"]) or ""
                    item.quantity = _to_float(el_text(["Quantity", "Qty", "NetQuantity"]))
                    item.unit = el_text(["Unit", "UOM", "MeasurementUnit"])
                    item.unit_price = _to_float(el_text(["UnitPrice", "Price", "Rate"]))
                    item.total_value = _to_float(el_text(["TotalValue", "Amount", "Value", "CIFValue", "FOBValue"]))
                    item.weight_kg = _to_float(el_text(["Weight", "GrossWeight", "NetWeight"]))
                    item.country_of_origin = el_text(["CountryOfOrigin", "Origin", "ManufacturingCountry"])

                    if item.description:
                        manifest.items.append(item)
                break

    except Exception as e:
        manifest.parse_errors.append(f"XML parse failed: {e}")
        logger.exception("XML parse error")

    return manifest


def _parse_word(file_path: str) -> ParsedManifest:
    manifest = ParsedManifest()
    try:
        from docx import Document

        doc = Document(file_path)
        paragraphs_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

        table_texts = []
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                table_texts.append(row_text)

        manifest.raw_text = paragraphs_text + "\n\nTABLES:\n" + "\n".join(table_texts)

        # Parse tables as line items
        for table in doc.tables:
            if len(table.rows) < 2:
                continue
            header_row = [cell.text.strip().lower() for cell in table.rows[0].cells]
            col_map = _map_excel_columns(header_row)
            if not col_map.get("description"):
                continue

            for i, row in enumerate(table.rows[1:], 1):
                cells = [cell.text.strip() for cell in row.cells]
                if len(cells) < len(header_row):
                    continue
                row_dict = dict(zip(header_row, cells))

                item = ParsedItem()
                item.line_number = i
                item.description = row_dict.get(col_map.get("description", ""), "")
                item.quantity = _to_float(row_dict.get(col_map.get("quantity", ""), None))
                item.total_value = _to_float(row_dict.get(col_map.get("total_value", ""), None))
                item.weight_kg = _to_float(row_dict.get(col_map.get("weight", ""), None))
                item.country_of_origin = row_dict.get(col_map.get("origin", ""), None)

                if item.description:
                    manifest.items.append(item)

        _extract_header_from_text(manifest, manifest.raw_text)

    except Exception as e:
        manifest.parse_errors.append(f"Word parse failed: {e}")
        logger.exception("Word parse error")

    return manifest


def _extract_header_from_text(manifest: ParsedManifest, text: str) -> None:
    """Regex-based extraction of common header fields from free text."""
    patterns = {
        "shipper_name": [
            r"(?:Shipper|Exporter|Seller)[:\s]+([A-Z][A-Za-z0-9\s,&\.]{3,60})",
        ],
        "consignee_name": [
            r"(?:Consignee|Importer|Buyer)[:\s]+([A-Z][A-Za-z0-9\s,&\.]{3,60})",
        ],
        "bill_of_lading_number": [
            r"(?:B/?L\s*(?:No|Number|#)?)[:\s]+([A-Z0-9\-]{6,30})",
            r"(?:AWB|Air\s*Waybill)[:\s]+([0-9\-]{8,20})",
        ],
        "port_of_loading": [
            r"(?:Port\s+of\s+Loading|POL|Load\s+Port)[:\s]+([A-Z][A-Za-z\s]{2,30})",
        ],
        "port_of_discharge": [
            r"(?:Port\s+of\s+Discharge|POD|Discharge\s+Port)[:\s]+([A-Z][A-Za-z\s]{2,30})",
        ],
        "incoterms": [
            r"\b(FOB|CIF|CFR|EXW|DAP|DDP|FCA|CPT|CIP|DAT)\b",
        ],
        "country_of_origin": [
            r"(?:Country\s+of\s+Origin|Made\s+in|Origin)[:\s]+([A-Z][A-Za-z\s]{2,30})",
        ],
    }

    for field, pats in patterns.items():
        if getattr(manifest, field):
            continue
        for pat in pats:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                setattr(manifest, field, match.group(1).strip())
                break

    # Extract total CIF value
    if not manifest.total_cif_value:
        cif_match = re.search(
            r"(?:Total\s+CIF|CIF\s+Value|Invoice\s+Value|Total\s+Amount)[:\s]+(?:USD|EUR|GBP)?\s*([\d,]+\.?\d*)",
            text, re.IGNORECASE
        )
        if cif_match:
            manifest.total_cif_value = _to_float(cif_match.group(1))


def _extract_items_from_text(manifest: ParsedManifest, text: str) -> None:
    """
    Heuristic line-item extraction from unstructured text.
    Falls back gracefully — AI classifier will handle ambiguous descriptions.
    """
    if manifest.items:
        return  # Already parsed (e.g., from table)

    lines = text.split("\n")
    item_pattern = re.compile(
        r"^\s*(\d+)[.\)]\s+(.{10,100})\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)"
    )

    for line in lines:
        match = item_pattern.match(line)
        if match:
            item = ParsedItem()
            item.line_number = int(match.group(1))
            item.description = match.group(2).strip()
            item.quantity = _to_float(match.group(3))
            item.total_value = _to_float(match.group(4))
            manifest.items.append(item)


def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
