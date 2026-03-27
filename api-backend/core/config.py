import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_origins(raw: str) -> list[str]:
	return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
	app_name: str
	app_version: str
	environment: str
	log_level: str
	host: str
	port: int
	allowed_origins: list[str]
	openai_api_key: str
	openai_model: str
	openai_temperature: float
	openai_top_p: float
	ssl_verify: bool
	max_pdf_chars: int  # input truncation budget (chars sent to OpenAI)


def get_settings() -> Settings:
	api_key = os.getenv("OPENAI_API_KEY", "")
	if not api_key.strip():
		raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
	return Settings(
		app_name=os.getenv("APP_NAME", "Procurement API"),
		app_version=os.getenv("APP_VERSION", "0.1.0"),
		environment=os.getenv("ENVIRONMENT", "development"),
		log_level=os.getenv("LOG_LEVEL", "INFO"),
		host=os.getenv("HOST", "127.0.0.1"),
		port=int(os.getenv("PORT", "8000")),
		allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")),
		openai_api_key=api_key,
		openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
		openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
		openai_top_p=float(os.getenv("OPENAI_TOP_P", "0.2")),
		ssl_verify=os.getenv("SSL_VERIFY", "true").lower() != "false",
		max_pdf_chars=int(os.getenv("MAX_PDF_CHARS", "12000")),
	)


settings = get_settings()
