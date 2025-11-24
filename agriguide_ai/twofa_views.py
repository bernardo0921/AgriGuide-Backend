# twofa_views.py - Create this new file for 2FA views - FIXED

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db import transaction
from .models import VerificationCode, User, FarmerProfile, ExtensionWorkerProfile
from .serializers import (
    RequestVerificationSerializer,
    VerifyCodeSerializer,
    ResendCodeSerializer,
    UserSerializer
)
from .email_utils import send_verification_email, send_welcome_email
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_verification_code(request):
    """
    Step 1: Request a verification code for registration or login
    
    For Registration: Include user details + email
    For Login: Just include email
    """
    serializer = RequestVerificationSerializer(data=request.data)
    
    if not serializer.is_valid():
        logger.error(f"Validation error: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    purpose = serializer.validated_data['purpose']
    
    try:
        # Store registration data if purpose is registration
        registration_data = None
        if purpose == 'registration':
            registration_data = {
                'username': serializer.validated_data.get('username'),
                'password': serializer.validated_data.get('password'),
                'email': email,
                'first_name': serializer.validated_data.get('first_name'),
                'last_name': serializer.validated_data.get('last_name'),
                'phone_number': serializer.validated_data.get('phone_number'),
                'user_type': serializer.validated_data.get('user_type'),
            }
            
            # Add type-specific fields
            user_type = serializer.validated_data.get('user_type')
            if user_type == 'farmer':
                # Convert farm_size to string for JSON storage
                farm_size = serializer.validated_data.get('farm_size')
                farm_size_str = str(farm_size) if farm_size else '0'
                
                registration_data['farmer_profile'] = {
                    'farm_name': serializer.validated_data.get('farm_name', ''),
                    'farm_size': farm_size_str,
                    'location': serializer.validated_data.get('location', ''),
                    'region': serializer.validated_data.get('region', ''),
                    'crops_grown': serializer.validated_data.get('crops_grown', []),
                    'farming_method': serializer.validated_data.get('farming_method', 'conventional'),
                    'years_of_experience': serializer.validated_data.get('years_of_experience', 0),
                }
            elif user_type == 'extension_worker':
                registration_data['extension_worker_profile'] = {
                    'organization': serializer.validated_data.get('organization', ''),
                    'employee_id': serializer.validated_data.get('employee_id', ''),
                    'specialization': serializer.validated_data.get('specialization', ''),
                    'regions_covered': serializer.validated_data.get('regions_covered', []),
                }
        
        # Create verification code
        verification, created = VerificationCode.create_verification(
            email=email,
            purpose=purpose,
            registration_data=registration_data,
            expiry_minutes=5
        )
        
        # Send email
        email_sent = send_verification_email(email, verification.code, purpose)
        
        if not email_sent:
            logger.error(f"Failed to send email to {email}")
            return Response({
                'error': 'Failed to send verification email. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.info(f"✅ Verification code sent to {email} for {purpose}")
        
        return Response({
            'message': f'Verification code sent to {email}',
            'email': email,
            'purpose': purpose,
            'expires_in_minutes': 5
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        # Rate limit exceeded
        logger.warning(f"Rate limit exceeded for {email}: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    except Exception as e:
        logger.error(f"Error creating verification code: {str(e)}", exc_info=True)
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_code_and_register(request):
    """
    Step 2: Verify code and complete registration
    """
    serializer = VerifyCodeSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    purpose = serializer.validated_data['purpose']
    
    if purpose != 'registration':
        return Response({
            'error': 'This endpoint is for registration only. Use /verify-code-and-login for login.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get the verification code
        verification = VerificationCode.objects.filter(
            email=email,
            purpose='registration',
            verified_at__isnull=True
        ).order_by('-created_at').first()
        
        if not verification:
            return Response({
                'error': 'No verification code found. Please request a new one.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify the code
        success, message = verification.verify(code)
        
        if not success:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Code verified! Now create the user
        registration_data = verification.registration_data
        
        if not registration_data:
            return Response({
                'error': 'Registration data not found. Please start registration again.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=registration_data['username'],
                email=registration_data['email'],
                password=registration_data['password'],
                first_name=registration_data['first_name'],
                last_name=registration_data['last_name'],
                phone_number=registration_data.get('phone_number', ''),
                user_type=registration_data['user_type']
            )
            
            # Create profile based on user type
            if registration_data['user_type'] == 'farmer':
                farmer_data = registration_data.get('farmer_profile', {})
                FarmerProfile.objects.create(
                    user=user,
                    farm_name=farmer_data.get('farm_name', ''),
                    farm_size=Decimal(farmer_data.get('farm_size', '0')),  # Convert back to Decimal
                    location=farmer_data.get('location', ''),
                    region=farmer_data.get('region', ''),
                    crops_grown=farmer_data.get('crops_grown', []),
                )
            
            elif registration_data['user_type'] == 'extension_worker':
                worker_data = registration_data.get('extension_worker_profile', {})
                ExtensionWorkerProfile.objects.create(
                    user=user,
                    organization=worker_data.get('organization', ''),
                    specialization=worker_data.get('specialization', ''),
                    years_of_experience=worker_data.get('years_of_experience', 0),
                    is_approved=False  # Requires approval
                )
            
            # Create token
            token = Token.objects.create(user=user)
            
            # Send welcome email (async if possible)
            send_welcome_email(email, user.username)
            
            logger.info(f"✅ User {user.username} registered successfully via 2FA")
            
            return Response({
                'message': 'Registration successful!',
                'user': UserSerializer(user).data,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return Response({
            'error': 'Registration failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_code_and_login(request):
    """
    Step 2: Verify code and complete login
    
    Body: {
        "email": "user@example.com",
        "code": "123456",
        "purpose": "login",
        "password": "user_password"
    }
    """
    serializer = VerifyCodeSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    purpose = serializer.validated_data['purpose']
    password = request.data.get('password')
    
    if purpose != 'login':
        return Response({
            'error': 'This endpoint is for login only. Use /verify-code-and-register for registration.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not password:
        return Response({
            'error': 'Password is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get the verification code
        verification = VerificationCode.objects.filter(
            email=email,
            purpose='login',
            verified_at__isnull=True
        ).order_by('-created_at').first()
        
        if not verification:
            return Response({
                'error': 'No verification code found. Please request a new one.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify the code
        success, message = verification.verify(code)
        
        if not success:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Code verified! Now authenticate user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check password
        if not user.check_password(password):
            return Response({
                'error': 'Invalid password'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if user is active
        if not user.is_active:
            return Response({
                'error': 'Account is inactive'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get or create token
        token, created = Token.objects.get_or_create(user=user)
        
        logger.info(f"✅ User {user.username} logged in successfully via 2FA")
        
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response({
            'error': 'Login failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_code(request):
    """
    Resend verification code
    
    Body: {
        "email": "user@example.com",
        "purpose": "registration" or "login"
    }
    """
    serializer = ResendCodeSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    purpose = serializer.validated_data['purpose']
    
    try:
        # Get the most recent unverified code
        verification = VerificationCode.objects.filter(
            email=email,
            purpose=purpose,
            verified_at__isnull=True
        ).order_by('-created_at').first()
        
        if not verification:
            return Response({
                'error': 'No pending verification found. Please request a new code.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if we can resend (not too many attempts)
        if verification.send_count >= 3:
            return Response({
                'error': 'Maximum resend limit reached. Please request a new code.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Generate new code
        new_code = VerificationCode.generate_code()
        verification.code = new_code
        verification.send_count += 1
        verification.attempts = 0  # Reset attempts
        verification.save()
        
        # Send email
        email_sent = send_verification_email(email, new_code, purpose)
        
        if not email_sent:
            return Response({
                'error': 'Failed to send verification email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.info(f"✅ Verification code resent to {email}")
        
        return Response({
            'message': f'New verification code sent to {email}',
            'email': email,
            'purpose': purpose
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Resend error: {str(e)}")
        return Response({
            'error': 'Failed to resend code'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
@permission_classes([AllowAny])
def complete_extension_worker_registration(request):
    """
    Complete extension worker registration with file upload
    """
    email = request.data.get('email')
    code = request.data.get('code')
    
    if not email or not code:
        return Response({
            'error': 'Email and code are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Verify code
        verification = VerificationCode.objects.filter(
            email=email,
            purpose='registration',
            verified_at__isnull=True
        ).order_by('-created_at').first()
        
        if not verification:
            return Response({
                'error': 'No verification code found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        success, message = verification.verify(code)
        if not success:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get stored registration data
        registration_data = verification.registration_data
        if not registration_data:
            return Response({
                'error': 'Registration data not found'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=registration_data['username'],
                email=registration_data['email'],
                password=registration_data['password'],
                first_name=registration_data['first_name'],
                last_name=registration_data['last_name'],
                phone_number=registration_data.get('phone_number', ''),
                user_type='extension_worker'
            )
            
            # Create extension worker profile
            worker_data = registration_data.get('extension_worker_profile', {})
            profile = ExtensionWorkerProfile.objects.create(
                user=user,
                organization=worker_data.get('organization', ''),
                employee_id=worker_data.get('employee_id', ''),
                specialization=worker_data.get('specialization', ''),
                regions_covered=worker_data.get('regions_covered', []),
                is_approved=False
            )
            
            # Handle uploaded file if present
            verification_doc = request.FILES.get('verification_document')
            if verification_doc:
                profile.verification_document = verification_doc
                profile.save()
            
            # Create token
            token = Token.objects.create(user=user)
            
            send_welcome_email(email, user.username)
            
            return Response({
                'message': 'Registration successful!',
                'user': UserSerializer(user).data,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        logger.error(f"Extension worker registration error: {str(e)}")
        return Response({
            'error': 'Registration failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)