# voice_views.py - Voice chat with Hugging Face + Edge TTS (Free, No Quota)
import os
import uuid
import struct
import mimetypes
import asyncio
import base64
from django.http import FileResponse, JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import requests
import edge_tts
from .models import ChatSession, ChatMessage
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import tempfile
import io

# Hugging Face model for text generation (free, no quota)
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
HF_API_TOKEN = os.environ.get('HF_API_TOKEN')  # Optional: use free tier without token or provide yours

# Edge TTS voice (free, built-in, no key needed)
EDGE_TTS_VOICE = "en-US-AriaNeural"  # Available voices: en-US-GuyNeural, en-US-AriaNeural, en-GB-SoniaNeural, etc.

# System instruction for voice chat
VOICE_SYSTEM_INSTRUCTION = """
You are AgriGuide AI, a friendly agricultural advisor. Keep responses concise and conversational for voice chat.
- Use short sentences suitable for speech
- Avoid complex formatting or bullet points
- Keep responses under 3-4 sentences when possible for quick voice interaction
- Be warm and encouraging
- Use simple, clear language
"""


async def generate_speech(text: str, voice: str = EDGE_TTS_VOICE) -> bytes:
    """Generate speech from text using Edge TTS (free, no quota)"""
    try:
        output = io.BytesIO()
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                output.write(chunk["data"])
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        print(f"Error generating speech: {str(e)}")
        raise


def generate_text_hf(prompt: str) -> str:
    """Generate text using Hugging Face Inference API"""
    api_url = "https://router.huggingface.co/hf-inference/mistralai/Mistral-7B-Instruct-v0.1"
    
    hf_token = os.getenv('HF_API_TOKEN')
    headers = {
        "Authorization": f"Bearer {hf_token}" if hf_token else "",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.7,
        }
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 410:
            raise Exception(f"Hugging Face API error: {response.status_code} - {response.text}")
        
        if response.status_code == 429:
            raise Exception(f"Rate limited by Hugging Face. Please retry in a few moments.")
        
        if response.status_code != 200:
            raise Exception(f"Hugging Face API error: {response.status_code}")
        
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "").strip()
        elif isinstance(result, dict):
            return result.get("generated_text", "").strip()
        
        return "Unable to generate response"
    
    except requests.exceptions.Timeout:
        raise Exception("Hugging Face API request timed out")
    except Exception as e:
        raise Exception(f"Hugging Face API error: {str(e)}")





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_chat(request):
    """
    Voice chat endpoint - Returns audio response using free Hugging Face + Edge TTS
    Expected JSON: {
        "message": "user text message",
        "session_id": "optional_session_id",
        "voice": "en-US-AriaNeural" (optional, default: "en-US-AriaNeural")
    }
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        voice_name = request.data.get('voice', EDGE_TTS_VOICE)
        
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
        
        # Get conversation history (last 5 messages)
        last_messages_qs = ChatMessage.objects.filter(
            session=chat_session
        ).order_by('-created_at')[:5]

        # Convert to list and reverse to get oldest->newest ordering
        last_messages = list(last_messages_qs)[::-1]

        # Build conversation history for context
        conversation_context = ""
        for msg in last_messages:
            role = "User" if msg.role == "user" else "Assistant"
            conversation_context += f"{role}: {msg.message}\n"
        
        # Combine system instruction with context
        prompt = f"{VOICE_SYSTEM_INSTRUCTION}\n\nConversation History:\n{conversation_context}\n\nUser: {message}\n\nRespond naturally and concisely:"
        
        # Generate text response using Hugging Face (free, no quota)
        text_response = generate_text_hf(prompt)
        
        # Save messages to database
        ChatMessage.objects.create(
            session=chat_session,
            role='user',
            message=message
        )
        
        ChatMessage.objects.create(
            session=chat_session,
            role='model',
            message=text_response
        )
        
        chat_session.save()
        
        # Generate speech using Edge TTS (free, unlimited)
        try:
            audio_data = asyncio.run(generate_speech(text_response, voice_name))
            
            # Return JSON response with audio in base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_base64': audio_base64,
                'audio_format': 'wav',
                'voice_used': voice_name
            })
        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            # Return text-only response if speech generation fails
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_base64': None,
                'voice_used': voice_name,
                'warning': 'Could not generate audio, returning text only'
            })
            
    except Exception as e:
        print(f"❌ Error in voice_chat: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_chat_stream(request):
    """
    Streaming voice chat - Returns audio in base64
    Better for real-time responses
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        voice_name = request.data.get('voice', EDGE_TTS_VOICE)
        
        if not message:
            return Response({
                'error': 'Message is required'
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
        
        # Build prompt
        prompt = f"{VOICE_SYSTEM_INSTRUCTION}\n\n{message}"
        
        # Generate text response
        text_response = generate_text_hf(prompt)
        
        # Save to database
        ChatMessage.objects.create(session=chat_session, role='user', message=message)
        ChatMessage.objects.create(session=chat_session, role='model', message=text_response)
        chat_session.save()
        
        # Generate speech
        try:
            audio_data = asyncio.run(generate_speech(text_response, voice_name))
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_base64': audio_base64,
                'audio_format': 'wav',
                'voice_used': voice_name
            })
        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_base64': None,
                'voice_used': voice_name,
                'warning': 'Could not generate audio'
            })
            
    except Exception as e:
        print(f"❌ Error in voice_chat_stream: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_voices(request):
    """Return list of available Edge TTS voices (free, no quota)"""
    voices = [
        {'name': 'en-US-AriaNeural', 'description': 'Friendly female voice', 'language': 'English (US)'},
        {'name': 'en-US-GuyNeural', 'description': 'Professional male voice', 'language': 'English (US)'},
        {'name': 'en-GB-SoniaNeural', 'description': 'British female voice', 'language': 'English (UK)'},
        {'name': 'en-AU-NatashaNeural', 'description': 'Australian female voice', 'language': 'English (AU)'},
        {'name': 'en-IN-NeerjaNeural', 'description': 'Indian female voice', 'language': 'English (IN)'},
    ]
    
    return Response({'voices': voices})