from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    LANGSMITH_PROJECT: str
    LANGSMITH_API_KEY: str
    OPENAI_API_KEY: str
    OPENAI_LLM: str
    OPENAI_LLM_TEMPERATURE: float
    OPENAI_EMBEDDING_MODEL: str
    GOOGLE_API_KEY: str
    TAVILY_API_KEY: str
    CHROMA_DB_PATH: str
    UPLOAD_DIR: str
    LANGCHAIN_TRACING_V2: str
    PROJECT_NAME: str
    VENOM_DB_PATH: str


    class Config:
        env_file = ".env"


def get_settings(): 
    return Settings()