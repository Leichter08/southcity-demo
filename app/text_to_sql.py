import json
import logging
import re
from contextlib import closing
from typing import Any
from xml.etree import ElementTree

import sqlparse
from sqlparse import tokens as sql_tokens

from app.database import get_connection
from app.llm import create_chat_model, get_temperature
from app.prompts import (
    ERP_SCHEMA_PROMPT,
    RESPONSE_SYNTHESIS_PROMPT,
    SQL_GENERATION_PROMPT,
)

logger = logging.getLogger(__name__)

MAX_RESULT_ROWS = 200
FORBIDDEN_KEYWORDS = {
    "ALTER",
    "BULK",
    "CREATE",
    "DELETE",
    "DENY",
    "DROP",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "INSERT",
    "INTO",
    "MERGE",
    "OPENQUERY",
    "OPENROWSET",
    "OPENDATASOURCE",
    "RECONFIGURE",
    "REVOKE",
    "TRUNCATE",
    "UPDATE",
    "USE",
    "WAITFOR",
}


class SQLValidationError(ValueError):
    pass


class RoleAccessError(PermissionError):
    pass


class ModelResponseError(RuntimeError):
    pass


def validate_sql(sql_query: str, user_role: str) -> None:
    query = sql_query.strip()
    statements = [
        statement for statement in sqlparse.parse(query) if str(statement).strip()
    ]

    if len(statements) != 1 or statements[0].get_type().upper() != "SELECT":
        raise SQLValidationError("Only a single SELECT query is permitted.")

    for token in statements[0].flatten():
        if token.ttype in sql_tokens.Comment:
            raise SQLValidationError("SQL comments are not permitted.")
        if token.ttype in sql_tokens.Literal.String:
            continue
        if re.search(
            r"\b(?:%s)\b" % "|".join(FORBIDDEN_KEYWORDS),
            token.value,
            re.IGNORECASE,
        ):
            raise SQLValidationError("The query contains a forbidden SQL operation.")

    if user_role == "Sales_Staff" and re.search(
        r"\bGL_Journals\b", query, re.IGNORECASE
    ):
        raise RoleAccessError("Sales_Staff cannot access General Ledger data.")


def execute_query(sql_query: str, user_role: str) -> dict[str, Any]:
    validate_sql(sql_query, user_role)
    with closing(get_connection()) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(sql_query)
            if cursor.description is None:
                raise SQLValidationError("The query did not return a result set.")

            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(MAX_RESULT_ROWS + 1)
            truncated = len(rows) > MAX_RESULT_ROWS
            results = [dict(zip(columns, row)) for row in rows[:MAX_RESULT_ROWS]]

    return {"rows": results, "truncated": truncated}


def get_schema_for_role(user_role: str) -> str:
    if user_role != "Sales_Staff":
        return ERP_SCHEMA_PROMPT

    root = ElementTree.fromstring(ERP_SCHEMA_PROMPT)
    for parent in root.iter():
        for table in list(parent):
            if table.tag == "table" and table.get("name") == "GL_Journals":
                parent.remove(table)
    return ElementTree.tostring(root, encoding="unicode")


async def generate_sql(question: str, user_role: str) -> str:
    schema = get_schema_for_role(user_role)
    system_prompt = SQL_GENERATION_PROMPT.format(
        schema=schema,
        user_question=question,
    )
    temperature = get_temperature("SQL_GENERATION_TEMPERATURE")
    response = await create_chat_model(temperature=temperature).ainvoke(
        [("system", system_prompt), ("human", question)]
    )
    if not isinstance(response.content, str) or not response.content.strip():
        raise ModelResponseError("The language model returned an empty SQL response.")

    logger.info("LLM SQL generation output:\n%s", response.content)
    generated_sql = response.content.strip()
    generated_sql = re.sub(
        r"^```(?:sql)?\s*|\s*```$", "", generated_sql, flags=re.IGNORECASE
    )
    return generated_sql.strip()


async def synthesize_response(
    question: str,
    sql_query: str,
    query_results: dict[str, Any],
) -> str:
    context = json.dumps(
        {
            "question": question,
            "executed_sql": sql_query,
            "database_results": query_results,
        },
        ensure_ascii=False,
        default=str,
    )
    temperature = get_temperature("RESPONSE_SYNTHESIS_TEMPERATURE")
    response = await create_chat_model(temperature=temperature).ainvoke(
        [
            ("system", RESPONSE_SYNTHESIS_PROMPT),
            ("human", context),
        ]
    )
    if not isinstance(response.content, str) or not response.content.strip():
        raise ModelResponseError("The language model returned an empty answer.")
    logger.info("LLM answer output:\n%s", response.content)
    return response.content.strip()
