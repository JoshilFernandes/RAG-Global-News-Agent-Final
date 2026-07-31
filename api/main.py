from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from agent.llm_agent import agent_chat
import asyncio

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    user_query = data.get("query", "")
    if not user_query:
        return {"error": "Missing 'query' in request body."}
    response = await agent_chat(user_query)
    return {"response": response} 