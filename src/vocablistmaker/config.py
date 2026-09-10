"""Zentrale Einstellungen der Anwendung."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_MODEL = "claude-opus-5"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "ja", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    """Alle Stellschrauben an einem Ort - überschreibbar per Umgebungsvariable."""

    # --- Sprachmodell ---
    api_key: str | None = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: os.environ.get("VLM_MODEL", DEFAULT_MODEL))
    use_llm: bool = field(default_factory=lambda: _env_bool("VLM_USE_LLM", True))
    effort: str = field(default_factory=lambda: os.environ.get("VLM_EFFORT", "high"))
    max_tokens: int = field(default_factory=lambda: _env_int("VLM_MAX_TOKENS", 16000))
    max_retries: int = field(default_factory=lambda: _env_int("VLM_MAX_RETRIES", 3))
    timeout_seconds: float = field(default_factory=lambda: float(_env_int("VLM_TIMEOUT", 300)))
    batch_size: int = field(default_factory=lambda: _env_int("VLM_BATCH_SIZE", 30))

    # --- Testaufbau ---
    words_per_test: int = field(default_factory=lambda: _env_int("VLM_WORDS_PER_TEST", 30))
    max_repair_rounds: int = field(default_factory=lambda: _env_int("VLM_REPAIR_ROUNDS", 3))

    # --- Ausgabe ---
    heading_test1: str = field(default_factory=lambda: os.environ.get("VLM_HEADING1", "Test 1"))
    heading_test2: str = field(default_factory=lambda: os.environ.get("VLM_HEADING2", "Test 2"))
    column_titles: tuple[str, str, str, str] = ("Nr.", "Deutsch", "English", "Example sentence")
    font_name: str = field(default_factory=lambda: os.environ.get("VLM_FONT", "Century Gothic"))
    # 10 pt statt der 11 pt der Vorlage: Bei 30 Einträgen mit zweizeiligen
    # Beispielsätzen liefe eine Liste bei 11 pt auf eine zweite Seite.
    font_size_pt: float = field(default_factory=lambda: float(os.environ.get("VLM_FONT_SIZE", 10)))
    row_height_twips: int = field(default_factory=lambda: _env_int("VLM_ROW_HEIGHT", 340))
    bold_target_word: bool = field(default_factory=lambda: _env_bool("VLM_BOLD_TARGET", True))
    page_break_between_tests: bool = field(
        default_factory=lambda: _env_bool("VLM_PAGE_BREAK", True)
    )
    #: Wenn False, bricht die Pipeline ab, statt Beispielsätze aus festen
    #: Mustern zu erzeugen. Für kuratierte Inhalte ist das die richtige
    #: Einstellung: lieber ein klarer Fehler als blasse Füllsätze.
    allow_template_sentences: bool = field(
        default_factory=lambda: _env_bool("VLM_ALLOW_TEMPLATE_SENTENCES", True)
    )

    # --- Reproduzierbarkeit ---
    seed: int = field(default_factory=lambda: _env_int("VLM_SEED", 20240607))

    @property
    def target_total(self) -> int:
        return self.words_per_test * 2
