from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from routes.upload import router as upload_router
from routes.chat import router as chat_router   # ⭐ ADD THIS
from routes.review import router as review_router


app = FastAPI()

app.include_router(upload_router, prefix="/api")
app.include_router(chat_router, prefix="/api")  # ⭐ ADD THIS
app.include_router(review_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "Smart Repository Running"}