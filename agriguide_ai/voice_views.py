# voice_views.py - Voice chat with Gemini TTS
import os
import uuid
import struct
import mimetypes
from django.http import FileResponse, JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# Try to import the newer `google.genai` package first; if it's not
# available (for example the environment only has `google-generativeai`),
# fall back to `google.generativeai` and provide a small compatibility
# shim so the rest of the code can continue to call
# `client.models.generate_content_stream(...)`.
try:
    import google.genai as genai
    from google.genai import types
    _GENAI_IMPL = "genai"
except Exception:
    import google.generativeai as genai
    from google.generativeai import types
    _GENAI_IMPL = "generativeai"
from .models import ChatSession, ChatMessage
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import tempfile

# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Initialize client depending on which package is available.
if _GENAI_IMPL == "genai":
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    # google-generativeai uses a different top-level API. Configure it
    # and provide a tiny shim so existing calls to
    # `client.models.generate_content_stream(...)` will work.
    genai.configure(api_key=GEMINI_API_KEY)

    class _ModelsShim:
        def __init__(self, genai_module):
            self._genai = genai_module

        def generate_content_stream(self, model, contents=None, config=None, **kwargs):
            # Map the older config object (if any) to the newer generation_config
            gen_config = None
            try:
                if config is not None:
                    # Attempt to extract a few common fields
                    gen_config = {}
                    if hasattr(config, 'temperature'):
                        gen_config['temperature'] = getattr(config, 'temperature')
                    if hasattr(config, 'max_output_tokens'):
                        gen_config['max_output_tokens'] = getattr(config, 'max_output_tokens')
                    if hasattr(config, 'candidate_count'):
                        gen_config['candidate_count'] = getattr(config, 'candidate_count')
            except Exception:
                gen_config = None

            gen_model = self._genai.GenerativeModel(model)
            # The generativeai API uses `generation_config` and `stream=True`.
            response = gen_model.generate_content(contents or [], generation_config=gen_config, stream=True, **kwargs)
            for chunk in response:
                yield chunk

    client = type("ClientShim", (), {"models": _ModelsShim(genai)})()

# System instruction for voice chat
VOICE_SYSTEM_INSTRUCTION = """
You are AgriGuide AI, a friendly agricultural advisor. Keep responses concise and conversational for voice chat.
- Use short sentences suitable for speech
- Avoid complex formatting or bullet points
- Keep responses under 3-4 sentences when possible for quick voice interaction
- Be warm and encouraging
- Use simple, clear language
"""


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Convert audio data to WAV format with proper headers"""
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size
    )
    return header + audio_data


def parse_audio_mime_type(mime_type: str) -> dict:
    """Parse bits per sample and rate from audio MIME type"""
    bits_per_sample = 16
    rate = 24000

    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass

    return {"bits_per_sample": bits_per_sample, "rate": rate}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_chat(request):
    """
    Voice chat endpoint - Returns audio response
    Expected JSON: {
        "message": "user text message",
        "session_id": "optional_session_id",
        "voice": "Zephyr" (optional, default: "Zephyr")
    }
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        voice_name = request.data.get('voice', 'Zephyr')  # Zephyr, Puck, Charon, Kore, Fenrir, Aoede
        
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
        
        # Get conversation history (last 5 messages). Django QuerySets
        # do not support negative indexing (e.g. `qs[-5:]`). Use a
        # descending slice to fetch the most recent items and reverse
        # them to restore chronological order.
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
        
        # Configure TTS generation
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]
        
        generate_config = types.GenerateContentConfig(
            temperature=0.7,
            response_modalities=["TEXT", "AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            )
        )
        
        # Generate response with audio
        audio_chunks = []
        text_response = ""
        
        for chunk in client.models.generate_content_stream(
            model="gemini-2.0-flash-exp",
            contents=contents,
            config=generate_config
        ):
            if chunk.candidates and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                
                # Collect text
                if hasattr(part, 'text') and part.text:
                    text_response += part.text
                
                # Collect audio
                if part.inline_data and part.inline_data.data:
                    audio_chunks.append(part.inline_data.data)
        
        if not text_response:
            return Response({
                'error': 'No response generated'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
        
        # Combine audio chunks
        if audio_chunks:
            combined_audio = b''.join(audio_chunks)
            
            # Convert to WAV if needed
            mime_type = "audio/L16;rate=24000"
            wav_data = convert_to_wav(combined_audio, mime_type)
            
            # Save audio file temporarily or to S3
            audio_filename = f"voice_response_{uuid.uuid4()}.wav"
            
            # Option 1: Save to temporary file and return
            temp_dir = tempfile.gettempdir()
            audio_path = os.path.join(temp_dir, audio_filename)
            
            with open(audio_path, 'wb') as f:
                f.write(wav_data)
            
            # Return JSON response with audio file info
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_url': f'/api/voice/audio/{audio_filename}',
                'voice_used': voice_name
            })
        else:
            # No audio generated, return text only
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_url': None,
                'voice_used': voice_name
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
    Streaming voice chat - Returns audio in base64 chunks
    Better for real-time responses
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        voice_name = request.data.get('voice', 'Zephyr')
        
        if not message:
            return Response({
                'error': 'Message is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create session (same as above)
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
        
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]
        
        generate_config = types.GenerateContentConfig(
            temperature=0.7,
            response_modalities=["TEXT", "AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            )
        )
        
        # Generate and collect
        audio_chunks = []
        text_response = ""
        
        for chunk in client.models.generate_content_stream(
            model="gemini-2.0-flash-exp",
            contents=contents,
            config=generate_config
        ):
            if chunk.candidates and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                
                if hasattr(part, 'text') and part.text:
                    text_response += part.text
                
                if part.inline_data and part.inline_data.data:
                    audio_chunks.append(part.inline_data.data)
        
        # Save to database
        ChatMessage.objects.create(session=chat_session, role='user', message=message)
        ChatMessage.objects.create(session=chat_session, role='model', message=text_response)
        chat_session.save()
        
        # Convert audio to WAV
        if audio_chunks:
            import base64
            combined_audio = b''.join(audio_chunks)
            wav_data = convert_to_wav(combined_audio, "audio/L16;rate=24000")
            audio_base64 = base64.b64encode(wav_data).decode('utf-8')
            
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_base64': audio_base64,
                'audio_format': 'wav',
                'voice_used': voice_name
            })
        else:
            return Response({
                'session_id': session_id,
                'text_response': text_response,
                'audio_base64': None,
                'voice_used': voice_name
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
    """Return list of available voice options"""
    voices = [
        {'name': 'Zephyr', 'description': 'Warm and friendly', 'gender': 'neutral'},
        {'name': 'Puck', 'description': 'Energetic and bright', 'gender': 'neutral'},
        {'name': 'Charon', 'description': 'Deep and authoritative', 'gender': 'neutral'},
        {'name': 'Kore', 'description': 'Gentle and calm', 'gender': 'neutral'},
        {'name': 'Fenrir', 'description': 'Strong and clear', 'gender': 'neutral'},
        {'name': 'Aoede', 'description': 'Melodic and soothing', 'gender': 'neutral'},
    ]
    
    return Response({'voices': voices})