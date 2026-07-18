import logging

from fastapi import FastAPI

from app.websocket.chat_socket import (
    router as chat_router,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s %(levelname)s "
        "%(name)s: %(message)s"
    ),
)


app = FastAPI(
    title="PowerNET AI Chatbot",
    version="1.0.0",
)

app.include_router(chat_router)


@app.get("/")
def root():
    return {
        "message": "PowerNET AI Chatbot running",
        "websocket": "/ws/chat",
        "handoff": "email",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }