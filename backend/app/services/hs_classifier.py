"""
HS Code Classifier using Claude AI.
Classifies goods into 8-digit ITC-HS codes for Indian Customs with confidence scoring.
Target accuracy: >90%. Items below 85% confidence are flagged for manual review.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

TARIFF_DATA_PATH = Path(__file__).parent.parent / "data" / "duty_rates.json"
FTA_DATA_PATH = Path(__file__).parent.parent / "data" / "fta_rates.json"

# Load tariff data once at module level
with open(TARIFF_DATA_PATH) as f:
    TARIFF_DATA = json.load(f)

with open(FTA_DATA_PATH) as f:
    FTA_DATA = json.load(f)

CONFIDENCE_MANUAL_REVIEW_THRESHOLD = 0.85

HS_CLASSIFICATION_PROMPT = """You are an expert Indian Customs classifier specializing in ITC-HS (Indian Trade Classification based on Harmonized System) codes.

Your task is to classify the given goods description into the most accurate 8-digit ITC-HS code for Indian import purposes.

## Key Classification Rules (Chapter Notes apply):
1. HS classification is based on the ESSENTIAL CHARACTER of the goods
2. For machinery: classify by principal function (Chapter 84/85)
3. For mixtures: classify by predominant material or by GRI Rule 3(c)
4. For sets: classify as if consisting of component which gives essential character
5. Finished articles take precedence over materials (GRI Rule 2b)
6. Most specific description prevails over general (GRI Rule 3a)

## Indian Customs Specific Notes:
- Use ITC-HS 2022 Schedule 1 (Import Policy)
- 8-digit codes required (first 6 = HS, last 2 = Indian subheading)
- Consider Chapter 98 for project imports if applicable
- AIDC (Agriculture Infrastructure Development Cess) applies to specific agri items

## Available tariff data for reference:
{tariff_context}

## Goods to Classify:
Description: {description}
Country of Origin: {country_of_origin}
Additional context: {context}

## Required Output (JSON only, no other text):
{{
  "itc_hs_code": "XXXXXXXX",  // 8-digit code, no spaces or hyphens
  "hs_description": "Official HS description for this heading",
  "chapter": "XX",
  "heading": "XXXX",
  "confidence": 0.XX,  // 0.0 to 1.0
  "reasoning": "Brief explanation of classification basis and key GRI rules applied",
  "alternative_codes": ["XXXXXXXX"],  // 1-2 alternative codes if close call
  "special_notes": "Any anti-dumping duties, AIDC, or other special charges to note",
  "needs_manual_review": false  // true if confidence < 0.85 or genuinely ambiguous
}}"""


class ClassificationResult:
    def __init__(self):
        self.itc_hs_code: str = ""
        self.hs_description: str = ""
        self.chapter: str = ""
        self.heading: str = ""
        self.confidence: float = 0.0
        self.reasoning: str = ""
        self.alternative_codes: list[str] = []
        self.special_notes: str = ""
        self.needs_manual_review: bool = True
        self.error: Optional[str] = None


def classify_item(
    description: str,
    country_of_origin: Optional[str] = None,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> ClassificationResult:
    """Classify a single goods item into an ITC-HS code using Claude."""
    result = ClassificationResult()

    if not description or len(description.strip()) < 3:
        result.error = "Description too short to classify"
        result.needs_manual_review = True
        return result

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Build relevant tariff context (top chapters likely to match)
    tariff_context = _build_tariff_context(description)

    context_parts = []
    if quantity and unit:
        context_parts.append(f"Quantity: {quantity} {unit}")
    if additional_context:
        context_parts.append(additional_context)

    prompt = HS_CLASSIFICATION_PROMPT.format(
        tariff_context=tariff_context,
        description=description,
        country_of_origin=country_of_origin or "Not specified",
        context="; ".join(context_parts) if context_parts else "None",
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_response = message.content[0].text.strip()
        parsed = _parse_classification_response(raw_response)
        _populate_result(result, parsed)

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        result.error = f"API error: {e}"
        result.needs_manual_review = True
    except Exception as e:
        logger.exception(f"Classification error for '{description}': {e}")
        result.error = str(e)
        result.needs_manual_review = True

    return result


def classify_manifest_items(items: list[dict]) -> list[ClassificationResult]:
    """
    Classify multiple items in a single batched Claude call for efficiency.
    Items should have keys: description, country_of_origin, quantity, unit.
    """
    if not items:
        return []

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += f"\nItem {i}:\n"
        items_text += f"  Description: {item.get('description', '')}\n"
        if item.get("country_of_origin"):
            items_text += f"  Country of Origin: {item['country_of_origin']}\n"
        if item.get("quantity"):
            items_text += f"  Quantity: {item['quantity']} {item.get('unit', '')}\n"

    tariff_context = _build_tariff_context(" ".join(i.get("description", "") for i in items))

    batch_prompt = f"""You are an expert Indian Customs ITC-HS classifier. Classify ALL items below into 8-digit ITC-HS codes.

## Tariff Reference Data:
{tariff_context}

## Items to Classify:
{items_text}

## Output: Return a JSON array with one object per item (same order). Each object:
{{
  "item_number": N,
  "itc_hs_code": "XXXXXXXX",
  "hs_description": "Official HS description",
  "chapter": "XX",
  "heading": "XXXX",
  "confidence": 0.XX,
  "reasoning": "Classification basis and GRI rules applied",
  "alternative_codes": [],
  "special_notes": "",
  "needs_manual_review": false
}}

Return ONLY the JSON array. No other text."""

    results = [ClassificationResult() for _ in items]

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": batch_prompt}],
        )
        raw_response = message.content[0].text.strip()

        # Extract JSON array
        json_match = re.search(r"\[.*\]", raw_response, re.DOTALL)
        if json_match:
            parsed_list = json.loads(json_match.group())
            for parsed in parsed_list:
                idx = parsed.get("item_number", 1) - 1
                if 0 <= idx < len(results):
                    _populate_result(results[idx], parsed)
        else:
            raise ValueError("No JSON array found in response")

    except Exception as e:
        logger.exception(f"Batch classification error: {e}")
        # Fall back to individual classification
        for i, item in enumerate(items):
            results[i] = classify_item(
                description=item.get("description", ""),
                country_of_origin=item.get("country_of_origin"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
            )

    return results


def _build_tariff_context(description: str) -> str:
    """Select the most relevant chapters from the tariff database based on keywords."""
    desc_lower = description.lower()

    priority_chapters = []

    keyword_chapter_map = {
        ("phone", "mobile", "smartphone", "tablet", "laptop", "computer", "processor", "chip", "circuit"): ["84", "85"],
        ("motor", "engine", "pump", "compressor", "generator", "turbine", "machine", "equipment"): ["84"],
        ("cable", "wire", "switch", "transformer", "relay", "semiconductor", "led", "diode"): ["85"],
        ("garment", "apparel", "clothing", "shirt", "trouser", "jacket", "dress", "textile", "fabric", "cotton", "polyester"): ["61", "62", "63"],
        ("shoe", "boot", "footwear", "sandal", "slipper"): ["64"],
        ("plastic", "polymer", "resin", "pvc", "hdpe", "ldpe", "pp "): ["39"],
        ("steel", "iron", "metal", "pipe", "tube", "bolt", "nut", "rod", "wire rod"): ["72", "73"],
        ("car", "vehicle", "automobile", "motorcycle", "auto part", "spare part"): ["87"],
        ("medicine", "drug", "pharma", "vaccine", "tablet ", "capsule", "injection"): ["30"],
        ("medical", "instrument", "surgical", "diagnostic", "spectacle", "optical"): ["90"],
        ("furniture", "sofa", "chair", "table", "bed", "mattress", "lamp"): ["94"],
        ("perfume", "cosmetic", "beauty", "skincare", "hair", "cream", "lotion"): ["33"],
        ("toy", "game", "sport", "ball", "racket", "fitness"): ["95"],
        ("fruit", "vegetable", "food", "nut", "cashew", "almond", "apple"): ["08"],
        ("oil", "petroleum", "fuel", "diesel", "petrol", "lubricant"): ["27"],
    }

    for keywords, chapters in keyword_chapter_map.items():
        if any(kw in desc_lower for kw in keywords):
            for ch in chapters:
                if ch not in priority_chapters:
                    priority_chapters.append(ch)

    # Always include at least the top 3 guessed chapters
    if not priority_chapters:
        priority_chapters = ["84", "85", "39"]  # Most common import categories

    context_parts = []
    for chapter in priority_chapters[:4]:
        chapter_data = TARIFF_DATA.get(chapter)
        if chapter_data:
            context_parts.append(f"Chapter {chapter}: {chapter_data['description']}")
            for code, info in list(chapter_data.get("subcategories", {}).items())[:10]:
                context_parts.append(f"  {code}: {info['description']} | BCD: {info['bcd']}% | IGST: {info['igst']}%")

    return "\n".join(context_parts)


def _parse_classification_response(raw: str) -> dict:
    """Extract JSON from Claude's response."""
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return json.loads(raw)


def _populate_result(result: ClassificationResult, parsed: dict) -> None:
    result.itc_hs_code = str(parsed.get("itc_hs_code", "")).replace("-", "").replace(" ", "")
    result.hs_description = parsed.get("hs_description", "")
    result.chapter = parsed.get("chapter", result.itc_hs_code[:2] if result.itc_hs_code else "")
    result.heading = parsed.get("heading", result.itc_hs_code[:4] if result.itc_hs_code else "")
    result.confidence = float(parsed.get("confidence", 0.0))
    result.reasoning = parsed.get("reasoning", "")
    result.alternative_codes = parsed.get("alternative_codes", [])
    result.special_notes = parsed.get("special_notes", "")
    result.needs_manual_review = (
        parsed.get("needs_manual_review", False)
        or result.confidence < CONFIDENCE_MANUAL_REVIEW_THRESHOLD
    )
