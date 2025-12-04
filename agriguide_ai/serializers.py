# Updated serializers.py - SIMPLIFIED FARMER REGISTRATION
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, FarmerProfile, ExtensionWorkerProfile, CommunityPost, PostLike, PostComment
from .models import Tutorial, Notification
import os


class FarmerProfileSerializer(serializers.ModelSerializer):
    """SIMPLIFIED - No fields needed anymore"""
    class Meta:
        model = FarmerProfile
        fields = []  # Empty - just creates the relation


class ExtensionWorkerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionWorkerProfile
        fields = [
            'organization', 'employee_id', 'specialization',
            'regions_covered', 'verification_document', 'is_approved'
        ]
        read_only_fields = ['is_approved']


class UserSerializer(serializers.ModelSerializer):
    farmer_profile = FarmerProfileSerializer(required=False, read_only=True)
    extension_worker_profile = ExtensionWorkerProfileSerializer(
        required=False, 
        read_only=True
    )
    profile_picture_url = serializers.SerializerMethodField()
    is_approved = serializers.SerializerMethodField()  # NEW: For extension workers
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'user_type', 'profile_picture', 'profile_picture_url',
            'is_verified', 'created_at', 'farmer_profile',
            'extension_worker_profile', 'is_approved'  # NEW
        ]
        read_only_fields = [
            'id', 'created_at', 'is_verified', 
            'user_type', 'username'
        ]
    
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            return obj.profile_picture.url
        return None
    
    def get_is_approved(self, obj):
        """Check if extension worker is approved"""
        if obj.user_type == 'extension_worker':
            try:
                return obj.extension_worker_profile.is_approved
            except ExtensionWorkerProfile.DoesNotExist:
                return False
        return True  # Farmers are always "approved"

    def update(self, instance, validated_data):
        # Update user fields only
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FarmerRegistrationSerializer(serializers.ModelSerializer):
    """SIMPLIFIED - Only basic user fields"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone_number',
            'profile_picture'  # Optional
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data['phone_number'],
            user_type='farmer',
            profile_picture=validated_data.get('profile_picture')
        )
        
        # Create empty farmer profile (just for relation)
        farmer_profile = FarmerProfile.objects.create(user=user)
        
        return farmer_profile


class ExtensionWorkerRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    extension_worker_profile = ExtensionWorkerProfileSerializer(required=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone_number',
            'profile_picture', 'extension_worker_profile'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        extension_profile_data = validated_data.pop('extension_worker_profile')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data['phone_number'],
            user_type='extension_worker',
            profile_picture=validated_data.get('profile_picture')
        )
        
        extension_worker_profile = ExtensionWorkerProfile.objects.create(
            user=user,
            **extension_profile_data
        )
        
        return extension_worker_profile


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        username = attrs.get('username')
        email = attrs.get('email')
        phone_number = attrs.get('phone_number')
        password = attrs.get('password')

        user = None

        if username:
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
        elif email:
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(
                    request=self.context.get('request'),
                    username=user_obj.username,
                    password=password
                )
            except User.DoesNotExist:
                pass
        elif phone_number:
            try:
                user_obj = User.objects.get(phone_number=phone_number)
                user = authenticate(
                    request=self.context.get('request'),
                    username=user_obj.username,
                    password=password
                )
            except User.DoesNotExist:
                pass

        if not user:
            raise serializers.ValidationError(
                'Unable to log in with provided credentials.',
                code='authorization'
            )

        if not user.is_active:
            raise serializers.ValidationError(
                'User account is disabled.',
                code='authorization'
            )

        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True
    )
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "Password fields didn't match."
            })
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class CommunityPostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_profile_picture = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = CommunityPost
        fields = [
            'id', 'author_name', 'author_username', 'author_profile_picture',
            'content', 'image', 'tags', 'likes_count', 'comments_count',
            'is_liked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_author_name(self, obj):
        if obj.author.first_name and obj.author.last_name:
            return f"{obj.author.first_name} {obj.author.last_name}"
        return obj.author.username
    
    def get_author_profile_picture(self, obj):
        if obj.author.profile_picture:
            return obj.author.profile_picture.url
        return None
    
    def get_likes_count(self, obj):
        return obj.likes_count
    
    def get_comments_count(self, obj):
        return obj.comments_count
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return PostLike.objects.filter(
                user=request.user,
                post=obj
            ).exists()
        return False
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['author'] = request.user
        return super().create(validated_data)


class PostCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_profile_picture = serializers.SerializerMethodField()
    
    class Meta:
        model = PostComment
        fields = [
            'id', 'user_name', 'user_username', 'user_profile_picture',
            'content', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_user_name(self, obj):
        if obj.user.first_name and obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return obj.user.username
    
    def get_user_profile_picture(self, obj):
        if obj.user.profile_picture:
            return obj.user.profile_picture.url
        return None


class TutorialSerializer(serializers.ModelSerializer):
    uploader_name = serializers.SerializerMethodField()
    uploader_id = serializers.IntegerField(source='uploader.id', read_only=True)
    uploader_profile_picture = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Tutorial
        fields = [
            'id', 'title', 'description', 'category', 'video', 'thumbnail',
            'video_url', 'thumbnail_url', 'uploader_id', 'uploader_name',
            'uploader_profile_picture', 'view_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'view_count', 'created_at', 'updated_at']
    
    def get_uploader_name(self, obj):
        return obj.uploader_name
    
    def get_uploader_profile_picture(self, obj):
        if obj.uploader.profile_picture:
            return obj.uploader.profile_picture.url
        return None
    
    def get_video_url(self, obj):
        if obj.video:
            return obj.video.url
        return None
    
    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return obj.thumbnail.url
        return None
    
    def validate_category(self, value):
        valid_categories = [
            'crops', 'livestock', 'irrigation', 'pest_control',
            'soil_management', 'harvesting', 'post_harvest',
            'farm_equipment', 'marketing', 'other'
        ]
        
        if value.lower() not in valid_categories:
            raise serializers.ValidationError(
                f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        
        return value.lower()
    
    def validate_video(self, value):
        if value:
            if value.size > 100 * 1024 * 1024:
                raise serializers.ValidationError(
                    "Video file size must be under 100MB"
                )
            
            allowed_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
            file_extension = os.path.splitext(value.name)[1].lower()
            if file_extension not in allowed_extensions:
                raise serializers.ValidationError(
                    f"Video file must be one of: {', '.join(allowed_extensions)}"
                )
        
        return value
    
    def validate_thumbnail(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError(
                    "Thumbnail file size must be under 5MB"
                )
            
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            file_extension = os.path.splitext(value.name)[1].lower()
            if file_extension not in allowed_extensions:
                raise serializers.ValidationError(
                    f"Thumbnail must be one of: {', '.join(allowed_extensions)}"
                )
        
        return value
    
    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.method == 'POST':
            if request.user.user_type != 'extension_worker':
                raise serializers.ValidationError(
                    "Only extension workers can upload tutorials"
                )
        
        return attrs
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['uploader'] = request.user
        return super().create(validated_data)


class RequestVerificationSerializer(serializers.Serializer):
    """SIMPLIFIED Request verification - only basic user fields for farmers"""
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=['registration', 'login'],
        default='registration'
    )
    
    # Basic user fields
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    profile_picture = serializers.ImageField(required=False)
    user_type = serializers.ChoiceField(
        choices=['farmer', 'extension_worker'],
        required=False
    )
    
    # Extension worker fields (unchanged)
    organization = serializers.CharField(required=False)
    employee_id = serializers.CharField(required=False)
    specialization = serializers.CharField(required=False)
    regions_covered = serializers.ListField(child=serializers.CharField(), required=False)
    verification_document = serializers.FileField(required=False)


class VerifyCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=['registration', 'login']
    )
    
    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Code must be 6 digits")
        return value


class ResendCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=['registration', 'login']
    )


class NotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    sender_profile_picture = serializers.SerializerMethodField()
    post_id = serializers.IntegerField(source='post.id', read_only=True)
    post_content_preview = serializers.SerializerMethodField()
    comment_content = serializers.CharField(source='comment.content', read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'sender_name', 'sender_profile_picture',
            'post_id', 'post_content_preview', 'comment_content', 
            'is_read', 'created_at', 'time_ago', 'message'
        ]
        read_only_fields = ['id', 'created_at', 'message']
    
    def get_sender_profile_picture(self, obj):
        if hasattr(obj.sender, 'userprofile') and obj.sender.userprofile.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.sender.userprofile.profile_picture.url)
        return None
    
    def get_post_content_preview(self, obj):
        if obj.post:
            content = obj.post.content
            return content[:50] + '...' if len(content) > 50 else content
        return ""
    
    def get_time_ago(self, obj):
        from django.utils.timesince import timesince
        return timesince(obj.created_at) + " ago"