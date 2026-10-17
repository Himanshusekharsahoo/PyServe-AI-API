from typing import Literal

from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):
    """
    Schema for sentiment analysis prediction response.
    """

    sentiment: Literal["negative", "positive"] = Field(
        ...,
        description="Predicted sentiment classification label.",
        json_schema_extra={"example": "positive"},
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 and 1.0.",
        json_schema_extra={"example": 0.95},
    )
