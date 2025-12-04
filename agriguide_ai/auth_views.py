# auth_views.py - UPDATED WITH APPROVAL MIDDLEWARE

from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.authtoken.models import Token
from django.contrib.auth import logout
from .models import User
from .serializers import (
    FarmerRegistrationSerializer,
    ExtensionWorkerRegistrationSerializer,
    LoginSerializer,
    UserSerializer,
    ChangePasswordSerializer
)
from .permissions import IsApprovedOrFarmer  # NEW IMPORT


class FarmerRegistrationView(generics.CreateAPIView):
    """Register a new farmer - SIMPLIFIED"""
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = FarmerRegistrationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        farmer_profile = serializer.save()

        user = farmer_profile.user
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'message': 'Farmer registration successful',
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)


class ExtensionWorkerRegistrationView(generics.CreateAPIView):
    """Register a new extension worker"""
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = ExtensionWorkerRegistrationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        worker_profile = serializer.save()

        user = worker_profile.user
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'message': 'Extension worker registration successful. '
                       'Your account is pending approval.',
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login endpoint (OLD - kept for backward compatibility)
    🔒 NOW CHECKS EXTENSION WORKER APPROVAL
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # 🔒 CHECK IF EXTENSION WORKER IS APPROVED
        if user.user_type == 'extension_worker':
            try:
                worker_profile = user.extension_worker_profile
                if not worker_profile.is_approved:
                    return Response({
                        'error': 'Your account is pending approval. Please wait for admin approval.',
                        'error_code': 'ACCOUNT_PENDING_APPROVAL'
                    }, status=status.HTTP_403_FORBIDDEN)
            except:
                return Response({
                    'error': 'Extension worker profile not found.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout endpoint - deletes user token"""
    print(f"Logout requested for user: {request.user.username}")
    
    try:
        from rest_framework.authtoken.models import Token
        
        token_exists = Token.objects.filter(user=request.user).exists()
        print(f"Token exists before logout: {token_exists}")
        
        if token_exists:
            Token.objects.filter(user=request.user).delete()
            print("Token deleted successfully")
        
        logout(request)
        print("Django logout completed")
        
        return Response({
            'message': 'Successfully logged out',
            'token_deleted': token_exists
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Logout error: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsApprovedOrFarmer])  # 🔒 APPROVAL CHECK
def profile_view(request):
    """Get current user profile - BLOCKS UNAPPROVED EXTENSION WORKERS"""
    serializer = UserSerializer(request.user, context={'request': request})
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, IsApprovedOrFarmer])  # 🔒 APPROVAL CHECK
@parser_classes([MultiPartParser, FormParser, JSONParser])
def update_profile_view(request):
    """
    Update current user profile - BLOCKS UNAPPROVED EXTENSION WORKERS
    SIMPLIFIED - farmers don't have farm fields anymore
    """
    user = request.user
    data = request.data.copy()
    
    serializer = UserSerializer(user, data=data, partial=True, context={'request': request})
    
    if serializer.is_valid():
        try:
            serializer.save()
            return Response({
                'message': 'Profile updated successfully',
                'user': serializer.data
            })
        except Exception as e:
            return Response({
                'error': f'Failed to save profile: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsApprovedOrFarmer])  # 🔒 APPROVAL CHECK
def change_password_view(request):
    """Change user password - BLOCKS UNAPPROVED EXTENSION WORKERS"""
    serializer = ChangePasswordSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        
        return Response({
            'message': 'Password changed successfully',
            'token': token.key
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_token(request):
    """
    Verify if token is valid
    🔒 RETURNS APPROVAL STATUS
    """
    user_data = UserSerializer(request.user, context={'request': request}).data
    
    # Add approval status check for extension workers
    is_approved = True
    if request.user.user_type == 'extension_worker':
        try:
            is_approved = request.user.extension_worker_profile.is_approved
        except:
            is_approved = False
    
    return Response({
        'valid': True,
        'user': user_data,
        'is_approved': is_approved,
        'requires_approval': request.user.user_type == 'extension_worker'
    })