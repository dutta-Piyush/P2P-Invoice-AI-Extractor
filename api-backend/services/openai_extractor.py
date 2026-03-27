# --- Standard and third-party imports ---
import logging
import os
import json
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

# --- Project imports ---
from core.circuit_breaker import CircuitBreaker
from core.extraction_response_parser import ExtractionResponseParser
from core.exceptions import AIServiceError, ExtractionError
from models.schemas import ExtractResponse, OrderLine, _VALID_COMMODITY_IDS as _SCHEMA_COMMODITY_IDS
# --- Commodity catalog imports ---
from core.commodity_catalog import (
    COMMODITY_IDS,
    build_category_ids,
    build_commodity_groups_text,
    build_valid_categories_str,
    build_id_to_name,
    category_groups_text,
)

logger = logging.getLogger(__name__)

# Build derived structures once
_CATEGORY_IDS = build_category_ids()
_COMMODITY_GROUPS = build_commodity_groups_text()
_VALID_CATEGORIES_STR = build_valid_categories_str(_CATEGORY_IDS)
_ID_TO_NAME = build_id_to_name()


class VendorOfferSignature(dspy.Signature):
    """Extract structured procurement data from a vendor offer PDF.

    Rules:
    - Extract only what is explicitly present in the text. Do not guess or infer missing values.
    - If a field is not found, return an empty string "" for text fields, "0.0" for total_cost, and "[]" for order_lines_json.
    - All text output must be in English, even if the source PDF is in another language.
    - For order_lines_json: skip any position explicitly marked as alternative (e.g. marked with "Alt.", "Alternativ", "Alternative").
      Only include confirmed/primary line items.
    - total_cost must be the final grand total (Endsumme/total including VAT and shipping if present), not a subtotal.
    - For department: Return empty string if department name not found.
    - For commodity_category: Check the *FULL LIST* of category and commodity group list below to understand what each category covers before taking a decision.
    """ + _COMMODITY_GROUPS

    pdf_text: str = dspy.InputField(desc="Raw text extracted from a vendor offer PDF")
    vendor_name: str = dspy.OutputField(desc="Vendor company name is the company name that issued the offer. Vendor cannot be Lio Technologies GmbH. Return empty string if not found.")
    vat_id: str = dspy.OutputField(desc="VAT ID (USt-IdNr. or Umsatzsteuer-Identifikationsnummer), e.g. DE123456789. Return empty string if not found.")
    department: str = dspy.OutputField(desc="Return empty string.")
    order_lines_json: str = dspy.OutputField(
        desc=(
            'JSON array of order lines: [{"position_description":"...","unit_price":0.0,"amount":0.0,"unit":"...","discount":0.0,"total_price":0.0},...]. '
            'discount is a percentage (0–100) if a line-level discount is stated, otherwise 0.0. '
            'Exclude alternative positions (marked Alt., Alternativ, Alternative). '
            'Return "[]" if none found.'
        )
    )
    total_cost: str = dspy.OutputField(desc='Final grand total (Endsumme) including VAT and shipping as a decimal number (e.g. 1847.19). Return "0.0" if not found.')
    item_summary: str = dspy.OutputField(desc="Brief English description of what the items/services in this offer actually are (translate from German if needed), including their purpose or use context.")
    commodity_category: str = dspy.OutputField(desc=f"You MUST return exactly one of these category names: {_VALID_CATEGORIES_STR}. Choose the one that best matches the item_summary you just wrote. Do not invent a new category name.")


class CommodityGroupSignature(dspy.Signature):
    """Select the best matching commodity group ID from the provided list.
    You MUST return one of the IDs exactly as written in category_groups. Do not invent or modify any ID."""

    item_summary: str = dspy.InputField(desc="English description of the items/services in the offer.")
    commodity_category: str = dspy.InputField(desc="The already-selected category.")
    category_groups: str = dspy.InputField(desc="Complete list of valid commodity groups for the chosen category, in the format ID=Name. You MUST pick one ID from this list only.")
    commodity_group_id: str = dspy.OutputField(desc="3-digit commodity group ID copied exactly from category_groups above. Return only the numeric ID, nothing else.")


_CIRCUIT_THRESHOLD = 5
_CIRCUIT_COOLDOWN = 60.0
_DEFAULT_MAX_INPUT_CHARS = 12_000



# Main Extractor Class
class OpenAIExtractor:
    """Extracts structured procurement data from PDF text using OpenAI."""
    _VALID_COMMODITY_IDS: frozenset[str] = _SCHEMA_COMMODITY_IDS
    _COMMODITY_FALLBACK = "009"

    def __init__(self, settings) -> None:
        # SSL and LLM setup
        if not settings.ssl_verify:
            litellm.ssl_verify = False
            os.environ.setdefault("CURL_CA_BUNDLE", "")
            os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
            logger.warning("SSL verification disabled — corporate network mode")
        lm = dspy.LM(
            f"openai/{settings.openai_model}",
            api_key=settings.openai_api_key,
            temperature=settings.openai_temperature,
            top_p=settings.openai_top_p,
        )
        dspy.configure(lm=lm)
        self._predict = dspy.Predict(VendorOfferSignature)
        self._predict_group = dspy.Predict(CommodityGroupSignature)
        self._max_input_chars = settings.max_pdf_chars
        self._circuit = CircuitBreaker(_CIRCUIT_THRESHOLD, _CIRCUIT_COOLDOWN)
        self._parser = ExtractionResponseParser(self._VALID_COMMODITY_IDS, self._COMMODITY_FALLBACK)

    # Truncation logic to stay within token limits and prevent excessive costs
    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_input_chars:
            return text
        logger.warning("PDF text truncated from %d to %d chars", len(text), self._max_input_chars)
        return text[: self._max_input_chars]

    def _validate_category(self, category: str, warnings: list[str]) -> str:
        if category in _CATEGORY_IDS:
            return category
        for valid in _CATEGORY_IDS:
            if valid.lower() == category.lower():
                return valid
        warnings.append(f"Category '{category}' is not valid. Defaulted to 'General Services'.")
        return "General Services"

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError)),
        reraise=True,
    )
    def _call_predict(self, pdf_text: str):
        return self._predict(pdf_text=pdf_text)

    def extract(self, pdf_text: str) -> ExtractResponse:
        """Main entry: extract structured data from raw PDF text using OpenAI."""
        if self._circuit.is_open():
            raise AIServiceError("AI service is temporarily unavailable. Please fill in the fields manually.")

        pdf_text = self._truncate(pdf_text)
        logger.info("Sending %d characters to OpenAI for extraction", len(pdf_text))
        try:
            result = self._call_predict(pdf_text)
            warnings: list[str] = []
            category = getattr(result, "commodity_category", "").strip()
            category = self._validate_category(category, warnings)
            group_result = self._predict_group(
                item_summary=result.item_summary,
                commodity_category=category,
                category_groups=category_groups_text(category, _CATEGORY_IDS, _ID_TO_NAME),
            )
            self._circuit.record_success()
        except openai.AuthenticationError as exc:
            raise AIServiceError("OpenAI API key is invalid or has been revoked.") from exc
        except openai.RateLimitError as exc:
            self._circuit.record_failure()
            raise AIServiceError("OpenAI quota exhausted or rate-limited. Try again later.") from exc
        except openai.APIConnectionError as exc:
            self._circuit.record_failure()
            raise AIServiceError("Could not reach the OpenAI API.") from exc
        except Exception as exc:
            self._circuit.record_failure()
            raise AIServiceError(f"AI extraction failed: {exc}") from exc

        return self._parser.to_response(result, group_result, category, warnings) # group_result is sending the predicted commodity group ID

