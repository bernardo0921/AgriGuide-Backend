# views.py (Updated with Language Support)
import google.generativeai as genai
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
import json
import os
from .models import ChatSession, ChatMessage
from django.core.cache import cache
from datetime import date
import uuid
from PIL import Image
import io
from django.http import HttpResponse

# Import prompts from separate file
from .prompts import (
    get_system_instruction,
    get_vision_instruction,
    get_language_directive,
    get_supported_languages,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES
)


# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Initialize Gemini API
genai.configure(api_key=GEMINI_API_KEY, transport='rest')

# Set up models
text_model = genai.GenerativeModel('gemini-2.5-flash-lite')
vision_model = genai.GenerativeModel('gemini-2.5-flash-lite')


def validate_language(language: str) -> str:
    """Validate and return the language, defaulting if invalid"""
    if not language:
        return DEFAULT_LANGUAGE
    lang = language.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE
    return lang


def build_conversation_history(chat_session, exclude_message_id=None):
    """
    Build conversation history in Gemini's expected format
    Returns a list of {'role': 'user'/'model', 'parts': ['text']}
    """
    history_messages = ChatMessage.objects.filter(
        session=chat_session
    ).order_by('created_at')
    
    if exclude_message_id:
        history_messages = history_messages.exclude(id=exclude_message_id)
    
    history = []
    for msg in history_messages:
        if not msg.message or msg.role not in ['user', 'model']:
            continue
        history.append({
            'role': msg.role,
            'parts': [msg.message]
        })
    
    return history


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_languages(request):
    """Return list of supported languages"""
    return Response({
        'languages': get_supported_languages(),
        'default': DEFAULT_LANGUAGE
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_chat_session(request):
    """Clear a chat session"""
    try:
        session_id = request.data.get('session_id')
        
        if not session_id:
            return Response({
                'error': 'session_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        chat_session = ChatSession.objects.get(
            session_id=session_id,
            user=request.user
        )
        
        chat_session.is_active = False
        chat_session.save()
        
        print(f"🗑️ Session {session_id} marked as inactive")
        
        return Response({'message': 'Session cleared'})
        
    except ChatSession.DoesNotExist:
        return Response({
            'error': 'Session not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_chat_session(request, session_id):
    """Delete a chat session permanently"""
    try:
        chat_session = ChatSession.objects.get(
            session_id=session_id,
            user=request.user
        )
        
        message_count = chat_session.messages.count()
        chat_session.delete()
        
        print(f"🗑️ Deleted session {session_id} with {message_count} messages")
        
        return Response({
            'message': 'Session deleted successfully'
        })
        
    except ChatSession.DoesNotExist:
        return Response({
            'error': 'Session not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_connection(request):
    """Test endpoint to verify Gemini API connection"""
    try:
        response = text_model.generate_content('Hello, test connection')
        return Response({
            'status': 'connected',
            'response': response.text,
            'user': request.user.username
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_ai_stream(request):
    """
    Streaming endpoint for real-time typing animation with conversation memory
    Now supports language parameter: 'english' or 'sesotho'
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        language = validate_language(request.data.get('language'))
        
        if not message:
            return Response({
                'error': 'Message is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create chat session
        if session_id:
            try:
                chat_session = ChatSession.objects.get(
                    session_id=session_id,
                    user=request.user
                )
            except ChatSession.DoesNotExist:
                chat_session = ChatSession.objects.create(
                    user=request.user,
                    session_id=session_id
                )
        else:
            session_id = str(uuid.uuid4())
            chat_session = ChatSession.objects.create(
                user=request.user,
                session_id=session_id
            )
        
        # Save user message
        user_message = ChatMessage.objects.create(
            session=chat_session,
            role='user',
            message=message
        )
        
        # Get language-specific system instruction
        system_instruction = get_system_instruction(language)
        
        # Generator function for streaming
        def generate_response():
            try:
                # Build conversation history
                history = build_conversation_history(
                    chat_session, 
                    exclude_message_id=user_message.id
                )
                
                print(f"📚 Loading {len(history)} previous messages | Language: {language}")
                
                # Start chat with history
                chat = text_model.start_chat(history=history)
                
                # Send system instruction if history is empty
                if not history:
                    chat.send_message(system_instruction)
                
                # For subsequent messages, add language reminder if not English
                prompt_with_language = message
                if language != 'english' and history:
                    lang_reminder = get_language_directive(language)
                    prompt_with_language = f"{message}\n\n[Remember: {lang_reminder}]"
                
                # Generate streaming response
                response = chat.send_message(
                    prompt_with_language,
                    generation_config={
                        'temperature': 0.7,
                        'top_p': 0.8,
                        'top_k': 40,
                        'max_output_tokens': 1024
                    },
                    stream=True
                )
                
                full_response = ""
                
                # Send session_id and language first
                yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id, 'language': language})}\n\n"
                
                # Stream chunks
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                        yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
                
                # Save complete response
                ChatMessage.objects.create(
                    session=chat_session,
                    role='model',
                    message=full_response
                )
                
                chat_session.save()
                
                print(f"✅ Response saved in {language}. Session: {chat_session.messages.count()} messages")
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'done', 'full_text': full_response})}\n\n"
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                print(f"❌ Error in streaming: {error_msg}")
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
        
        # Return streaming response
        response = StreamingHttpResponse(
            generate_response(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_ai(request):
    """
    Standard endpoint for image analysis with conversation memory
    Now supports language parameter: 'english' or 'sesotho'
    """
    try:
        has_image = 'image' in request.FILES
        
        if has_image:
            message = request.data.get('message', '').strip()
            session_id = request.data.get('session_id')
            language = validate_language(request.data.get('language'))
            image_file = request.FILES['image']
        else:
            return Response({
                'error': 'Use /chat-stream endpoint for text messages'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create session
        if session_id:
            try:
                chat_session = ChatSession.objects.get(
                    session_id=session_id,
                    user=request.user
                )
            except ChatSession.DoesNotExist:
                chat_session = ChatSession.objects.create(
                    user=request.user,
                    session_id=session_id
                )
        else:
            session_id = str(uuid.uuid4())
            chat_session = ChatSession.objects.create(
                user=request.user,
                session_id=session_id
            )
        
        # Save user message with image
        user_message = ChatMessage.objects.create(
            session=chat_session,
            role='user',
            message=message or "Please analyze this image",
            image=image_file
        )
        
        # Process image
        img = Image.open(image_file)
        max_size = (1024, 1024)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        if img.format == 'JPEG':
            img = img.convert('RGB')
        
        # Build conversation history
        history = build_conversation_history(
            chat_session, 
            exclude_message_id=user_message.id
        )
        
        # Get language-specific vision instruction
        vision_instruction = get_vision_instruction(language)
        
        # Create context-aware prompt
        vision_prompt = f"{vision_instruction}\n\n"
        
        # Add conversation context if exists
        if history:
            vision_prompt += "Previous conversation context:\n"
            for msg in history[-4:]:
                role = "User" if msg['role'] == 'user' else "AI"
                vision_prompt += f"{role}: {msg['parts'][0][:200]}...\n"
            vision_prompt += "\n"
        
        if message:
            vision_prompt += f"User's question: {message}\n\n"
        
        vision_prompt += "Please analyze the image and provide detailed information."
        
        print(f"📸 Analyzing image | Language: {language} | Context: {len(history)} messages")
        
        # Generate vision response
        response = vision_model.generate_content(
            [vision_prompt, img],
            generation_config={
                'temperature': 0.4,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 1024
            }
        )
        
        ai_response = response.text
        
        # Save AI response
        ChatMessage.objects.create(
            session=chat_session,
            role='model',
            message=ai_response
        )
        
        chat_session.save()
        
        print(f"✅ Image analysis complete in {language}. Session: {chat_session.messages.count()} messages")
        
        return Response({
            'response': ai_response,
            'session_id': session_id,
            'language': language,
            'image_url': user_message.image_url
        })
        
    except Exception as e:
        print(f"❌ Error in image analysis: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_sessions(request):
    """Get all chat sessions for the authenticated user"""
    sessions = ChatSession.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-updated_at')
    
    sessions_data = []
    for session in sessions:
        last_message = session.messages.last()
        sessions_data.append({
            'session_id': session.session_id,
            'created_at': session.created_at,
            'updated_at': session.updated_at,
            'message_count': session.messages.count(),
            'last_message': last_message.message if last_message else None
        })
    
    return Response({'sessions': sessions_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request, session_id):
    """Get chat history for a specific session"""
    try:
        chat_session = ChatSession.objects.get(
            session_id=session_id,
            user=request.user
        )
        
        messages = ChatMessage.objects.filter(
            session=chat_session
        ).order_by('created_at')
        
        history = []
        for msg in messages:
            history.append({
                'role': msg.role,
                'message': msg.message,
                'image_url': msg.image_url,
                'created_at': msg.created_at
            })
        
        return Response({
            'session_id': session_id,
            'history': history
        })
        
    except ChatSession.DoesNotExist:
        return Response({
            'error': 'Session not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tester(request):
    return Response({"status": "available"})