# twofa_views.py - WITH EXTENSION WORKER APPROVAL CHECK

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db import transaction
from decimal import Decimal
from .models import VerificationCode, User, FarmerProfile, ExtensionWorkerProfile
from .serializers import UserSerializer
from .microsoft_email_utils import send_verification_email, send_welcome_email
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_verification_code(request):
    """
    Step 1: Request a verification code for registration or login
    SIMPLIFIED FOR FARMERS - only basic fields needed
    """
    logger.info(f"🎯 Verification request received from {request.data.get('email')}")
    
    try:
        email = request.data.get('email')
        purpose = request.data.get('purpose', 'registration')
        
        if not email:
            return Response({
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if purpose not in ['registration', 'login']:
            return Response({
                'error': 'Purpose must be either "registration" or "login"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For login, check if user exists
        if purpose == 'login':
            if not User.objects.filter(email=email).exists():
                return Response({
                    'error': 'No account found with this email'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # For registration, validate and store data
        registration_data = None
        if purpose == 'registration':
            if User.objects.filter(email=email).exists():
                return Response({
                    'error': 'This email is already registered'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # SIMPLIFIED validation for farmers
            required_fields = ['username', 'password', 'password_confirm', 
                             'first_name', 'last_name', 'phone_number', 'user_type']
            missing_fields = [f for f in required_fields if not request.data.get(f)]
            
            if missing_fields:
                return Response({
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if User.objects.filter(username=request.data.get('username')).exists():
                return Response({
                    'error': 'This username is already taken'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if request.data.get('password') != request.data.get('password_confirm'):
                return Response({
                    'error': 'Passwords do not match'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            password = request.data.get('password')
            if len(password) < 8:
                return Response({
                    'error': 'Password must be at least 8 characters long'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_type = request.data.get('user_type')
            
            # Build registration data - SIMPLIFIED for farmers
            registration_data = {
                'username': request.data.get('username'),
                'password': request.data.get('password'),
                'email': email,
                'first_name': request.data.get('first_name'),
                'last_name': request.data.get('last_name'),
                'phone_number': request.data.get('phone_number'),
                'user_type': user_type,
            }
            
            # Extension worker still needs their fields
            if user_type == 'extension_worker':
                worker_required = ['organization', 'specialization']
                missing_worker = [f for f in worker_required if not request.data.get(f)]
                
                if missing_worker:
                    return Response({
                        'error': f'Missing extension worker fields: {", ".join(missing_worker)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                registration_data['extension_worker_profile'] = {
                    'organization': request.data.get('organization'),
                    'employee_id': request.data.get('employee_id', ''),
                    'specialization': request.data.get('specialization'),
                    'regions_covered': request.data.get('regions_covered', []),
                }
            
            elif user_type != 'farmer':
                return Response({
                    'error': 'Invalid user_type. Must be "farmer" or "extension_worker"'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create verification code
        logger.info(f"📧 Creating verification code for {email}")
        verification, created = VerificationCode.create_verification(
            email=email,
            purpose=purpose,
            registration_data=registration_data,
            expiry_minutes=5
        )
        
        # Send email
        logger.info(f"📤 Sending verification email to {email}")
        email_sent = send_verification_email(email, verification.code, purpose)
        
        if not email_sent:
            logger.error(f"❌ Failed to send email to {email}")
        
        logger.info(f"✅ Verification code created for {email} (Purpose: {purpose})")
        
        response_data = {
            'message': f'Verification code sent to {email}',
            'email': email,
            'purpose': purpose,
            'expires_in_minutes': 5,
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except ValueError as e:
        logger.warning(f"⚠️ Rate limit exceeded for {email}: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    except Exception as e:
        logger.error(f"❌ Error in request_verification_code: {str(e)}", exc_info=True)
        return Response({
            'error': 'An unexpected error occurred. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_code_and_register(request):
    """
    Step 2: Verify code and complete registration
    SIMPLIFIED FOR FARMERS - no farm fields needed
    """
    logger.info(f"🔍 Registration verification request for {request.data.get('email')}")
    
    try:
        email = request.data.get('email')
        code = request.data.get('code')
        purpose = request.data.get('purpose')
        
        if not all([email, code, purpose]):
            return Response({
                'error': 'Email, code, and purpose are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if purpose != 'registration':
            return Response({
                'error': 'This endpoint is for registration only'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(code) != 6 or not code.isdigit():
            return Response({
                'error': 'Code must be 6 digits'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get verification code
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
        
        # Get stored registration data
        registration_data = verification.registration_data
        
        if not registration_data:
            return Response({
                'error': 'Registration data not found. Please start registration again.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"✅ Code verified for {email}. Creating user...")
        
        # Create user and profile in a transaction
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
            
            logger.info(f"👤 User created: {user.username}")
            
            # Create profile based on user type
            if registration_data['user_type'] == 'farmer':
                # SIMPLIFIED - just create empty profile
                FarmerProfile.objects.create(user=user)
                logger.info(f"🌾 Farmer profile created")
            
            elif registration_data['user_type'] == 'extension_worker':
                worker_data = registration_data.get('extension_worker_profile', {})
                ExtensionWorkerProfile.objects.create(
                    user=user,
                    organization=worker_data.get('organization', ''),
                    employee_id=worker_data.get('employee_id', ''),
                    specialization=worker_data.get('specialization', ''),
                    regions_covered=worker_data.get('regions_covered', []),
                    is_approved=False  # 🔒 NOT APPROVED BY DEFAULT
                )
                logger.info(f"👨‍🏫 Extension worker profile created (PENDING APPROVAL)")
            
            # Create authentication token
            token = Token.objects.create(user=user)
            
            # Send welcome email
            try:
                send_welcome_email(email, user.username)
            except Exception as e:
                logger.warning(f"⚠️ Failed to send welcome email: {e}")
            
            logger.info(f"🎉 Registration complete for {user.username}")
            
            return Response({
                'message': 'Registration successful!',
                'user': UserSerializer(user).data,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"❌ Registration error: {str(e)}", exc_info=True)
        return Response({
            'error': 'Registration failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_code_and_login(request):
    """
    Step 2: Verify code and complete login
    🔒 BLOCKS UNAPPROVED EXTENSION WORKERS
    """
    logger.info(f"🔍 Login verification request for {request.data.get('email')}")
    
    try:
        email = request.data.get('email')
        code = request.data.get('code')
        purpose = request.data.get('purpose')
        password = request.data.get('password')
        
        if not all([email, code, purpose, password]):
            return Response({
                'error': 'Email, code, purpose, and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if purpose != 'login':
            return Response({
                'error': 'This endpoint is for login only'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(code) != 6 or not code.isdigit():
            return Response({
                'error': 'Code must be 6 digits'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get verification code
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
        
        # Get user
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
                'error': 'Account is inactive. Please contact support.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 🔒 CHECK IF EXTENSION WORKER IS APPROVED
        if user.user_type == 'extension_worker':
            try:
                worker_profile = user.extension_worker_profile
                if not worker_profile.is_approved:
                    logger.warning(f"🚫 Unapproved extension worker tried to login: {user.username}")
                    return Response({
                        'error': 'Your account is pending approval. Please wait for admin approval.',
                        'error_code': 'ACCOUNT_PENDING_APPROVAL'
                    }, status=status.HTTP_403_FORBIDDEN)
            except ExtensionWorkerProfile.DoesNotExist:
                return Response({
                    'error': 'Extension worker profile not found.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create token
        token, created = Token.objects.get_or_create(user=user)
        
        logger.info(f"✅ User {user.username} logged in successfully")
        
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}", exc_info=True)
        return Response({
            'error': 'Login failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def complete_extension_worker_registration(request):
    """
    Step 2: Complete extension worker registration with file upload
    """
    logger.info(f"👨‍🏫 Extension worker verification for {request.data.get('email')}")
    
    try:
        email = request.data.get('email')
        code = request.data.get('code')
        
        if not email or not code:
            return Response({
                'error': 'Email and code are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(code) != 6 or not code.isdigit():
            return Response({
                'error': 'Code must be 6 digits'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get verification code
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
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get stored registration data
        registration_data = verification.registration_data
        if not registration_data:
            return Response({
                'error': 'Registration data not found. Please start registration again.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"✅ Code verified. Creating extension worker...")
        
        # Create user and profile in transaction
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
            
            logger.info(f"👤 User created: {user.username}")
            
            # Create extension worker profile
            worker_data = registration_data.get('extension_worker_profile', {})
            profile = ExtensionWorkerProfile.objects.create(
                user=user,
                organization=worker_data.get('organization', ''),
                employee_id=worker_data.get('employee_id', ''),
                specialization=worker_data.get('specialization', ''),
                regions_covered=worker_data.get('regions_covered', []),
                is_approved=False  # 🔒 NOT APPROVED BY DEFAULT
            )
            
            # Handle uploaded verification document
            verification_doc = request.FILES.get('verification_document')
            if verification_doc:
                profile.verification_document = verification_doc
                profile.save()
                logger.info(f"📄 Verification document uploaded")
            
            # Create token
            token = Token.objects.create(user=user)
            
            # Send welcome email
            try:
                send_welcome_email(email, user.username)
            except Exception as e:
                logger.warning(f"⚠️ Failed to send welcome email: {e}")
            
            logger.info(f"🎉 Extension worker registration complete for {user.username} (PENDING APPROVAL)")
            
            return Response({
                'message': 'Registration successful! Your account is pending approval.',
                'user': UserSerializer(user).data,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        logger.error(f"❌ Extension worker registration error: {str(e)}", exc_info=True)
        return Response({
            'error': 'Registration failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_code(request):
    """Resend verification code"""
    logger.info(f"🔄 Resend request for {request.data.get('email')}")
    
    try:
        email = request.data.get('email')
        purpose = request.data.get('purpose')
        
        if not email or not purpose:
            return Response({
                'error': 'Email and purpose are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if purpose not in ['registration', 'login']:
            return Response({
                'error': 'Purpose must be "registration" or "login"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get most recent unverified code
        verification = VerificationCode.objects.filter(
            email=email,
            purpose=purpose,
            verified_at__isnull=True
        ).order_by('-created_at').first()
        
        if not verification:
            return Response({
                'error': 'No pending verification found. Please request a new code.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check resend limit
        if verification.send_count >= 3:
            return Response({
                'error': 'Maximum resend limit reached. Please request a new code.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Generate new code
        new_code = VerificationCode.generate_code()
        verification.code = new_code
        verification.send_count += 1
        verification.attempts = 0
        verification.save()
        
        # Send email
        email_sent = send_verification_email(email, new_code, purpose)
        
        if not email_sent:
            logger.warning(f"⚠️ Failed to send email to {email}")
        
        logger.info(f"✅ Verification code resent to {email}")
        
        return Response({
            'message': f'New verification code sent to {email}',
            'email': email,
            'purpose': purpose
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Resend error: {str(e)}", exc_info=True)
        return Response({
            'error': 'Failed to resend code. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)