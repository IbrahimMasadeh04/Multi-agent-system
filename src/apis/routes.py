from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.features.ingestion.service import process_and_save  # type: ignore
from src.features.agents.graph import graph  # type: ignore
import shutil
import os
from src.helper.config import get_settings  # type: ignore
settings = get_settings()


router = APIRouter()


def _message_text(message):
    if hasattr(message, "content"):
        return message.content
    return str(message)

class ChatRequest(BaseModel):
    message: str

class ApprovalRequest(BaseModel):
    approved: bool


#######################
#      UPLOAD EP      #
#######################

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


####################
#      CHAT EP     #
####################
@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        config = { "configurable": { "thread_id": "user_session_123" } }
        inputs = { "messages": [HumanMessage(content=request.message)] }
        
        # Execute the graph
        final_state = await graph.ainvoke(inputs, config=config)
        
        # After execution, check if there's a pending SQL that needs approval
        if final_state.get("pending_sql") and final_state.get("requires_confirmation"):
            return {
                "status": "interrupted",
                "pending_sql": final_state.get("pending_sql", ""),
                "message": f"Graph Interrupted. Awaiting Approval for Query:\n\n```sql\n{final_state.get('pending_sql', '')}\n```"
            }

        # Otherwise, return the response
        response = _message_text(final_state["messages"][-1])
        return { "status": "success", "response": response }
    except Exception as e:
        print(f"  Chat Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


###################
#   APPROVAL EP   #
###################
@router.post("/approve")
async def approve_query(request: ApprovalRequest):
    try:
        config = { "configurable": { "thread_id": "user_session_123" } }
        state = graph.get_state(config)
        
        if not state or not state.values:
            return {"status": "error", "message": "No pending confirmation found."}
        
        pending_sql = state.values.get("pending_sql", "")
        requires_conf = state.values.get("requires_confirmation", False)
        
        if not pending_sql or not requires_conf:
            return {"status": "error", "message": "No pending database operation awaiting approval."}
            
        print(f"\n" + "="*50)
        print(f"  Received User Approval: {request.approved}")
        print(f"  Pending SQL: {pending_sql}")
        print("="*50)
        
        # Update state with user approval
        graph.update_state(config, {"user_approval": request.approved})
        print(f"  State updated with user_approval={request.approved}")
        
        # Resume execution - pass None as input since we're resuming from checkpoint
        print(f"  Resuming graph execution...")
        final_state = await graph.ainvoke(None, config=config)
        
        print(f"  Graph execution completed")
        print(f"  Final state messages count: {len(final_state.get('messages', []))}")
        
        if not final_state.get("messages") or len(final_state["messages"]) == 0:
            return {"status": "error", "message": "No response from graph execution."}
        
        response = _message_text(final_state["messages"][-1])
        print(f"  Response: {response}")
        
        return {"status": "success", "response": response}
    except Exception as e:
        print(f"  Approve Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))