from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from src.helper.config import get_settings  # type: ignore
settings = get_settings()

_db_instance = None

def _get_db():
    """Lazily initialize and return the SQLDatabase instance."""
    global _db_instance
    if _db_instance is None:
        try:
            _db_instance = SQLDatabase.from_uri(f"sqlite:///{settings.VENOM_DB_PATH}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to connect to database at {settings.VENOM_DB_PATH}. "
                f"Please ensure the path exists and is accessible. Error: {e}"
            )
    return _db_instance

def _message_text(message):
    if hasattr(message, "content"):
        return message.content
    if isinstance(message, (tuple, list)) and len(message) > 1:
        return str(message[1])
    return str(message)


def _get_llm(TEMPERATURE: float =settings.OPENAI_LLM_TEMPERATURE) -> ChatOpenAI:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required.")

    return ChatOpenAI(
        model=settings.OPENAI_LLM,
        temperature=TEMPERATURE,
        api_key=settings.OPENAI_API_KEY,
    )


def _get_embeddings() -> OpenAIEmbeddings:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required to process or search documents.")

    return OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
