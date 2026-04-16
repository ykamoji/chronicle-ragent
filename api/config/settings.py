import json
import os
import logging

logger = logging.getLogger(__name__)

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")


class AppSettings:
    """Singleton that holds runtime-configurable settings loaded from settings.json."""

    def __init__(self):
        self._model_list = []
        self._active_model = None  # dict with name, model, delay
        self._delay_override = None  # int | None
        self._ingestion = {"parallel": True, "extractorRateLimit": 8, "embedderRateLimit": 25}
        self._load()

    # ── Bootstrap ──────────────────────────────────────────────────────

    def _load(self):
        """Load modelList from disk and determine the default active model."""
        try:
            with open(_SETTINGS_PATH, "r") as f:
                data = json.load(f)
            self._model_list = data.get("modelList", [])
            self._ingestion = data.get("ingestion", {"parallel": True, "extractorRateLimit": 8, "embedderRateLimit": 25})
        except Exception as e:
            logger.error(f"Failed to load settings.json: {e}")
            self._model_list = []

        # Default to the model marked as default, or the first one in the list
        default = next(
            (m for m in self._model_list if m.get("default") is True),
            self._model_list[0] if self._model_list else None,
        )
        self._active_model = default

    # ── Getters ────────────────────────────────────────────────────────

    def get_model(self) -> str:
        """Returns the model id string for API calls."""
        if self._active_model:
            return self._active_model["model"]
        return ""

    def get_model_info(self) -> dict:
        """Returns the full active model dict (name, model, delay)."""
        return self._active_model or {}

    def get_model_list(self) -> list:
        return self._model_list

    def get_delay(self) -> int:
        """Returns the effective delay (override wins over model default)."""
        if self._delay_override is not None:
            return self._delay_override
        if self._active_model:
            return self._active_model.get("delay", 10)
        return 10

    def get_delay_override(self):
        """Returns the delay override value, or None if not set."""
        return self._delay_override

    def get_thinking(self):
        """Return the thinking enable setting."""
        if self._active_model:
            return self._active_model.get("thinking", False)
        return False

    def get_ingestion_parallel(self) -> bool:
        """Returns whether parallel embedding is enabled."""
        return self._ingestion.get("parallel", True)

    def get_extractor_rate_limit(self) -> int:
        """Returns the rate limit for metadata extraction."""
        return self._ingestion.get("extractorRateLimit", 8)

    def get_embedder_rate_limit(self) -> int:
        """Returns the rate limit for document embedding."""
        return self._ingestion.get("embedderRateLimit", 25)

    # ── Setters ────────────────────────────────────────────────────────

    def set_model(self, model_id: str) -> bool:
        """Activates a model by its id. Returns True on success."""
        match = next((m for m in self._model_list if m["model"] == model_id), None)
        if match:
            self._active_model = match
            logger.info(f"Active model changed to: {match['name']} ({model_id})")
            return True
            
        logger.warning(f"Model id '{model_id}' not found in settings.")
        return False

    def set_delay_override(self, value) -> None:
        """Sets a manual delay override. Pass None to clear."""
        if value is None:
            self._delay_override = None
            logger.info("Delay override cleared — using model default.")
        else:
            self._delay_override = int(value)
            logger.info(f"Delay override set to {self._delay_override}s")
        self._save()

    def set_ingestion_parallel(self, enabled: bool) -> None:
        """Sets whether parallel embedding is enabled."""
        self._ingestion["parallel"] = bool(enabled)
        logger.info(f"Ingestion parallel set to {self._ingestion['parallel']}")
        self._save()

    def set_extractor_rate_limit(self, value: int) -> None:
        """Sets the rate limit for metadata extraction."""
        self._ingestion["extractorRateLimit"] = int(value)
        logger.info(f"Extractor rate limit set to {value}")
        self._save()

    def set_embedder_rate_limit(self, value: int) -> None:
        """Sets the rate limit for document embedding."""
        self._ingestion["embedderRateLimit"] = int(value)
        logger.info(f"Embedder rate limit set to {value}")
        self._save()

    # ── Serialisation ──────────────────────────────────────────────────

    def _save(self):
        """Save current configuration to settings.json."""
        try:
            with open(_SETTINGS_PATH, "r") as f:
                data = json.load(f)
            
            data["modelList"] = self._model_list
            data["ingestion"] = self._ingestion           
            with open(_SETTINGS_PATH, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save settings.json: {e}")

    def to_dict(self) -> dict:
        return {
            "modelList": self._model_list,
            "activeModel": self._active_model,
            "delayOverride": self._delay_override,
            "ingestion": self._ingestion
        }


# ── Global singleton ───────────────────────────────────────────────────
app_settings = AppSettings()
