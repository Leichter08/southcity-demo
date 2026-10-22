import logging
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.logging_config import DailyFileHandler
from app.text_to_sql import generate_sql, synthesize_response


class DailyFileHandlerTests(unittest.TestCase):
    def test_appends_to_existing_daily_file_and_uses_new_file_next_day(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_directory = Path(temporary_directory)
            existing_log = log_directory / "2026-10-22.log"
            existing_log.write_text("previous entry\n", encoding="utf-8")

            handler = DailyFileHandler(log_directory)
            handler.setFormatter(logging.Formatter("%(message)s"))
            try:
                with patch("app.logging_config.datetime") as mocked_datetime:
                    mocked_datetime.now.side_effect = [
                        datetime(2026, 10, 22, 10, 0),
                        datetime(2026, 10, 23, 10, 0),
                    ]
                    handler.handle(
                        logging.LogRecord(
                            "test", logging.INFO, __file__, 1, "same-day entry", (), None
                        )
                    )
                    handler.handle(
                        logging.LogRecord(
                            "test", logging.INFO, __file__, 2, "next-day entry", (), None
                        )
                    )
            finally:
                handler.close()

            self.assertEqual(
                existing_log.read_text(encoding="utf-8"),
                "previous entry\nsame-day entry\n",
            )
            self.assertEqual(
                (log_directory / "2026-10-23.log").read_text(encoding="utf-8"),
                "next-day entry\n",
            )


class LLMOutputLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_logs_sql_and_synthesized_llm_outputs(self) -> None:
        class FakeChatModel:
            def __init__(self) -> None:
                self.outputs = iter(
                    ("```sql\nSELECT 1\n```", "The answer is 1.")
                )

            async def ainvoke(self, messages: list[tuple[str, str]]) -> SimpleNamespace:
                return SimpleNamespace(content=next(self.outputs))

        with (
            patch.dict(
                os.environ,
                {
                    "SQL_GENERATION_TEMPERATURE": "0.0",
                    "RESPONSE_SYNTHESIS_TEMPERATURE": "0.0",
                },
            ),
            patch("app.text_to_sql.create_chat_model", return_value=FakeChatModel()),
            self.assertLogs("app.text_to_sql", level="INFO") as captured,
        ):
            sql = await generate_sql("test question", "Management")
            answer = await synthesize_response("test question", sql, {"rows": []})

        output = "\n".join(captured.output)
        self.assertIn("LLM SQL generation output:\n```sql\nSELECT 1\n```", output)
        self.assertIn("LLM answer output:\nThe answer is 1.", output)
        self.assertNotIn("test question", output)
        self.assertEqual(sql, "SELECT 1")
        self.assertEqual(answer, "The answer is 1.")


if __name__ == "__main__":
    unittest.main()
