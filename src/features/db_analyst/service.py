"""Prepare the connection and define the toolt that the agent will use"""

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.tools import tool

from src.helper.shared import _get_llm, _get_db
from src.helper.config import get_settings
settings = get_settings()


def _get_sql_toolkit():
    llm = _get_llm()
    return SQLDatabaseToolkit(db=_get_db(), llm=llm)

def _get_db_context():
    return _get_db().get_table_info()