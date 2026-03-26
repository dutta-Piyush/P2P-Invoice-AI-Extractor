import json
import logging
import os
import time

import dspy
import litellm
import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.exceptions import AIServiceError, ExtractionError
from models.schemas import ExtractResponse, OrderLine, _VALID_COMMODITY_IDS as _SCHEMA_COMMODITY_IDS

logger = logging.getLogger(__name__)


_COMMODITY_GROUPS = """
001=Accommodation Rentals, 002=Membership Fees, 003=Workplace Safety, 004=Consulting,
005=Financial Services, 006=Fleet Management, 007=Recruitment Services, 008=Professional Development,
009=Miscellaneous Services, 010=Insurance, 011=Electrical Engineering, 012=Facility Management Services,
013=Security, 014=Renovations, 015=Office Equipment, 016=Energy Management, 017=Maintenance,
018=Cafeteria and Kitchenettes, 019=Cleaning, 020=Audio and Visual Production, 021=Books/Videos/CDs,
022=Printing Costs, 023=Software Development for Publishing, 024=Material Costs,
025=Shipping for Production, 026=Digital Product Development, 027=Pre-production,
028=Post-production Costs, 029=Hardware, 030=IT Services, 031=Software,
032=Courier Express and Postal Services, 033=Warehousing and Material Handling,
034=Transportation Logistics, 035=Delivery Services, 036=Advertising, 037=Outdoor Advertising,
038=Marketing Agencies, 039=Direct Mail, 040=Customer Communication, 041=Online Marketing,
042=Events, 043=Promotional Materials, 044=Warehouse and Operational Equipment,
045=Production Machinery, 046=Spare Parts, 047=Internal Transportation, 048=Production Materials,
049=Consumables, 050=Maintenance and Repairs
"""


class VendorOfferSignature(dspy.Signature):
    """Extract structured procurement data from a vendor offer PDF.

    Rules:
    - Extract only what is explicitly present in the text. Do not guess or infer missing values.
    - If a field is not found, return an empty string "" for text fields, "0.0" for total_cost, and "[]" for order_lines_json.
    - All text output must be in English, even if the source PDF is in another language.
    - For order_lines_json: skip any position explicitly marked as alternative (e.g. marked with "Alt.", "Alternativ", "Alternative").
      Only include confirmed/primary line items.
    - total_cost must be the final grand total (Endsumme/total including VAT and shipping if present), not a subtotal.
    - commodity_group_id must be exactly a 3-digit ID from this list (choose the single best match):
    """ + _COMMODITY_GROUPS

    pdf_text: str = dspy.InputField(desc="Raw text extracted from a vendor offer PDF")
    vendor_name: str = dspy.OutputField(desc="Vendor company name. Return empty string if not found.")
    vat_id: str = dspy.OutputField(desc="VAT ID (Umsatzsteuer-Identifikationsnummer), e.g. DE123456789. Return empty string if not found.")
    department: str = dspy.OutputField(desc="Department name the offer is addressed to (e.g. HR, IT, Marketing). Return empty string if not explicitly mentioned.")
    order_lines_json: str = dspy.OutputField(
        desc=(
            'JSON array of order lines: [{"position_description":"...","unit_price":0.0,"amount":0.0,"unit":"...","total_price":0.0},...]. '
            'Exclude alternative positions (marked Alt., Alternativ, Alternative). '
            'Return "[]" if none found.'
        )
    )
    total_cost: str = dspy.OutputField(desc='Final grand total (Endsumme) including VAT and shipping as a decimal number (e.g. 1847.19). Return "0.0" if not found.')
    commodity_group_id: str = dspy.OutputField(desc="3-digit commodity group ID from the provided list that best matches the items. Always return exactly one ID, e.g. '043'.")


_CIRCUIT_THRESHOLD = 5
_CIRCUIT_COOLDOWN = 60.0
_DEFAULT_MAX_INPUT_CHARS = 12_000


class OpenAIExtractor:
    _VALID_COMMODITY_IDS: frozenset[str] = _SCHEMA_COMMODITY_IDS
    _COMMODITY_FALLBACK = "009"

    def __init__(self, model: str, api_key: str, ssl_verify: bool = True, max_input_chars: int = _DEFAULT_MAX_INPUT_CHARS) -> None:
        if not ssl_verify:
            # WARNING: Mutates global env vars — affects ALL HTTP clients in process.
            litellm.ssl_verify = False
            os.environ.setdefault("CURL_CA_BUNDLE", "")
            os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
            logger.warning("SSL verification disabled — corporate network mode")
        lm = dspy.LM(f"openai/{model}", api_key=api_key, temperature=0.0)
        dspy.configure(lm=lm)
        self._predict = dspy.Predict(VendorOfferSignature)
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._max_input_chars = max_input_chars

    # ── Circuit breaker ──────────────────────────────────────────────────

    def _is_circuit_open(self) -> bool:
        if self._circuit_open_until > time.monotonic():
            remaining = round(self._circuit_open_until - time.monotonic())
            logger.warning("Circuit breaker OPEN — skipping AI call (%ds remaining)", remaining)
            return True
        return False

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= _CIRCUIT_THRESHOLD:
            self._circuit_open_until = time.monotonic() + _CIRCUIT_COOLDOWN
            logger.error("Circuit breaker OPENED after %d failures", self._consecutive_failures)

    # ── AI call ──────────────────────────────────────────────────────────

    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_input_chars:
            return text
        logger.warning("PDF text truncated from %d to %d chars", len(text), self._max_input_chars)
        return text[: self._max_input_chars]

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError)),
        reraise=True,
    )
    def _call_predict(self, pdf_text: str):
        return self._predict(pdf_text=pdf_text)

    def extract(self, pdf_text: str) -> ExtractResponse:
        if self._is_circuit_open():
            raise AIServiceError("AI service is temporarily unavailable. Please fill in the fields manually.")

        pdf_text = self._truncate(pdf_text)
        logger.info("Sending %d characters to OpenAI for extraction", len(pdf_text))
        try:
            result = self._call_predict(pdf_text)
            self._record_success()
        except openai.AuthenticationError as exc:
            raise AIServiceError("OpenAI API key is invalid or has been revoked.") from exc
        except openai.RateLimitError as exc:
            self._record_failure()
            raise AIServiceError("OpenAI quota exhausted or rate-limited. Try again later.") from exc
        except openai.APIConnectionError as exc:
            self._record_failure()
            raise AIServiceError("Could not reach the OpenAI API.") from exc
        except Exception as exc:
            self._record_failure()
            raise AIServiceError(f"AI extraction failed: {exc}") from exc

        return self._to_response(result)

    # ── Response parsing ─────────────────────────────────────────────────

    def _to_response(self, result) -> ExtractResponse:
        warnings: list[str] = []
        order_lines = self._parse_order_lines(result.order_lines_json, warnings)
        total_cost = self._parse_float(result.total_cost)
        cg_id = self._validate_commodity_id(result.commodity_group_id.strip(), warnings)
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

    def _validate_commodity_id(self, value: str, warnings: list[str]) -> str:
        normalised = value.zfill(3) if value.isdigit() else value
        if normalised in self._VALID_COMMODITY_IDS:
            return normalised
        warnings.append(f"Commodity group '{value}' not valid. Defaulted to {self._COMMODITY_FALLBACK}.")
        return self._COMMODITY_FALLBACK

    def _sanity_check(self, order_lines: list[OrderLine], total_cost: float, warnings: list[str]) -> None:
        if not order_lines and total_cost > 0.0:
            warnings.append("Order lines missing but total cost found — please review.")
        if order_lines and total_cost == 0.0:
            warnings.append("Line items found but total cost missing — please review.")

    def _parse_order_lines(self, json_str: str, warnings: list[str]) -> list[OrderLine]:
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
            except (TypeError, ValueError, Exception):
                warnings.append(f"Line item {i + 1} skipped due to invalid data.")
        return lines

    def _parse_float(self, value: str) -> float:
        if not value or not value.strip():
            return 0.0
        try:
            return float(value.replace(",", ".").strip())
        except ValueError:
            return 0.0
