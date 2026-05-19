import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from webhook_receiver.routes import router

load_dotenv()

app = FastAPI(title="Webhook Receiver")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "webhook_receiver.main:app",
        host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        port=int(os.getenv("WEBHOOK_PORT", "8001")),
        reload=False,
    )
