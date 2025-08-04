"""Main application file for Cosmic Guru backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Include routes
app.include_router(router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cosmic-guru-backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)