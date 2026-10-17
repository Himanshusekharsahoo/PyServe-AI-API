from fastapi import APIRouter, Depends, HTTPException, status
from starlette.requests import Request

from app.core import security
from app.core.logging import logger
from app.core.metrics import record_prediction
from app.models.payload import TextPayload
from app.models.prediction import PredictionResponse
from app.services.model_service import ModelError, ModelNotLoadedError, predict

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

    - **Auth:** Requires API Key in header (`token: <API_KEY>`)
    - **Input:** TextPayload (`text: str`)
    - **Output:** PredictionResponse (`sentiment`, `confidence`)
    - **Errors:** 401 (unauthorized), 422 (validation error), 503 (model unavailable)
    """

    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
        )

    client_host = security.get_client_ip(request)
    logger.info(f"Received prediction request from client: {client_host}")

    try:
        result = predict(payload.text)
        record_prediction()

        response = PredictionResponse(
            sentiment=result["sentiment"],
            confidence=result["confidence"],
        )

        logger.info(
            f"Prediction successful | Sentiment={response.sentiment} | "
            f"Confidence={response.confidence}"
        )

        return response

    except ModelNotLoadedError as mnle:
        logger.warning(f"Inference rejected because model is unavailable: {mnle}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(mnle),
        ) from mnle

    except ModelError as me:
        logger.error(f"Prediction execution error: {me}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model prediction failed. Check input data or model configuration.",
        ) from me

    except Exception as e:
        logger.error(f"Unexpected prediction failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during prediction.",
        ) from e
