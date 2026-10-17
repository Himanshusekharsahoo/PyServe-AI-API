from pydantic import BaseModel, Field, field_validator


class TextPayload(BaseModel):
    """
    Schema for sentiment analysis prediction requests.
    """

    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Input text string for sentiment classification.",
        json_schema_extra={
            "example": "The customer service team resolved my issue quickly!"
        },
    )

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Input text cannot be empty or blank whitespace.")
        return stripped
