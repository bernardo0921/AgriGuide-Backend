# agriguide_ai/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (CommunityPost, 
                     PostLike, 
                     PostComment, 
                     Tutorial, 
                     VerificationCode,
                     Notification)



@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'recipient',
        'sender', 
        'notification_type',
        'post_preview',
        'is_read',
        'created_at',
    ]
    
    list_filter = [
        'notification_type',
        'is_read',
        'created_at',
    ]
    
    search_fields = [
        'recipient__username',
        'recipient__email',
        'sender__username',
        'sender__email',
        'post__content',
    ]
    
    readonly_fields = [
        'created_at',
        'message',
        'get_comment_preview',
    ]
    
    list_per_page = 25
    
    date_hierarchy = 'created_at'
    
    # Organize fields in the detail view
    fieldsets = (
        ('Notification Info', {
            'fields': (
                'notification_type',
                'message',
                'is_read',
            )
        }),
        ('Users', {
            'fields': (
                'recipient',
                'sender',
            )
        }),
        ('Related Content', {
            'fields': (
                'post',
                'comment',
                'get_comment_preview',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
            )
        }),
    )
    
    # Custom methods for display
    def post_preview(self, obj):
        """Show a preview of the post content"""
        if obj.post:
            content = obj.post.content
            return content[:50] + '...' if len(content) > 50 else content
        return '-'
    post_preview.short_description = 'Post Preview'
    
    def get_comment_preview(self, obj):
        """Show comment content if it exists"""
        if obj.comment:
            content = obj.comment.content
            return content[:100] + '...' if len(content) > 100 else content
        return 'No comment'
    get_comment_preview.short_description = 'Comment Content'
    
    # Actions
    actions = ['mark_as_read', 'mark_as_unread', 'delete_selected']
    
    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read"""
        updated = queryset.update(is_read=True)
        self.message_user(
            request,
            f'{updated} notification(s) marked as read.'
        )
    mark_as_read.short_description = 'Mark selected as read'
    
    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread"""
        updated = queryset.update(is_read=False)
        self.message_user(
            request,
            f'{updated} notification(s) marked as unread.'
        )
    mark_as_unread.short_description = 'Mark selected as unread'
    
    # Optimize database queries
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            'recipient',
            'sender',
            'post',
            'comment'
        )
    
    # Custom list display styling
    def get_list_display_links(self, request, list_display):
        """Make id and recipient clickable"""
        return ('id', 'recipient')
@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    """Admin interface for tutorials"""
    list_display = [
        'id',
        'title',
        'uploader',
        'category',
        'view_count',
        'created_at',
        'has_thumbnail'
    ]
    list_filter = ['category', 'created_at', 'uploader']
    search_fields = [
        'title',
        'description',
        'uploader__username',
        'uploader__first_name',
        'uploader__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'view_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uploader', 'title', 'description', 'category')
        }),
        ('Media Files', {
            'fields': ('video', 'thumbnail')
        }),
        ('Statistics', {
            'fields': ('view_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_thumbnail(self, obj):
        """Check if tutorial has a thumbnail"""
        return bool(obj.thumbnail)
    has_thumbnail.boolean = True
    has_thumbnail.short_description = 'Thumbnail'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('uploader')

from .models import (
    User, 
    FarmerProfile, 
    ExtensionWorkerProfile, 
    ChatSession, 
    ChatMessage
)

admin.site.register(VerificationCode)


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    """Admin interface for community posts"""
    list_display = [
        'id',
        'author',
        'content_preview',
        'tags_display',
        'likes_count',
        'comments_count',
        'created_at'
    ]
    list_filter = ['created_at', 'author']
    search_fields = ['content', 'author__username', 'author__email']
    readonly_fields = ['created_at', 'updated_at', 'likes_count', 'comments_count']
    
    def content_preview(self, obj):
        """Show a preview of the content"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
    
    def tags_display(self, obj):
        """Display tags as a comma-separated string"""
        return ', '.join(obj.tags) if obj.tags else 'No tags'
    tags_display.short_description = 'Tags'


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    """Admin interface for post likes"""
    list_display = ['id', 'user', 'post', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'post__content']
    readonly_fields = ['created_at']


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    """Admin interface for post comments"""
    list_display = ['id', 'user', 'post', 'content_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'user__username', 'post__content']
    readonly_fields = ['created_at', 'updated_at']
    
    def content_preview(self, obj):
        """Show a preview of the comment content"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Comment'
# This custom admin class will improve how your User model looks
class CustomUserAdmin(UserAdmin):
    model = User
    
    # This adds your custom fields to the "Edit User" page
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Profile Info', {
            'fields': (
                'user_type', 
                'phone_number', 
                'profile_picture', 
                'is_verified'
            )
        }),
    )
    
    # This adds your custom fields to the "Create User" page
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Profile Info', {
            'fields': (
                'first_name', 
                'last_name', 
                'email', 
                'user_type', 
                'phone_number'
            )
        }),
    )
    
    # This adds your custom fields to the main user list
    list_display = [
        'username', 
        'email', 
        'user_type', 
        'first_name', 
        'last_name', 
        'is_staff'
    ]

# Register your models with the admin site
admin.site.register(User, CustomUserAdmin)
admin.site.register(FarmerProfile)
admin.site.register(ExtensionWorkerProfile)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)
