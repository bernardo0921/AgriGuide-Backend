from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.core.files.storage import default_storage
from django.utils import timezone
from datetime import timedelta
import random
from .storage_backends import ChatImageStorage 
from .storage_backends import (
    ProfilePictureStorage,
    TutorialVideoStorage,
    TutorialThumbnailStorage,
    CommunityPostImageStorage,
    VerificationDocumentStorage
)


class User(AbstractUser):
    """Extended User model for AgriGuide AI"""
    USER_TYPE_CHOICES = (
        ('farmer', 'Farmer'),
        ('extension_worker', 'Extension Worker'),
    )
    
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='farmer'
    )
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in format: '+233123456789'"
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        unique=True
    )
    profile_picture = models.ImageField(
        storage=ProfilePictureStorage(),
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False)
    
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='agriguide_user_set',
        related_query_name='agriguide_user',
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='agriguide_user_set',
        related_query_name='agriguide_user',
    )
    
    def save(self, *args, **kwargs):
        """Override save to handle S3 storage errors"""
        try:
            super().save(*args, **kwargs)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving user {self.username}: {str(e)}")
            raise
    
    class Meta:
        db_table = 'users'
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class FarmerProfile(models.Model):
    """SIMPLIFIED Profile for farmers - ONLY BASIC INFO"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='farmer_profile'
    )
    # ALL FARM FIELDS REMOVED - Farmers only need basic User info now
    # If you need to store any farmer-specific data in future, add it here
    
    class Meta:
        db_table = 'farmer_profiles'
    
    def __str__(self):
        return f"{self.user.username}'s Farmer Profile"


class ExtensionWorkerProfile(models.Model):
    """Profile for extension workers"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='extension_worker_profile'
    )
    organization = models.CharField(max_length=255)
    employee_id = models.CharField(max_length=50, unique=True)
    specialization = models.CharField(
        max_length=100,
        help_text="e.g., Crop Science, Animal Husbandry"
    )
    regions_covered = models.TextField(
        help_text="Comma-separated list of regions"
    )
    verification_document = models.FileField(
        storage=VerificationDocumentStorage(),
        blank=True,
        null=True
    )
    is_approved = models.BooleanField(default=False)  # KEY FIELD FOR BLOCKING
    approved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'extension_worker_profiles'
    
    def __str__(self):
        return f"{self.user.username} - {self.organization}"


class ChatSession(models.Model):
    """Store chat sessions for users"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_sessions'
    )
    session_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.user.username}"

class CommunityPost(models.Model):
    """Community post model for farmers to share information"""
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='community_posts'
    )
    content = models.TextField(
        help_text="Post content"
    )
    image = models.ImageField(
        storage=CommunityPostImageStorage(),
        blank=True,
        null=True,
        help_text="Optional image for the post"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tags for the post"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'community_posts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.author.username}: {self.content[:50]}..."
    
    @property
    def likes_count(self):
        return self.likes.count()
    
    @property
    def comments_count(self):
        return self.comments.count()


class PostLike(models.Model):
    """Model to track post likes"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='post_likes'
    )
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'post_likes'
        unique_together = ['user', 'post']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} likes post {self.post.id}"


class PostComment(models.Model):
    """Model to track post comments"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='post_comments'
    )
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'post_comments'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.username} on post {self.post.id}: {self.content[:30]}..."


class Tutorial(models.Model):
    """Tutorial model for extension farmers to post educational videos"""
    
    CATEGORY_CHOICES = (
        ('crops', 'Crops'),
        ('livestock', 'Livestock'),
        ('irrigation', 'Irrigation'),
        ('pest_control', 'Pest Control'),
        ('soil_management', 'Soil Management'),
        ('harvesting', 'Harvesting'),
        ('post_harvest', 'Post-Harvest'),
        ('farm_equipment', 'Farm Equipment'),
        ('marketing', 'Marketing'),
        ('other', 'Other'),
    )
    
    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tutorials',
        help_text="User who uploaded the tutorial"
    )
    title = models.CharField(
        max_length=200,
        help_text="Tutorial title"
    )
    description = models.TextField(
        help_text="Detailed description of the tutorial"
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other',
        help_text="Tutorial category"
    )
    video = models.FileField(
        storage=TutorialVideoStorage(),
        help_text="Tutorial video file"
    )
    thumbnail = models.ImageField(
        storage=TutorialThumbnailStorage(),
        blank=True,
        null=True,
        help_text="Optional thumbnail image for the video"
    )
    view_count = models.IntegerField(
        default=0,
        help_text="Number of views"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tutorials'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['category']),
            models.Index(fields=['uploader']),
        ]
    
    def __str__(self):
        return f"{self.title} by {self.uploader.username}"
    
    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    @property
    def uploader_name(self):
        if self.uploader.first_name and self.uploader.last_name:
            return f"{self.uploader.first_name} {self.uploader.last_name}"
        return self.uploader.username


class ChatMessage(models.Model):
    """Store individual chat messages with optional images"""
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(
        max_length=10,
        choices=(('user', 'User'), ('model', 'Model'))
    )
    message = models.TextField()
    image = models.ImageField(
        storage=ChatImageStorage(),
        blank=True,
        null=True,
        help_text="Optional image attachment"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.message[:50]}..."
    
    @property
    def image_url(self):
        if self.image:
            return self.image.url
        return None


class VerificationCode(models.Model):
    """Store temporary 2FA verification codes"""
    
    PURPOSE_CHOICES = [
        ('registration', 'Registration'),
        ('login', 'Login'),
        ('password_reset', 'Password Reset'),
    ]
    
    email = models.EmailField()
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    
    registration_data = models.JSONField(null=True, blank=True)
    
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    
    last_sent_at = models.DateTimeField(auto_now_add=True)
    send_count = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'purpose', 'verified_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.email} - {self.purpose} - {self.code}"
    
    @classmethod
    def generate_code(cls):
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    @classmethod
    def create_verification(cls, email, purpose, registration_data=None, expiry_minutes=5):
        fifteen_min_ago = timezone.now() - timedelta(minutes=15)
        recent_codes = cls.objects.filter(
            email=email,
            purpose=purpose,
            created_at__gte=fifteen_min_ago
        ).count()
        
        if recent_codes >= 3:
            raise ValueError("Too many verification attempts. Please try again in 15 minutes.")
        
        cls.objects.filter(
            email=email,
            purpose=purpose,
            verified_at__isnull=True
        ).delete()
        
        code = cls.generate_code()
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        
        verification = cls.objects.create(
            email=email,
            code=code,
            purpose=purpose,
            registration_data=registration_data,
            expires_at=expires_at
        )
        
        return verification, True
    
    def is_valid(self):
        if self.verified_at:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.attempts >= self.max_attempts:
            return False
        return True
    
    def verify(self, submitted_code):
        self.attempts += 1
        self.save()
        
        if not self.is_valid():
            if self.verified_at:
                return False, "Code already used"
            elif timezone.now() > self.expires_at:
                return False, "Code expired"
            elif self.attempts > self.max_attempts:
                return False, "Too many incorrect attempts"
        
        if self.code == submitted_code:
            self.verified_at = timezone.now()
            self.save()
            return True, "Verification successful"
        
        remaining = self.max_attempts - self.attempts
        return False, f"Invalid code. {remaining} attempts remaining"
    
    @classmethod
    def cleanup_expired(cls):
        expired = cls.objects.filter(expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        return count


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('like', 'Like'),
        ('comment', 'Comment'),
    )
    
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='sent_notifications'
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(
        'CommunityPost', 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    comment = models.ForeignKey(
        'PostComment', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.sender.username} {self.notification_type} on {self.post.id}"
    
    @property
    def message(self):
        if self.notification_type == 'like':
            return f"{self.sender.username} liked your post"
        elif self.notification_type == 'comment':
            return f"{self.sender.username} commented on your post"
        return "New notification"