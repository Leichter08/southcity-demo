import logging
from contextlib import closing
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
import pyodbc
from starlette.concurrency import run_in_threadpool

from app.database import DatabaseConfigurationError, get_connection
from app.llm import LLMConfigurationError
from app.schemas import PromptRequest, PromptResponse, UserRole
from app.security import GuardrailError, evaluate_injection_with_llm
from app.text_to_sql import (
    ModelResponseError,
    RoleAccessError,
    SQLValidationError,
    execute_query,
    generate_sql,
    synthesize_response,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/db/health")
def check_database() -> dict[str, str]:
    try:
        with closing(get_connection()) as connection:
            database_name = connection.execute("SELECT DB_NAME()").fetchone()[0]
    except (pyodbc.Error, DatabaseConfigurationError) as exc:
        logger.exception("SQL Server connection check failed")
        raise HTTPException(status_code=503, detail="SQL Server connection failed") from exc

    return {"status": "ok", "database": database_name}


@router.post("/ask", response_model=PromptResponse)
async def ask_llm(
    request: PromptRequest,
    user_role: Annotated[UserRole, Header(alias="user_role")],
) -> PromptResponse:
    logger.info("Starting /ask request for role=%s", user_role)
    try:
        is_injection = await evaluate_injection_with_llm(request.prompt)
    except GuardrailError as exc:
        logger.error("Prompt injection guard unavailable")
        raise HTTPException(
            status_code=503, detail="Security check is unavailable"
        ) from exc

    if is_injection:
        logger.warning("Prompt injection rejected for /ask request")
        raise HTTPException(
            status_code=400,
            detail="Peringatan Keamanan: Permintaan Anda terdeteksi melanggar kebijakan keamanan sistem.",
        )

    try:
        sql_query = await generate_sql(request.prompt, user_role)
        logger.info("SQL generated for /ask request")
        results = await run_in_threadpool(execute_query, sql_query, user_role)
        logger.info("Database query completed for /ask request")
        answer = await synthesize_response(request.prompt, sql_query, results)
    except RoleAccessError as exc:
        logger.warning("Access denied for /ask request: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SQLValidationError as exc:
        logger.warning("SQL validation rejected /ask request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server query failed")
        raise HTTPException(status_code=503, detail="SQL Server query failed") from exc
    except DatabaseConfigurationError as exc:
        logger.exception("SQL Server configuration failed")
        raise HTTPException(
            status_code=503, detail="SQL Server configuration failed"
        ) from exc
    except LLMConfigurationError as exc:
        logger.exception("Language model configuration failed")
        raise HTTPException(
            status_code=503, detail="Language model configuration failed"
        ) from exc
    except ModelResponseError as exc:
        logger.exception("Text-to-SQL processing failed")
        raise HTTPException(status_code=502, detail="Text-to-SQL processing failed") from exc

    logger.info("Completed /ask request for role=%s", user_role)
    return PromptResponse(answer=answer)
