from fastapi import FastAPI
from app.database import init_db

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    await init_db()


@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI Telegram Bot"}
