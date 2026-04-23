from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from src.helper.config import get_settings
settings = get_settings()

db = SQLDatabase.from_uri(f"sqlite:///{settings.VENOM_DB_PATH}")

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
