# from langchain.tools import tool
# from sqlalchemy import create_engine, text

# from src.helper.config import get_settings
# settings = get_settings()


# engine = create_engine(f"sqlite:///{settings.VENOM_DB_PATH}")


# @tool
# def execute_sql_query(query: str):
#     """
#     Executes a SQL query against the Venom Lounge database and returns results.
#     Use this for: items inventory, pricing, devices, and sales data.
#     Input should be a valid SQLite query.
#     """

#     try:
#         query_upper = query.strip().upper()
#         is_write = any(kw in query_upper for kw in ["UPDATE", "INSERT", "DELETE", "DROP", "ALTER"])
        
#         with engine.connect() as connection:
#             result = connection.execute(text(query))
            
#             # For write operations, commit and return row count
#             if is_write:
#                 connection.commit()
#                 rows_affected = result.rowcount
#                 return f"Query executed successfully. Rows affected: {rows_affected}"
            
#             # For read operations, fetch and return rows
#             rows = result.fetchall()
#             if not rows:
#                 return "No Results Found."
#             return str([dict(row._mapping) for row in rows])
    
#     except Exception as exc:
#         return f"SQL Execution Error: {exc}"
    