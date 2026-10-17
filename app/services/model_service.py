import hashlib
import os
from typing import Any, Dict, Optional

import joblib

from app.core import config
from app.core.config import DEFAULT_MODEL_PATH
from app.core.logging import logger


class ModelError(Exception):
    """Base exception for model-related failures."""

    pass


class ModelLoadError(ModelError):
    """Raised when the model artifact fails to load or is invalid."""

    pass


class ModelNotLoadedError(ModelError):
    """Raised when inference is requested but no model is loaded."""

    pass


class SentimentModelService:
    """
    Service responsible for the lifecycle and inference of the sentiment model.
    Encapsulates artifact loading, readiness validation, and execution.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        expected_sha256: Optional[str] = None,
    ) -> None:
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.expected_sha256 = expected_sha256
        self._model: Any = None
        self._is_loaded: bool = False
        self._load_error: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def load(
        self,
        path: Optional[str] = None,
        expected_sha256: Optional[str] = None,
    ) -> None:
        """
        Load and validate the model artifact from disk.
        Enforces pre-deserialization SHA-256 integrity check against a trusted digest
        before calling joblib.load to prevent arbitrary code execution from
        tampered artifacts.
        """
        target_path = path or self.model_path
        if not os.path.isabs(target_path):
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            target_path = os.path.join(base_dir, target_path)
        target_path = os.path.abspath(target_path)

        self._is_loaded = False
        self._model = None
        self._load_error = None

        if not os.path.exists(target_path):
            self._load_error = f"Model artifact not found at '{target_path}'."
            logger.warning(self._load_error)
            raise ModelLoadError(self._load_error)

        file_size = os.path.getsize(target_path)
        if file_size == 0:
            self._load_error = (
                f"Model artifact at '{target_path}' is empty (0 bytes). "
                "A trained sentiment model artifact must be provided."
            )
            logger.warning(self._load_error)
            raise ModelLoadError(self._load_error)

        # Pre-deserialization cryptographic integrity verification
        trusted_sha256 = (
            expected_sha256 or self.expected_sha256 or config.EXPECTED_MODEL_SHA256
        )

        if not trusted_sha256:
            if config.ENVIRONMENT == "production":
                self._load_error = (
                    "Model loading aborted: EXPECTED_MODEL_SHA256 is not configured "
                    "in production. Refusing to deserialize unverified model artifact."
                )
                logger.error(self._load_error)
                raise ModelLoadError(self._load_error)
        else:
            hasher = hashlib.sha256()
            try:
                with open(target_path, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                computed_sha256 = hasher.hexdigest().lower()
            except OSError as err:
                self._load_error = (
                    f"Failed to read artifact for integrity check at '{target_path}': "
                    f"{err}"
                )
                logger.error(self._load_error)
                raise ModelLoadError(self._load_error) from err

            if computed_sha256 != trusted_sha256.strip().lower():
                self._load_error = (
                    f"Model integrity verification failed for '{target_path}'. "
                    f"SHA-256 digest mismatch. Computed: {computed_sha256[:12]}..., "
                    f"Expected: {trusted_sha256.strip()[:12]}... "
                    "Artifact may be modified, incomplete, or untrusted."
                )
                logger.error(self._load_error)
                raise ModelLoadError(self._load_error)

        try:
            with open(target_path, "rb") as f:
                # Security: Loaded only after pre-deserialization integrity check
                loaded = joblib.load(f)

            if (
                not hasattr(loaded, "predict")
                or not hasattr(loaded, "predict_proba")
                or not hasattr(loaded, "classes_")
                or set(map(str, loaded.classes_)) != {"negative", "positive"}
            ):
                self._load_error = (
                    f"Loaded object from '{target_path}' is not a binary sentiment "
                    "classifier with probability support."
                )
                raise ModelLoadError(self._load_error)

            self._model = loaded
            self._is_loaded = True
            logger.info(f"Sentiment model successfully loaded from '{target_path}'.")

        except Exception as e:
            if not self._load_error:
                self._load_error = (
                    f"Failed to deserialize model from '{target_path}': {str(e)}"
                )
            logger.error(self._load_error)
            raise ModelLoadError(self._load_error) from e

    def set_model(self, model_instance: Any) -> None:
        """
        Inject a validated model instance directly (for testing/mock injection).
        """
        if not hasattr(model_instance, "predict"):
            raise ValueError("Model instance must implement a 'predict' method.")
        self._model = model_instance
        self._is_loaded = True
        self._load_error = None

    def unload(self) -> None:
        """Release the loaded model from memory."""
        self._model = None
        self._is_loaded = False
        self._load_error = None
        logger.info("Sentiment model unloaded.")

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Run inference using the loaded sentiment model.
        Extracts real label and confidence score without fabrication.
        """
        if not self.is_loaded or self._model is None:
            detail = self._load_error or "Model is not loaded."
            raise ModelNotLoadedError(f"Inference unavailable: {detail}")

        # Real model execution
        try:
            predictions = self._model.predict([text])
            sentiment_output = str(predictions[0])

            probas = self._model.predict_proba([text])[0]
            classes = list(self._model.classes_)
            confidence = float(probas[classes.index(sentiment_output)])

            return {
                "sentiment": sentiment_output,
                "confidence": round(confidence, 4),
            }
        except Exception as e:
            logger.error(f"Error during model inference: {str(e)}")
            raise ModelError(f"Model prediction failed: {str(e)}") from e


# Singleton service instance used by the application
_default_service = SentimentModelService()


def get_model_service() -> SentimentModelService:
    """Return the application's sentiment model service instance."""
    return _default_service


def predict(text: str) -> Dict[str, Any]:
    """
    Convenience function delegating to the singleton model service.
    """
    return _default_service.predict(text)
