# views.py (Updated with Image Analysis)
import google.generativeai as genai
from django.http import JsonResponse
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

# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Initialize Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Set up models - one for text, one for vision
text_model = genai.GenerativeModel('gemini-2.0-flash-exp')
vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')

# System instructions
SYSTEM_INSTRUCTION = """
You are **AgriGuide AI**, an expert agricultural advisor specializing in farming practices, crop management, pest control, soil health, irrigation, and sustainable agriculture. You provide personalized, context-aware advice to farmers and agricultural enthusiasts.

## Core Identity
- **Name**: AgriGuide AI
- **Expertise**: Agriculture, farming, horticulture, agronomy, livestock management, sustainable farming
- **Tone**: Friendly, professional, encouraging, and supportive
- **Communication Style**: Clear, practical, and actionable advice with specific steps when possible

## Memory Simulation Instructions

To simulate memory across conversations:

1. **Extract and Reference Context**: When users mention previous topics in the conversation history, acknowledge and reference them naturally.
   - Example: "Based on what you mentioned earlier about your tomato plants..."

2. **Build Upon Previous Advice**: If the user returns with updates, acknowledge the progression and build upon previous recommendations.

3. **Maintain Consistency**: Keep track of details mentioned such as:
   - Crop types and growth stages
   - Farm location and climate
   - Soil conditions
   - Previous problems or challenges
   - Farming methods (organic, conventional, etc.)

4. **Personalize Responses**: Use information from previous messages to personalize advice.

5. **Ask Clarifying Questions**: When important context is missing, ask specific questions.

## Response Guidelines

### Formatting for Better Readability
- Use **bold** for important terms and key points
- Use bullet points (•) for lists of items
- Use numbered lists for sequential steps
- Use headers (##) for major sections in long responses
- Use `inline code` for technical terms, measurements, or chemical names

### Response Structure
1. **Acknowledge the Query**: Show you understand the question/problem
2. **Provide Context**: Brief explanation of why this matters
3. **Give Actionable Advice**: Step-by-step instructions when applicable
4. **Add Preventive Tips**: Help avoid future issues
5. **Follow-up**: Encourage users to update you on progress

## Important Constraints
1. **Safety First**: Always prioritize safe handling of chemicals, machinery, and livestock
2. **Recommend Professional Help**: For serious diseases or large-scale problems, suggest consulting local agricultural extension services
3. **Realistic Expectations**: Be honest about challenges and realistic timelines
4. **Cost Awareness**: Consider budget constraints when recommending solutions

## Conversational Memory Phrases
Use these patterns to create the illusion of memory:
- "Following up on your [previous topic]..."
- "Since you mentioned you're growing [crop]..."
- "Based on your earlier description of [situation]..."
- "How did [previous recommendation] work out?"

Remember: You are a trusted farming companion helping users succeed in their agricultural endeavors. Be helpful, be specific, and build rapport through contextual awareness!
"""

VISION_SYSTEM_INSTRUCTION = """
You are **AgriGuide AI Vision Expert**, specializing in crop identification and disease detection from images.

## Your Capabilities
1. **Crop Identification**: Identify crops from images with confidence levels
2. **Disease Detection**: Analyze plants for signs of disease, pests, or nutrient deficiencies
3. **Health Assessment**: Evaluate overall plant health
4. **Actionable Advice**: Provide specific treatment recommendations

## Response Format

When analyzing an image, structure your response as follows:

### 🌱 Crop Identification
- **Crop Name**: [Specific crop name]
- **Confidence**: [High/Medium/Low]
- **Growth Stage**: [Seedling/Vegetative/Flowering/Fruiting/Mature]

### 🔍 Health Assessment
- **Overall Health**: [Healthy/Concerning/Critical]
- **Disease Detected**: [Yes/No]

### ⚠️ Findings
[Detailed description of what you observe]

### 💊 Recommendations
[Specific, actionable steps to address any issues]

### 📋 Additional Information
[Relevant facts about the crop, growing conditions, harvest time, etc.]

## Guidelines
- Be specific but concise
- Prioritize safety in all recommendations
- If uncertain, say so and suggest consulting local agricultural experts
- Always provide preventive care tips
- Consider organic and chemical treatment options
"""


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_ai(request):
    """
    Endpoint to chat with AgriGuide AI (supports text and images)
    Supports both form-data (with image) and JSON (text only)
    """
    try:
        # Check if request has files (multipart/form-data)
        has_image = 'image' in request.FILES
        
        if has_image:
            # Handle multipart form data
            message = request.data.get('message', '').strip()
            session_id = request.data.get('session_id')
            image_file = request.FILES['image']
        else:
            # Handle JSON data
            message = request.data.get('message', '').strip()
            session_id = request.data.get('session_id')
            image_file = None
        
        if not message and not has_image:
            return Response({
                'error': 'Message or image is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create chat session
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
                print(f"✅ Created new session with provided ID: {session_id}")
        else:
            session_id = str(uuid.uuid4())
            chat_session = ChatSession.objects.create(
                user=request.user,
                session_id=session_id
            )
            print(f"✅ Created new session with UUID: {session_id}")
        
        # Save user message with optional image
        user_message = ChatMessage.objects.create(
            session=chat_session,
            role='user',
            message=message or "Please analyze this image",
            image=image_file if has_image else None
        )
        
        # Process image if present
        if has_image:
            print(f"🖼️ Processing image: {image_file.name}")
            
            # Load image for Gemini
            img = Image.open(image_file)
            
            # Prepare prompt for vision analysis
            if message:
                vision_prompt = f"{VISION_SYSTEM_INSTRUCTION}\n\nUser's question: {message}\n\nPlease analyze the image and provide detailed information."
            else:
                vision_prompt = f"{VISION_SYSTEM_INSTRUCTION}\n\nPlease analyze this crop image and provide detailed information about the crop, its health, and any diseases or issues you can identify."
            
            # Generate response with image
            response = vision_model.generate_content(
                [vision_prompt, img],
                generation_config={
                    'temperature': 0.4,  # Lower temperature for more factual responses
                    'top_p': 0.8,
                    'top_k': 40
                }
            )
            
            ai_response = response.text
            
        else:
            # Text-only conversation
            # Get conversation history
            all_messages = ChatMessage.objects.filter(
                session=chat_session
            ).order_by('created_at')
            
            # Exclude the message we just saved (keep all but the latest)
            history_messages = all_messages[:all_messages.count()-1] if all_messages.count() > 1 else []
            
            print(f"📚 Loading {len(history_messages)} messages from history")
            
            # Build conversation contents
            contents = []
            
            # Add history (only text messages)
            for msg in history_messages:
                if not msg.image:  # Skip messages with images in history for now
                    contents.append({
                        'role': msg.role,
                        'parts': [{'text': msg.message}]
                    })
            
            # Start chat with history
            chat = text_model.start_chat(history=[])
            
            # Add system instruction
            chat.send_message(SYSTEM_INSTRUCTION)
            
            # Send the actual message and get response
            response = chat.send_message(message, generation_config={
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40
            })
            
            ai_response = response.text
        
        # Save AI response
        ChatMessage.objects.create(
            session=chat_session,
            role='model',
            message=ai_response
        )
        
        # Update session timestamp
        chat_session.save()
        
        print(f"✅ Response saved to session {session_id}")
        print(f"📊 Session now has {chat_session.messages.count()} messages")
        
        return Response({
            'response': ai_response,
            'session_id': session_id,
            'image_url': user_message.image_url if has_image else None
        })
        
    except Exception as e:
        print(f"❌ Error in chat_with_ai: {str(e)}")
        import traceback
        print(traceback.format_exc())
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
    
    print(f"📋 Returning {len(sessions_data)} sessions for user {request.user.username}")
    
    return Response({'sessions': sessions_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request, session_id):
    """Get chat history for a specific session (includes images)"""
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
        
        print(f"📖 Returning {len(history)} messages for session {session_id}")
        
        return Response({
            'session_id': session_id,
            'history': history
        })
        
    except ChatSession.DoesNotExist:
        return Response({
            'error': 'Session not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)


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