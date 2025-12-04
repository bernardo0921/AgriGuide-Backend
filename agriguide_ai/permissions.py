# agriguide_ai/permissions.py - CUSTOM PERMISSION FOR APPROVED EXTENSION WORKERS

from rest_framework import permissions
from .models import ExtensionWorkerProfile
import logging

logger = logging.getLogger(__name__)


class IsApprovedOrFarmer(permissions.BasePermission):
    """
    Custom permission:
    - Farmers: Always allowed
    - Extension Workers: Only if approved (is_approved=True)
    - Others: Denied
    """
    
    message = "Your account is pending approval. Please wait for admin approval."
    
    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        user = request.user
        
        # Farmers always have permission
        if user.user_type == 'farmer':
            logger.debug(f"✅ Farmer {user.username} has permission")
            return True
        
        # Extension workers must be approved
        if user.user_type == 'extension_worker':
            try:
                worker_profile = user.extension_worker_profile
                if worker_profile.is_approved:
                    logger.debug(f"✅ Approved extension worker {user.username} has permission")
                    return True
                else:
                    logger.warning(f"🚫 Unapproved extension worker {user.username} denied access")
                    return False
            except ExtensionWorkerProfile.DoesNotExist:
                logger.error(f"❌ Extension worker profile not found for {user.username}")
                return False
        
        # Unknown user type
        logger.warning(f"⚠️ Unknown user type for {user.username}: {user.user_type}")
        return False


class IsApprovedExtensionWorker(permissions.BasePermission):
    """
    Permission for extension worker-only endpoints (like tutorial upload)
    Requires:
    - User must be extension_worker
    - Must be approved (is_approved=True)
    """
    
    message = "Only approved extension workers can perform this action."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        user = request.user
        
        if user.user_type != 'extension_worker':
            logger.debug(f"🚫 User {user.username} is not an extension worker")
            return False
        
        try:
            worker_profile = user.extension_worker_profile
            if worker_profile.is_approved:
                logger.debug(f"✅ Approved extension worker {user.username} has permission")
                return True
            else:
                logger.warning(f"🚫 Unapproved extension worker {user.username} denied access")
                return False
        except ExtensionWorkerProfile.DoesNotExist:
            logger.error(f"❌ Extension worker profile not found for {user.username}")
            return False