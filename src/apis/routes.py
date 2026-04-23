from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.features.ingestion.service import process_and_save
from src.features.agents.graph import create_graph
import shutil
import os
from src.helper.config import get_settings
settings = get_settings()


router = APIRouter()
graph = create_graph()


def _message_text(message):
    if hasattr(message, "content"):
        return message.content
    return str(message)

class ChatRequest(BaseModel):
    message: str

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        if not os.path.exists(settings.UPLOAD_DIR):
            os.makedirs(settings.UPLOAD_DIR)
            
        file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        result = await process_and_save(file_path)
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        inputs = { "messages": [HumanMessage(content=request.message)] }
        final_state = await graph.ainvoke(inputs)

        response = _message_text(final_state["messages"][-1])
        return { "response": response }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))