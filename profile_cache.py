from config import get_logger
from typing import Dict, Any, Optional
import time
from fastapi import HTTPException

logger = get_logger(__name__)
# Profile cache to avoid repeated Firebase queries
class ProfileCache:
	def __init__(self, ttl_minutes: float = 30):
		self.cache: Dict[str, Dict[str, Any]] = {}
		self.cache_times: Dict[str, float] = {}
		self.ttl_seconds = ttl_minutes * 60
	
	def get(self, user_id: str) -> Optional[Dict[str, Any]]:
			if user_id not in self.cache:
					return None
					
			# Check if cache entry has expired
			if time.time() - self.cache_times[user_id] > self.ttl_seconds:
					self.invalidate(user_id)
					return None
					
			return self.cache[user_id]
	
	def set(self, user_id: str, profile: Dict[str, Any]) -> None:
		self.cache[user_id] = profile
		self.cache_times[user_id] = time.time()
		logger.debug(f"Profile cached for user: {user_id}")
	
	def invalidate(self, user_id: str) -> None:
		self.cache.pop(user_id, None)
		self.cache_times.pop(user_id, None)
		logger.debug(f"Profile cache invalidated for user: {user_id}")
	
	def clear(self) -> None:
		self.cache.clear()
		self.cache_times.clear()
		logger.debug("Profile cache cleared")

# Initialize profile cache (30 minute TTL)
cache = ProfileCache(ttl_minutes=30)

def get_user_profile_cached(user_id: str, db) -> Dict[str, Any]:
    """Get user profile with caching to avoid repeated Firebase queries."""
    # Try to get from cache first
    cached_profile = cache.get(user_id)
    if cached_profile is not None:
        logger.debug(f"Profile retrieved from cache for user: {user_id}")
        return cached_profile
    
    # Cache miss - fetch from Firebase
    logger.debug(f"Profile cache miss, fetching from Firebase for user: {user_id}")
    assert db is not None, "Database client is None"
    profile_ref = db.collection('user_profiles').document(user_id)
    profile_doc = profile_ref.get()
    
    if not profile_doc.exists:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    profile = profile_doc.to_dict()
    
    # Cache the profile
    cache.set(user_id, profile)
    
    return profile