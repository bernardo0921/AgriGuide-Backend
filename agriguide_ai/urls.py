# agriguide_ai/urls.py - UPDATED WITH 2FA
from django.urls import path
from . import views
from . import auth_views
from . import community_views, lms_views, ai_tip_views, twofa_views
from . import deep_link_views

urlpatterns = [
    # ==================== 2FA AUTHENTICATION (PRIMARY) ====================
    path('api/auth/request-verification/', 
         twofa_views.request_verification_code, 
         name='request-verification'),
    path('api/auth/verify-and-register/', 
         twofa_views.verify_code_and_register, 
         name='verify-and-register'),
    path('api/auth/verify-and-login/', 
         twofa_views.verify_code_and_login, 
         name='verify-and-login'),
    path('api/auth/complete-extension-worker-registration/',
         twofa_views.complete_extension_worker_registration,
         name='complete-extension-worker-registration'),
    path('api/auth/resend-code/', 
         twofa_views.resend_verification_code, 
         name='resend-code'),

    # ==================== OLD AUTHENTICATION (Kept for backward compatibility) ====================
    path('api/auth/login/', 
         auth_views.login_view, 
         name='login'),
    
    # ==================== PROFILE & TOKEN ====================
    path('api/auth/logout/', 
         auth_views.logout_view, 
         name='logout'),
    path('api/auth/profile/', 
         auth_views.profile_view, 
         name='profile'),
    path('api/auth/profile/update/', 
         auth_views.update_profile_view, 
         name='update_profile'),
    path('api/auth/change-password/', 
         auth_views.change_password_view, 
         name='change_password'),
    path('api/auth/verify-token/', 
         auth_views.verify_token, 
         name='verify_token'),

    # DEBUG: Check user type endpoint
    path('api/auth/check-user-type/', 
         lms_views.check_user_type, 
         name='check_user_type'),

    # ==================== CHAT ENDPOINTS ====================
    path('api/chat/', 
         views.chat_with_ai, 
         name='chat_with_ai'),
    path('api/chat-stream/', 
         views.chat_with_ai_stream, 
         name='chat_with_ai_stream'),
    path('api/chat/sessions/', 
         views.get_chat_sessions, 
         name='get_chat_sessions'),
    path('api/chat/history/<str:session_id>/', 
         views.get_chat_history, 
         name='get_chat_history'),
    path('api/chat/clear/', 
         views.clear_chat_session, 
         name='clear_chat'),
    path('api/chat/delete/<str:session_id>/', 
         views.delete_chat_session, 
         name='delete_chat_session'),
    path('api/test/', 
         views.test_connection, 
         name='test_connection'),

    # ==================== AI TIP ====================
    path('api/farming-tip/', 
         ai_tip_views.get_daily_farming_tip, 
         name='get_daily_farming_tip'),
         
    # ==================== COMMUNITY ====================
    path('api/community/posts/', 
         community_views.CommunityPostListCreateView.as_view(), 
         name='community_posts'),
    path('api/community/posts/<int:pk>/', 
         community_views.CommunityPostDetailView.as_view(), 
         name='community_post_detail'),
    path('api/community/posts/<int:pk>/like/', 
         community_views.toggle_post_like, 
         name='toggle_post_like'),
    path('api/community/posts/<int:pk>/comments/', 
         community_views.post_comments, 
         name='post_comments'),
    path('api/community/posts/<int:pk>/comments/<int:comment_id>/', 
         community_views.delete_comment, 
         name='delete_comment'),
    path('api/community/my-posts/', 
         community_views.my_posts, 
         name='my_posts'),

    # ==================== LMS/TUTORIALS ====================
    path('api/tutorials/', 
         lms_views.TutorialListCreateView.as_view(), 
         name='tutorial_list_create'),
    path('api/tutorials/<int:pk>/', 
         lms_views.TutorialDetailView.as_view(), 
         name='tutorial_detail'),
    path('api/tutorials/<int:pk>/increment_views/', 
         lms_views.increment_views, 
         name='increment_views'),
    path('api/tutorials/my_tutorials/', 
         lms_views.my_tutorials, 
         name='my_tutorials'),
    path('api/tutorials/categories/', 
         lms_views.tutorial_categories, 
         name='tutorial_categories'),

    # ==================== DEEP LINKS ====================
    path('api/post/<int:post_id>/data/', 
         deep_link_views.post_deep_link_data, 
         name='post_deep_link_data'),
    path('post/<int:post_id>/', 
         deep_link_views.post_fallback_view, 
         name='post_fallback'),
    path('api/post/<int:post_id>/metadata/', 
         deep_link_views.generate_share_metadata, 
         name='post_share_metadata'),
    path('api/post/<int:post_id>/track-share/', 
         deep_link_views.track_share_analytics, 
         name='track_share'),

    # ==================== LANGUAGE ====================
    path('api/languages/', 
         views.get_available_languages, 
         name='get_languages'),

    # ==================== CONNECTION TESTER ====================
    path("tester/", 
         views.tester, 
         name="tester"),
]