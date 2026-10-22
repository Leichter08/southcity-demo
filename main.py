from fastapi import FastAPI

from app.logging_config import configure_logging
from app.routes import router

configure_logging()

app = FastAPI(title="Groq Prompt API")
app.include_router(router)
