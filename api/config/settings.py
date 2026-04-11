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
        self._load()

    # ── Bootstrap ──────────────────────────────────────────────────────

    def _load(self):
        """Load modelList from disk and default active model to gemini-3.1-flash-lite-preview."""
        try:
            with open(_SETTINGS_PATH, "r") as f:
                data = json.load(f)
            self._model_list = data.get("modelList", [])
        except Exception as e:
            logger.error(f"Failed to load settings.json: {e}")
            self._model_list = []

        # Default to gemini-3.1-flash-lite-preview
        default = next(
            (m for m in self._model_list if m["model"] == "gemini-3.1-flash-lite-preview"),
            self._model_list[0] if self._model_list else None,
        )
        self._active_model = default

    # ── Getters ────────────────────────────────────────────────────────

    def get_model(self) -> str:
        """Returns the model id string for API calls."""
        if self._active_model:
            return self._active_model["model"]
        return "gemini-3.1-flash-lite-preview"

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

    # ── Serialisation ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "modelList": self._model_list,
            "activeModel": self._active_model,
            "delayOverride": self._delay_override,
        }


# ── Global singleton ───────────────────────────────────────────────────
app_settings = AppSettings()
