import uvicorn


def start_fastapi():
    uvicorn.run("app.main:app", host="0.0.0.0", port=8085, reload=True)
