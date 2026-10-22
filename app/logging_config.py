import logging
from datetime import datetime
from pathlib import Path
from typing import TextIO


class DailyFileHandler(logging.Handler):
    def __init__(self, log_directory: Path) -> None:
        super().__init__()
        self.log_directory = log_directory
        self._stream: TextIO | None = None
        self._current_date: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            current_date = datetime.now().date().isoformat()
            if current_date != self._current_date:
                if self._stream is not None:
                    self._stream.close()
                self.log_directory.mkdir(parents=True, exist_ok=True)
                self._stream = (self.log_directory / f"{current_date}.log").open(
                    "a", encoding="utf-8"
                )
                self._current_date = current_date

            if self._stream is None:
                raise RuntimeError("Daily log file could not be opened")
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self.acquire()
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            super().close()
        finally:
            self.release()


def configure_logging(log_directory: Path | None = None) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(isinstance(handler, DailyFileHandler) for handler in root_logger.handlers):
        file_handler = DailyFileHandler(
            log_directory or Path(__file__).resolve().parent.parent / "logs"
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)

    if not any(
        isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers
    ):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(console_handler)
