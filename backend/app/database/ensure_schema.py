"""Add columns that create_all cannot alter on an existing SQLite file."""

from __future__ import annotations

from sqlalchemy import JSON, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.type_api import TypeEngine

from app.database.base import Base


def _literal_default(value: object) -> str | None:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if value is dict or value == {}:
        return "'{}'"
    if value is list or value == []:
        return "'[]'"
    return None


def _column_default_sql(column) -> str | None:
    if column.server_default is not None:
        arg = getattr(column.server_default, "arg", None)
        if arg is not None:
            return str(arg)

    default = column.default
    if default is None:
        if isinstance(column.type, JSON) or (
            isinstance(column.type, TypeEngine) and column.type.__class__.__name__ == "JSON"
        ):
            # Non-null JSON columns without a scalar default still need a value for ALTER.
            if not column.nullable:
                return "'{}'"
        return None

    arg = default.arg
    if default.is_scalar:
        return _literal_default(arg)
    if arg is dict:
        return "'{}'"
    if arg is list:
        return "'[]'"
    if isinstance(column.type, JSON) and not column.nullable:
        return "'{}'"
    return None


def ensure_sqlite_columns(engine: Engine) -> None:
    """SQLite create_all skips existing tables; patch missing columns in place."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                sql = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"
                default_sql = _column_default_sql(column)
                if default_sql is not None:
                    sql = f"{sql} DEFAULT {default_sql}"
                elif not column.nullable:
                    # Non-null without a usable default — skip rather than break startup.
                    continue
                conn.execute(text(sql))
