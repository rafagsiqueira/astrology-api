"""Business logic for user profile functionality, extracted for better testability."""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException

from models import UserProfile, ProfileCreationRequest, PartnerData, AddPartnerRequest
from astrology import get_timezone_from_coordinates
from config import get_logger

logger = get_logger(__name__)


def validate_database_availability(db) -> None:
    """Validate that database is available.
    
    Args:
        db: Firestore database client
        
    Raises:
        HTTPException: If database is not available
    """
    if not db:
        raise HTTPException(
            status_code=500, 
            detail="Database not available"
        )


def create_user_profile_data(
    user_id: str, 
    email: Optional[str], 
    profile_request: ProfileCreationRequest
) -> UserProfile:
    """Create user profile data from request and user info.
    
    Args:
        user_id: Firebase user ID
        email: User email (optional)
        profile_request: Profile creation request data
        
    Returns:
        UserProfile object ready to be saved to database
        
    Raises:
        Exception: If timezone lookup fails
    """
    # Get timezone from coordinates
    timezone_str = get_timezone_from_coordinates(
        profile_request.latitude, 
        profile_request.longitude
    )
    
    # Create profile data
    profile = UserProfile(
        uid=user_id,
        email=email,
        birth_date=profile_request.birth_date,
        birth_time=profile_request.birth_time,
        birth_location=f"Lat: {profile_request.latitude}, Lon: {profile_request.longitude}",
        latitude=profile_request.latitude,
        longitude=profile_request.longitude,
        timezone=timezone_str,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    return profile


def save_profile_to_database(db, user_id: str, profile: UserProfile) -> None:
    """Save user profile to Firestore database.
    
    Args:
        db: Firestore database client
        user_id: Firebase user ID
        profile: UserProfile object to save
        
    Raises:
        Exception: If database save operation fails
    """
    doc_ref = db.collection('user_profiles').document(user_id)
    doc_ref.set(profile.model_dump())
    logger.debug(f"Profile saved to database for user: {user_id}")


def get_profile_from_database(db, user_id: str) -> UserProfile:
    """Get user profile from Firestore database.
    
    Args:
        db: Firestore database client
        user_id: Firebase user ID
        
    Returns:
        UserProfile object from database
        
    Raises:
        HTTPException: If profile not found or database operation fails
    """
    doc_ref = db.collection('user_profiles').document(user_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(
            status_code=404, 
            detail="Profile not found"
        )
    
    profile_data = doc.to_dict()
    profile = UserProfile(**profile_data)
    
    logger.debug(f"Profile retrieved from database for user: {user_id}")
    return profile


def validate_profile_creation_request(profile_request: ProfileCreationRequest) -> None:
    """Validate profile creation request data.
    
    Args:
        profile_request: Profile creation request to validate
        
    Raises:
        HTTPException: If request data is invalid
    """
    # Basic validation - Pydantic handles most field validation
    # Add any additional business logic validation here
    
    # Example: Validate coordinates are within valid ranges
    if not (-90 <= profile_request.latitude <= 90):
        raise HTTPException(
            status_code=400,
            detail="Latitude must be between -90 and 90 degrees"
        )
    
    if not (-180 <= profile_request.longitude <= 180):
        raise HTTPException(
            status_code=400,
            detail="Longitude must be between -180 and 180 degrees"
        )
    
    # Validate birth time format (basic check)
    try:
        time_parts = profile_request.birth_time.split(':')
        if len(time_parts) != 2:
            raise ValueError("Invalid time format")
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        if not (0 <= hour <= 23):
            raise ValueError("Invalid hour")
        if not (0 <= minute <= 59):
            raise ValueError("Invalid minute")
            
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="Birth time must be in HH:MM format (24-hour)"
        )


def format_profile_response(profile: UserProfile) -> Dict[str, Any]:
    """Format profile for API response.
    
    Args:
        profile: UserProfile object
        
    Returns:
        Dictionary formatted for API response
    """
    # Convert to dict and handle any special formatting
    profile_dict = profile.model_dump()
    
    # Convert datetime objects to strings for JSON serialization
    if profile_dict.get('created_at'):
        profile_dict['created_at'] = profile_dict['created_at'].isoformat()
    if profile_dict.get('updated_at'):
        profile_dict['updated_at'] = profile_dict['updated_at'].isoformat()
    if profile_dict.get('birth_date'):
        profile_dict['birth_date'] = profile_dict['birth_date'].isoformat()
    
    return profile_dict


def create_partner_data(
    partner_request: AddPartnerRequest,
    user_id: str
) -> PartnerData:
    """Create partner data from request.
    
    Args:
        partner_request: Partner creation request data
        user_id: User ID who is creating this partner
        
    Returns:
        PartnerData object ready to be added to user profile
        
    Raises:
        Exception: If timezone lookup fails
    """
    import uuid
    
    # Generate unique UID for partner
    partner_uid = str(uuid.uuid4())
    
    # Get timezone from coordinates
    timezone_str = get_timezone_from_coordinates(
        partner_request.latitude, 
        partner_request.longitude
    )
    
    # Create birth location string
    birth_location = f"Lat: {partner_request.latitude}, Lon: {partner_request.longitude}"
    
    # Create partner data
    partner_data = PartnerData(
        uid=partner_uid,
        name=partner_request.name,
        birth_date=partner_request.birth_date,
        birth_time=partner_request.birth_time,
        birth_location=birth_location,
        latitude=partner_request.latitude,
        longitude=partner_request.longitude,
        timezone=timezone_str,
        created_at=datetime.now()
    )
    
    return partner_data


def add_partner_to_profile(db, user_id: str, partner_data: PartnerData) -> None:
    """Add partner to user's profile in Firestore database.
    
    Args:
        db: Firestore database client
        user_id: Firebase user ID
        partner_data: PartnerData object to add
        
    Raises:
        HTTPException: If profile not found
        Exception: If database operation fails
    """
    doc_ref = db.collection('user_profiles').document(user_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(
            status_code=404,
            detail="User profile not found"
        )
    
    profile_dict = doc.to_dict()
    
    # Initialize partners array if it doesn't exist
    if 'partners' not in profile_dict or profile_dict['partners'] is None:
        profile_dict['partners'] = []
    
    # Add new partner to the array
    profile_dict['partners'].append(partner_data.model_dump())
    
    # Update the profile with new partner and timestamp
    profile_dict['updated_at'] = datetime.now()
    
    # Save back to database
    doc_ref.update(profile_dict)
    
    logger.debug(f"Partner '{partner_data.name}' added to profile for user: {user_id}")