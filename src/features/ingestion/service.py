from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma.vectorstores import Chroma

from src.helper.config import get_settings  # type: ignore
from src.helper.shared import _get_embeddings  # type: ignore

async def process_and_save(file_path: str):
    settings = get_settings()
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=_get_embeddings(),
        persist_directory=settings.CHROMA_DB_PATH,
    )

    return "File processed successfully"


async def search_internal_docs_with_score(query: str):
    settings = get_settings()
    vectorstore = Chroma(
        persist_directory=settings.CHROMA_DB_PATH,
        embedding_function=_get_embeddings(),
    )

    results = await vectorstore.asimilarity_search_with_relevance_scores(query, k=2)
    # results is a list of tuples: (Document, score)
    if not results:
        return "", 0.0
    
    # taking the best score from the top result
    best_score = results[0][1]
    combined_text = "\n".join([str(doc.page_content) for doc, score in results])
    return combined_text, best_score

async def search_internal_docs(query: str):
    text, _ = await search_internal_docs_with_score(query)
    return text