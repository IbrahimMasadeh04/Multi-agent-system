from langchain.tools import tool
from sqlalchemy import create_engine, text

from src.helper.config import get_settings
settings = get_settings()


engine = create_engine(f"sqlite:///{settings.VENOM_DB_PATH}")


@tool
def execute_sql_query(query: str):
    """
    Executes a SQL query against the Venom Lounge database and returns results.
    Use this for: items inventory, pricing, devices, and sales data.
    Input should be a valid SQLite query.
    """

    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))
            rows = result.fetchall()

            if not rows:
                return "No Results Found."
            return str([dict(row._mapping) for row in rows])
    
    except Exception as exc:
        return f"SQL Execution Error: {exc}"
    