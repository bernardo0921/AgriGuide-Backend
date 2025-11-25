# agriguide_ai/notification_views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from .models import Notification
from .serializers import NotificationSerializer
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """
    Get all notifications for the authenticated user
    Query params:
    - unread_only: boolean (optional) - Filter for unread notifications only
    - limit: int (optional) - Limit number of results (default: 50)
    """
    try:
        user = request.user
        unread_only = request.GET.get('unread_only', 'false').lower() == 'true'
        limit = int(request.GET.get('limit', 50))
        
        # Build query
        notifications = Notification.objects.filter(recipient=user)
        
        if unread_only:
            notifications = notifications.filter(is_read=False)
        
        # Limit results
        notifications = notifications[:limit]
        
        # Serialize
        serializer = NotificationSerializer(
            notifications, 
            many=True,
            context={'request': request}
        )
        
        return Response({
            'count': notifications.count(),
            'unread_count': Notification.objects.filter(
                recipient=user, 
                is_read=False
            ).count(),
            'notifications': serializer.data
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid limit parameter'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}", exc_info=True)
        return Response({
            'error': 'Failed to fetch notifications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """
    Get count of unread notifications for the authenticated user
    """
    try:
        user = request.user
        unread_count = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()
        
        return Response({
            'unread_count': unread_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching unread count: {str(e)}", exc_info=True)
        return Response({
            'error': 'Failed to fetch unread count'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """
    Mark a specific notification as read
    """
    try:
        user = request.user
        
        notification = Notification.objects.filter(
            id=notification_id,
            recipient=user
        ).first()
        
        if not notification:
            return Response({
                'error': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Mark as read
        notification.is_read = True
        notification.save()
        
        return Response({
            'message': 'Notification marked as read',
            'notification': NotificationSerializer(
                notification,
                context={'request': request}
            ).data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}", exc_info=True)
        return Response({
            'error': 'Failed to mark notification as read'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """
    Mark all notifications as read for the authenticated user
    """
    try:
        user = request.user
        
        # Update all unread notifications
        updated_count = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).update(is_read=True)
        
        return Response({
            'message': f'{updated_count} notifications marked as read',
            'count': updated_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}", exc_info=True)
        return Response({
            'error': 'Failed to mark all notifications as read'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """
    Delete a specific notification
    """
    try:
        user = request.user
        
        notification = Notification.objects.filter(
            id=notification_id,
            recipient=user
        ).first()
        
        if not notification:
            return Response({
                'error': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        notification.delete()
        
        return Response({
            'message': 'Notification deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
        
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}", exc_info=True)
        return Response({
            'error': 'Failed to delete notification'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_notifications(request):
    """
    Delete all notifications for the authenticated user
    """
    try:
        user = request.user
        
        deleted_count, _ = Notification.objects.filter(
            recipient=user
        ).delete()
        
        return Response({
            'message': f'{deleted_count} notifications deleted',
            'count': deleted_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error deleting all notifications: {str(e)}", exc_info=True)
        return Response({
            'error': 'Failed to delete notifications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)