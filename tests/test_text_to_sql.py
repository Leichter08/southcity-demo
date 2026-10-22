import unittest
from xml.etree import ElementTree
from unittest.mock import patch

from app.text_to_sql import (
    RoleAccessError,
    SQLValidationError,
    get_schema_for_role,
    validate_sql,
)


class ValidateSQLTests(unittest.TestCase):
    def test_accepts_single_select_query(self) -> None:
        validate_sql("SELECT name FROM Units WHERE status = 'DELETE'", "Management")

    def test_rejects_non_select_query(self) -> None:
        with self.assertRaises(SQLValidationError):
            validate_sql("DELETE FROM Units", "Management")

    def test_rejects_multiple_statements(self) -> None:
        with self.assertRaises(SQLValidationError):
            validate_sql("SELECT 1; SELECT 2", "Management")

    def test_rejects_sql_comments(self) -> None:
        with self.assertRaises(SQLValidationError):
            validate_sql("SELECT 1 -- comment", "Management")

    def test_rejects_select_into(self) -> None:
        with self.assertRaises(SQLValidationError):
            validate_sql("SELECT name INTO NewUnits FROM Units", "Management")

    def test_rejects_general_ledger_for_sales_staff(self) -> None:
        with self.assertRaises(RoleAccessError):
            validate_sql("SELECT * FROM gl_journals", "Sales_Staff")

    def test_allows_general_ledger_for_management(self) -> None:
        validate_sql("SELECT * FROM GL_Journals", "Management")


class GetSchemaForRoleTests(unittest.TestCase):
    def test_removes_general_ledger_table_for_sales_staff(self) -> None:
        schema = ElementTree.fromstring(get_schema_for_role("Sales_Staff"))
        tables = [table.get("name") for table in schema.iter("table")]

        self.assertNotIn("GL_Journals", tables)

    def test_keeps_general_ledger_table_for_management(self) -> None:
        schema = ElementTree.fromstring(get_schema_for_role("Management"))
        tables = [table.get("name") for table in schema.iter("table")]

        self.assertIn("GL_Journals", tables)
