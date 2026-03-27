"""
Extraction response parser utility for OpenAIExtractor.
"""
import json
from typing import Any, Dict
from models.schemas import ExtractResponse, OrderLine

class ExtractionResponseParser:
    """Handles parsing and validation of AI extraction results."""
    def __init__(self, valid_commodity_ids, fallback):
        """
        Initialize the parser with a set of valid commodity IDs and a fallback value.
        Args:
            valid_commodity_ids: Set or list of valid commodity group IDs.
            fallback: Fallback commodity group ID to use if validation fails.
        """
        self._valid_commodity_ids = valid_commodity_ids
        self._fallback = fallback

    def to_response(self, result, group_result, category: str, warnings: list[str]) -> ExtractResponse:
        """
        Convert raw AI extraction results into a validated ExtractResponse object.
        Args:
            result: The main extraction result object from the AI model.
            group_result: The result object for commodity group prediction.
            category: The selected commodity category (string).
            warnings: List to append any warnings or validation issues.
        Returns:
            ExtractResponse: Structured, validated procurement data.
        """
        order_lines = self._parse_order_lines(result.order_lines_json, warnings)
        total_cost = self._parse_float(result.total_cost)
        cg_id = self._validate_commodity_id(group_result.commodity_group_id.strip(), warnings, category)
        self._sanity_check(order_lines, total_cost, warnings)
        return ExtractResponse(
            vendor_name=result.vendor_name.strip(),
            vat_id=result.vat_id.strip(),
            department=result.department.strip(),
            order_lines=order_lines,
            total_cost=total_cost,
            commodity_group_id=cg_id,
            warnings=warnings,
        )

    # --- Parsing and validation helpers ---
    def _parse_order_lines(self, json_str: str, warnings: list[str]) -> list[OrderLine]:
        """
        Parse a JSON string into a list of OrderLine objects.
        Args:
            json_str: JSON string representing order lines.
            warnings: List to append warnings if parsing fails or data is invalid.
        Returns:
            List[OrderLine]: Parsed order lines, or empty list if parsing fails.
        """
        if not json_str or json_str.strip() in ("[]", ""):
            return []
        try:
            raw_lines = json.loads(json_str)
        except json.JSONDecodeError:
            warnings.append("Order lines could not be parsed — please fill them in manually.")
            return []
        lines: list[OrderLine] = []
        for i, raw in enumerate(raw_lines):
            try:
                lines.append(OrderLine(**raw))
            except Exception:
                warnings.append(f"Line item {i + 1} skipped due to invalid data.")
        return lines

    def _parse_float(self, value: str) -> float:
        """
        Safely parse a string value into a float, handling empty or malformed input.
        Args:
            value: String representation of a number (may use comma or dot as decimal separator).
        Returns:
            float: Parsed float value, or 0.0 if parsing fails.
        """
        if not value or not value.strip():
            return 0.0
        try:
            return float(value.replace(",", ".").strip())
        except ValueError:
            return 0.0

    def _validate_commodity_id(self, comm_id: str, warnings: list[str], category: str = "") -> str:
        """
        Validate and normalize a commodity group ID for a given category.
        Args:
            comm_id: The commodity group ID to validate (string).
            warnings: List to append warnings if validation fails.
            category: The selected commodity category (string).
        Returns:
            str: A valid commodity group ID (normalized or fallback).
        """
        from services.openai_extractor import _CATEGORY_IDS  # Avoid circular import
        normalised = comm_id.zfill(3) if comm_id.isdigit() else comm_id # Zero-pad numeric IDs to 3 digits
        allowed = _CATEGORY_IDS.get(category, []) # Get allowed commodity IDs for the selected category
        if allowed and normalised not in allowed:
            fallback = self._fallback # Set to a default fallback value of 009 (Miscellaneous)
            # fallback = allowed[0]
            warnings.append(
                f"Commodity group '{normalised}' is not in category '{category}'. "
                f"Defaulted to fallback group: {fallback}."
            )
            return fallback
        if normalised in self._valid_commodity_ids:
            return normalised
        warnings.append(f"Commodity group '{comm_id}' not valid. Defaulted to {self._fallback}.")
        return self._fallback

    def _sanity_check(self, order_lines: list[OrderLine], total_cost: float, warnings: list[str]) -> None:
        """
        Perform consistency checks between order lines and total cost, appending warnings if needed.
        Args:
            order_lines: List of parsed OrderLine objects.
            total_cost: Parsed total cost value.
            warnings: List to append any detected inconsistencies.
        """
        if not order_lines and total_cost > 0.0:
            warnings.append("Order lines missing but total cost found — please review.")
        if order_lines and total_cost == 0.0:
            warnings.append("Line items found but total cost missing — please review.")
