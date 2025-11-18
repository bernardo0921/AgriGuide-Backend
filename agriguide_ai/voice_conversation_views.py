# agriguide_ai/voice_conversation_views.py
# FIXED VERSION - Handles all edge cases properly

import os
import uuid
import asyncio
import base64
import io
import requests
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import edge_tts
import google.generativeai as genai
from .models import ChatSession, ChatMessage

# ============ CONFIGURATION ============
HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
EDGE_TTS_VOICE = "en-US-AriaNeural"

# Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
else:
    gemini_model = None

# Hugging Face Whisper API endpoint
HF_WHISPER_API = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"

VOICE_SYSTEM_INSTRUCTION = """
You are AgriGuide AI, a friendly agricultural advisor for voice conversations.
Keep responses SHORT and conversational (2-3 sentences max).
Use simple language suitable for voice.
Be warm, encouraging, and helpful.
"""


# ============ SPEECH-TO-TEXT (FIXED) ============
def transcribe_audio_hf(audio_bytes: bytes) -> dict:
    """Transcribe audio using Hugging Face Inference API - FIXED VERSION"""
    if not HUGGINGFACE_API_KEY:
        return {
            'success': False,
            'error': 'HUGGINGFACE_API_KEY not configured. Please add it to environment variables.'
        }
    
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
    }
    
    try:
        print("🎤 Transcribing audio with Hugging Face Whisper...")
        print(f"🔑 Using API key: {HUGGINGFACE_API_KEY[:10]}...{HUGGINGFACE_API_KEY[-5:]}")
        print(f"📦 Audio size: {len(audio_bytes)} bytes")
        
        # Send as binary data, let HF detect format
        response = requests.post(
            HF_WHISPER_API,
            headers=headers,
            data=audio_bytes,  # Send raw bytes
            timeout=60
        )
        
        print(f"📥 Response status: {response.status_code}")
        
        # Handle 503 (model loading) BEFORE trying to parse JSON
        if response.status_code == 503:
            print("⏳ Model is loading...")
            return {
                'success': False,
                'error': 'AI model is warming up (10-20 seconds). Please try again.',
                'retry': True
            }
        
        # Handle 401 (auth error)
        if response.status_code == 401:
            print("❌ Authentication failed")
            return {
                'success': False,
                'error': 'Invalid API key. Please check HUGGINGFACE_API_KEY.'
            }
        
        # Try to parse response
        try:
            result = response.json()
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")
            print(f"Raw response: {response.text[:500]}")
            return {
                'success': False,
                'error': 'Invalid response from speech recognition service. Please try again.'
            }
        
        # Check for success
        if response.status_code == 200:
            text = result.get('text', '').strip()
            print(f"✅ Transcription: {text}")
            
            if not text:
                return {
                    'success': False,
                    'error': 'Could not transcribe audio. Please speak clearly and try again.'
                }
            
            return {'success': True, 'text': text}
        
        # Handle other errors
        error_msg = result.get('error', response.text)[:200]
        print(f"❌ HF API Error {response.status_code}: {error_msg}")
        return {
            'success': False,
            'error': f'Speech recognition failed. Please try again.'
        }
            
    except requests.exceptions.Timeout:
        print("⏰ Request timeout")
        return {
            'success': False,
            'error': 'Request timed out. The model may be loading. Please try again in 15 seconds.',
            'retry': True
        }
    except requests.exceptions.ConnectionError:
        print("🌐 Connection error")
        return {
            'success': False,
            'error': 'Could not connect to speech recognition service. Check your internet.'
        }
    except Exception as e:
        error_msg = f"Transcription error: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        print(traceback.format_exc())
        return {
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }


# ============ TEXT-TO-SPEECH ============
async def generate_speech(text: str, voice: str = EDGE_TTS_VOICE) -> bytes:
    """Generate speech using Edge TTS"""
    try:
        print(f"🔊 Generating speech with voice: {voice}")
        output = io.BytesIO()
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                output.write(chunk["data"])
        output.seek(0)
        audio_bytes = output.getvalue()
        print(f"✅ Generated {len(audio_bytes)} bytes of audio")
        return audio_bytes
    except Exception as e:
        print(f"❌ Speech generation error: {str(e)}")
        raise


# ============ AI TEXT GENERATION ============
def generate_ai_response(message: str, chat_session=None) -> str:
    """Generate AI response using Gemini"""
    if not gemini_model:
        return "Sorry, AI service is not configured properly."
    
    try:
        history = []
        if chat_session:
            last_messages = ChatMessage.objects.filter(
                session=chat_session
            ).order_by('-created_at')[:5]
            
            for msg in reversed(list(last_messages)):
                role = "User" if msg.role == "user" else "Assistant"
                history.append(f"{role}: {msg.message}")
        
        context = "\n".join(history) if history else ""
        prompt = f"{VOICE_SYSTEM_INSTRUCTION}\n\n{context}\n\nUser: {message}\n\nRespond briefly:"
        
        response = gemini_model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.7,
                'top_p': 0.8,
                'max_output_tokens': 150,
            }
        )
        
        return response.text.strip()
        
    except Exception as e:
        print(f"❌ Gemini error: {str(e)}")
        return "I'm having trouble responding right now. Please try again."


# ============ MAIN ENDPOINT (FIXED) ============
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def voice_conversation(request):
    """Full voice-to-voice conversation endpoint - FIXED VERSION"""
    try:
        print("=" * 80)
        print("🎤 VOICE CONVERSATION REQUEST")
        print("=" * 80)
        
        session_id = request.data.get('session_id')
        voice_name = request.data.get('voice', EDGE_TTS_VOICE)
        
        print(f"👤 User: {request.user.username}")
        print(f"🎭 Voice: {voice_name}")
        print(f"📋 Session: {session_id or 'NEW'}")
        
        # Get audio data
        audio_bytes = None
        
        if 'audio' in request.FILES:
            audio_file = request.FILES['audio']
            audio_bytes = audio_file.read()
            print(f"📁 Received audio file: {audio_file.name}, size: {len(audio_bytes)} bytes")
        elif 'audio_base64' in request.data:
            audio_base64 = request.data['audio_base64']
            audio_bytes = base64.b64decode(audio_base64)
            print(f"📦 Received base64 audio, size: {len(audio_bytes)} bytes")
        else:
            print("❌ No audio data provided")
            return Response({
                'success': False,
                'error': 'No audio data provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate audio size
        if len(audio_bytes) < 1000:  # Less than 1KB
            print("❌ Audio file too small")
            return Response({
                'success': False,
                'error': 'Audio file is too small. Please speak for longer.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(audio_bytes) > 10 * 1024 * 1024:  # More than 10MB
            print("❌ Audio file too large")
            return Response({
                'success': False,
                'error': 'Audio file too large (max 10MB)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # STEP 1: TRANSCRIBE
        print("\n🔄 STEP 1: Transcribing audio...")
        transcription_result = transcribe_audio_hf(audio_bytes)
        
        if not transcription_result['success']:
            print(f"❌ Transcription failed: {transcription_result['error']}")
            return Response({
                'success': False,
                'error': transcription_result['error'],
                'step': 'transcription',
                'retry': transcription_result.get('retry', False)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        user_message = transcription_result['text']
        print(f"✅ Transcribed: {user_message}")
        
        if not user_message or len(user_message.strip()) < 2:
            print("❌ Transcription too short")
            return Response({
                'success': False,
                'error': 'Could not understand audio. Please speak clearly.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # STEP 2: GET OR CREATE SESSION
        print("\n🔄 STEP 2: Managing session...")
        if session_id:
            try:
                chat_session = ChatSession.objects.get(
                    session_id=session_id,
                    user=request.user
                )
                print(f"✅ Using existing session: {session_id}")
            except ChatSession.DoesNotExist:
                chat_session = ChatSession.objects.create(
                    user=request.user,
                    session_id=session_id
                )
                print(f"✅ Created new session: {session_id}")
        else:
            session_id = str(uuid.uuid4())
            chat_session = ChatSession.objects.create(
                user=request.user,
                session_id=session_id
            )
            print(f"✅ Created new session: {session_id}")
        
        # STEP 3: GENERATE AI RESPONSE
        print("\n🔄 STEP 3: Generating AI response...")
        ai_response_text = generate_ai_response(user_message, chat_session)
        print(f"✅ AI Response: {ai_response_text}")
        
        # STEP 4: SAVE MESSAGES
        print("\n🔄 STEP 4: Saving messages...")
        ChatMessage.objects.create(
            session=chat_session,
            role='user',
            message=user_message
        )
        
        ChatMessage.objects.create(
            session=chat_session,
            role='model',
            message=ai_response_text
        )
        
        chat_session.save()
        print("✅ Messages saved")
        
        # STEP 5: GENERATE SPEECH
        print("\n🔄 STEP 5: Generating speech...")
        try:
            audio_response_bytes = asyncio.run(generate_speech(ai_response_text, voice_name))
            audio_response_base64 = base64.b64encode(audio_response_bytes).decode('utf-8')
            print(f"✅ Speech generated: {len(audio_response_base64)} chars (base64)")
        except Exception as e:
            print(f"⚠️ TTS failed: {str(e)}")
            # Continue without audio
            audio_response_base64 = None
        
        # RETURN RESPONSE
        print("\n" + "=" * 80)
        print("✅ SUCCESS - Returning response")
        print("=" * 80)
        
        return Response({
            'success': True,
            'session_id': session_id,
            'transcription': user_message,
            'ai_response_text': ai_response_text,
            'ai_response_audio_base64': audio_response_base64,
            'audio_format': 'mp3',
            'voice_used': voice_name,
            'message_count': chat_session.messages.count()
        })
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ VOICE CONVERSATION ERROR")
        print("=" * 80)
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return Response({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============ GET VOICES ============
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_voices(request):
    """Return list of available Edge TTS voices"""
    voices = [
        {'name': 'en-US-AriaNeural', 'description': 'Friendly female (US)', 'language': 'English (US)'},
        {'name': 'en-US-GuyNeural', 'description': 'Professional male (US)', 'language': 'English (US)'},
        {'name': 'en-GB-SoniaNeural', 'description': 'British female', 'language': 'English (UK)'},
        {'name': 'en-AU-NatashaNeural', 'description': 'Australian female', 'language': 'English (AU)'},
        {'name': 'en-IN-NeerjaNeural', 'description': 'Indian female', 'language': 'English (IN)'},
    ]
    
    return Response({
        'success': True,
        'voices': voices
    })


# ============ TEST ENDPOINT ============
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def test_transcription(request):
    """Test audio transcription only"""
    try:
        if 'audio' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No audio file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        audio_file = request.FILES['audio']
        audio_bytes = audio_file.read()
        
        print(f"Testing transcription with {len(audio_bytes)} bytes")
        
        result = transcribe_audio_hf(audio_bytes)
        
        return Response(result)
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)