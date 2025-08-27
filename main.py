"""Main application file for Avra backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config import (
    APP_TITLE, APP_VERSION, CORS_ORIGINS, CORS_CREDENTIALS, 
    CORS_METHODS, CORS_HEADERS, get_logger
)
from auth import initialize_firebase
from routes import router

# Initialize logging
logger = get_logger(__name__)

# Initialize Firebase
initialize_firebase()

# Create FastAPI app
app = FastAPI(title=APP_TITLE, version=APP_VERSION)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)

app.add_middleware(GZipMiddleware, minimum_size=500)

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)