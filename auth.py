"""Authentication module for Firebase integration."""

import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
from fastapi import HTTPException, Header, Depends
from functools import wraps
from config import get_logger, FIRESTORE_DATABASE_ID
from firebase_admin import credentials

logger = get_logger(__name__)

# Firebase app and database globals
firebase_app = None
db = None

def initialize_firebase():
    """Initialize Firebase Admin SDK and Firestore."""
    global firebase_app, db
    
    try:
        # Check if Firebase Admin is already initialized
        if not firebase_admin._apps:
            # For development, use Application Default Credentials
            # In production, you should use a service account key file
            cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")) if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ else None
            firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully")
        else:
            firebase_app = firebase_admin.get_app()
            logger.info("Firebase Admin SDK already initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        logger.warning("Authentication features will be disabled")

    # Initialize Firestore
    try:
        if firebase_app:
            # Initialize Firestore client (using default database for now)
            # TODO: Multi-database support requires Firebase Admin SDK 7.0+
            if FIRESTORE_DATABASE_ID:
                logger.info(f"Using Firestore database ID: {FIRESTORE_DATABASE_ID}")
                db = firestore.client(database_id=FIRESTORE_DATABASE_ID)
            else:
                logger.warning("FIRESTORE_DATABASE_ID not set, using default database")
                db = firestore.client()
        else:
            logger.warning("Firestore disabled - Firebase Admin SDK not initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Firestore: {e}")
        logger.warning("User profiles and database features will be disabled")

async def verify_firebase_token(authorization: str = Header(None)):
    """Verify Firebase ID token and return user info"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = authorization.split(" ")[1]
    
    try:
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token.get('uid')
        email = decoded_token.get('email')
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token - no user ID")
        
        logger.debug(f"Token verified for user: {user_id}")
        return {
            "uid": user_id,
            "email": email,
            "decoded_token": decoded_token
        }
    
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def require_auth(func):
    """Decorator to require Firebase authentication"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract user from kwargs (assuming it's passed by verify_firebase_token)
        user = kwargs.get('user')
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        return await func(*args, **kwargs)
    return wrapper

async def require_authenticated_user(user_info: dict = Depends(verify_firebase_token)):
    """Dependency that requires any authenticated user (including anonymous)"""
    return user_info

async def require_non_anonymous_user(user_info: dict = Depends(verify_firebase_token)):
    """Dependency that requires a non-anonymous authenticated user."""
    decoded_token = user_info.get('decoded_token')

    if not isinstance(decoded_token, dict):
        raise HTTPException(
            status_code=403,
            detail="User authentication data unavailable"
        )

    firebase_info = decoded_token.get('firebase')
    if not isinstance(firebase_info, dict):
        raise HTTPException(
            status_code=403,
            detail="User authentication data unavailable"
        )

    firebase_sign_in_provider = firebase_info.get('sign_in_provider')
    is_anonymous = firebase_sign_in_provider == 'anonymous'
    
    if is_anonymous:
        raise HTTPException(
            status_code=403, 
            detail="Anonymous users are not allowed for this operation"
        )
    
    return user_info

def get_firestore_client():
    """Get the Firestore client instance."""
    return db

def get_firebase_app():
    """Get the Firebase app instance."""
    return firebase_app

def validate_database_availability() -> None:
    """Validate that database is available.
        
    Raises:
        HTTPException: If database is not available
    """
    client = get_firestore_client()
    if not client:
        raise HTTPException(
            status_code=503, 
            detail="Firestore service unavailable"
        )
