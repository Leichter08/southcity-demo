import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()


class DatabaseConfigurationError(RuntimeError):
    pass


def get_connection() -> pyodbc.Connection:
    driver = os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("SQL_SERVER_NAME")
    database = os.getenv("SQL_SERVER_DATABASE")

    missing_settings = [
        name
        for name, value in (
            ("SQL_SERVER_NAME", server),
            ("SQL_SERVER_DATABASE", database),
        )
        if not value
    ]
    if missing_settings:
        raise DatabaseConfigurationError(
            f"Missing SQL Server settings: {', '.join(missing_settings)}"
        )

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(connection_string, timeout=5)
