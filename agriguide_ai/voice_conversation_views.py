# agriguide_ai/voice_conversation_views.py
# Full Voice-to-Voice with HF API + Gemini + Edge TTS (100% FREE)

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


# ============ SPEECH-TO-TEXT ============
def transcribe_audio_hf(audio_bytes: bytes) -> dict:
    """Transcribe audio using Hugging Face Inference API"""
    if not HUGGINGFACE_API_KEY:
        return {
            'success': False,
            'error': 'HUGGINGFACE_API_KEY not configured'
        }
    
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    
    try:
        print("🎤 Transcribing audio with Hugging Face Whisper...")
        response = requests.post(
            HF_WHISPER_API,
            headers=headers,
            data=audio_bytes,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get('text', '').strip()
            print(f"✅ Transcription: {text}")
            return {'success': True, 'text': text}
        else:
            error_msg = f"HF API Error {response.status_code}: {response.text}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        error_msg = f"Transcription error: {str(e)}"
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}


# ============ TEXT-TO-SPEECH ============
async def generate_speech(text: str, voice: str = EDGE_TTS_VOICE) -> bytes:
    """Generate speech using Edge TTS"""
    try:
        output = io.BytesIO()
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                output.write(chunk["data"])
        output.seek(0)
        return output.getvalue()
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


# ============ MAIN ENDPOINT ============
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def voice_conversation(request):
    """Full voice-to-voice conversation endpoint"""
    try:
        session_id = request.data.get('session_id')
        voice_name = request.data.get('voice', EDGE_TTS_VOICE)
        
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
            return Response({
                'success': False,
                'error': 'No audio data provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate audio size
        if len(audio_bytes) > 10 * 1024 * 1024:
            return Response({
                'success': False,
                'error': 'Audio file too large (max 10MB)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # STEP 1: TRANSCRIBE
        transcription_result = transcribe_audio_hf(audio_bytes)
        
        if not transcription_result['success']:
            return Response({
                'success': False,
                'error': transcription_result['error'],
                'step': 'transcription'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        user_message = transcription_result['text']
        
        if not user_message:
            return Response({
                'success': False,
                'error': 'Could not transcribe audio. Please speak clearly.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # STEP 2: GET OR CREATE SESSION
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
        
        # STEP 3: GENERATE AI RESPONSE
        ai_response_text = generate_ai_response(user_message, chat_session)
        
        # STEP 4: SAVE MESSAGES
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
        
        # STEP 5: GENERATE SPEECH
        try:
            audio_response_bytes = asyncio.run(generate_speech(ai_response_text, voice_name))
            audio_response_base64 = base64.b64encode(audio_response_bytes).decode('utf-8')
        except Exception as e:
            print(f"⚠️ TTS failed: {str(e)}")
            audio_response_base64 = None
        
        # RETURN RESPONSE
        return Response({
            'success': True,
            'session_id': session_id,
            'transcription': user_message,
            'ai_response_text': ai_response_text,
            'ai_response_audio_base64': audio_response_base64,
            'audio_format': 'wav',
            'voice_used': voice_name,
            'message_count': chat_session.messages.count()
        })
        
    except Exception as e:
        print(f"❌ Voice conversation error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============ GET VOICES ============
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_voices(request):
    """Return list of available Edge TTS voices"""
    voices = [
        {'name': 'en-US-AriaNeural', 'description': 'Friendly female', 'language': 'English (US)'},
        {'name': 'en-US-GuyNeural', 'description': 'Professional male', 'language': 'English (US)'},
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
        
        result = transcribe_audio_hf(audio_bytes)
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)