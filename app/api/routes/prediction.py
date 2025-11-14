from fastapi import APIRouter, Depends, HTTPException, status
from starlette.requests import Request

from app.core import security
from app.core.logging import logger
from app.models.payload import TextPayload
from app.models.prediction import PredictionResponse
from app.services.model_service import predict


router = APIRouter()


@router.post(
    "/predict",
    response_model=PredictionResponse,
    name="predict",
    summary="Run sentiment analysis on input text",
    description=(
        "Takes an input text string, processes it using the loaded ML model, "
        "and returns a sentiment label along with a confidence score."
    ),
)
def post_predict(
    request: Request,
    payload: TextPayload,
    authenticated: bool = Depends(security.validate_request),
) -> PredictionResponse:
    """
    ### Predict Sentiment  
    This endpoint runs the ML model to classify sentiment on input text.

    - **Auth:** Requires API Key / JWT depending on your config  
    - **Input:** TextPayload (`text: str`)  
    - **Output:** PredictionResponse (`sentiment`, `confidence`)  
    - **Errors:** 401 (unauthorized), 500 (model failure)
    """

    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
        )

    logger.info(f"Received prediction request from: {request.client.host}")

    try:
        result = predict(payload.text)

        response = PredictionResponse(
            sentiment=result["sentiment"],
            confidence=result["confidence"]
        )

        logger.info(
            f"Prediction successful | Sentiment={response.sentiment} | "
            f"Confidence={response.confidence}"
        )

        return response

    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed. Check model or input data.",
        )
