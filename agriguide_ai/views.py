# views.py (Updated with Image Analysis)
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


# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Initialize Gemini API
genai.configure(api_key=GEMINI_API_KEY, transport='rest')

# Set up models - one for text, one for vision with extended timeout
text_model = genai.GenerativeModel('gemini-2.5-flash')
vision_model = genai.GenerativeModel('gemini-2.5-flash')

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
    Streaming endpoint for real-time typing animation
    Returns chunks of text as they're generated
    """
    try:
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        
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
        
        # Generator function for streaming
        def generate_response():
            try:
                # Get conversation history
                history_messages = ChatMessage.objects.filter(
                    session=chat_session
                ).exclude(id=user_message.id).order_by('created_at')
                
                # Start chat with history
                chat = text_model.start_chat(history=[])
                chat.send_message(SYSTEM_INSTRUCTION)
                
                # Generate streaming response
                response = chat.send_message(
                    message,
                    generation_config={
                        'temperature': 0.7,
                        'top_p': 0.8,
                        'top_k': 40,
                        'max_output_tokens': 1024
                    },
                    stream=True  # Enable streaming
                )
                
                full_response = ""
                
                # Send session_id first
                yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
                
                # Stream chunks
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                        # Send each chunk as JSON
                        yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
                
                # Save complete response to database
                ChatMessage.objects.create(
                    session=chat_session,
                    role='model',
                    message=full_response
                )
                
                # Update session timestamp
                chat_session.save()
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'done', 'full_text': full_response})}\n\n"
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
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
    Standard endpoint (non-streaming) for image analysis
    Use this for image uploads, use chat_with_ai_stream for text
    """
    try:
        has_image = 'image' in request.FILES
        
        if has_image:
            message = request.data.get('message', '').strip()
            session_id = request.data.get('session_id')
            image_file = request.FILES['image']
        else:
            # Redirect to streaming endpoint for text-only
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
        
        # Generate vision response
        vision_prompt = f"{VISION_SYSTEM_INSTRUCTION}\n\n"
        if message:
            vision_prompt += f"User's question: {message}\n\n"
        vision_prompt += "Please analyze the image and provide detailed information."
        
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
        
        return Response({
            'response': ai_response,
            'session_id': session_id,
            'image_url': user_message.image_url
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Keep other endpoints (get_chat_sessions, get_chat_history, etc.) unchanged
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


# views.py (add to the bottom)
# In views.py, add these standard Django imports
from django.shortcuts import render 
from django.http import HttpResponse 
from django.views.decorators.csrf import csrf_exempt 

# Add the new form import
from .forms import TemporalSuperuserCreationForm 
# Note: 'os' and 'User' from models should already be imported in your file.
# The same 'os' is already imported at the top of your views.py snippet
# TEMPORAL_SUPERUSER_SECRET is the key that *must* match the value you set in Render.
TEMPORAL_SUPERUSER_SECRET = os.environ.get('SUPERUSER_CREATION_KEY', 'REMOVE_ME_AFTER_USE')


@csrf_exempt
def create_superuser_temporal(request):
    """
    TEMPORARY view to create a superuser via a web form.
    MUST BE REMOVED IMMEDIATELY AFTER USE.
    """
    if request.method == 'POST':
        form = TemporalSuperuserCreationForm(request.POST)
        if form.is_valid():
            
            # 1. SECRET KEY CHECK
            secret_key = form.cleaned_data['secret_key']
            if secret_key != TEMPORAL_SUPERUSER_SECRET or TEMPORAL_SUPERUSER_SECRET == 'REMOVE_ME_AFTER_USE':
                return HttpResponse("Error: Invalid or unset Temporal Secret Key.", status=403)
            
            # 2. CREATE SUPERUSER
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            password = form.cleaned_data['password']
            
            try:
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    phone_number=phone_number, # Required by your custom model
                    password=password,
                )
                
                # Success message
                return HttpResponse(
                    f"Superuser '{username}' created successfully! **REMOVE THIS ENDPOINT NOW!**", 
                    status=201
                )

            except Exception as e:
                # Catch errors like duplicate username or phone number
                return HttpResponse(f"Error creating superuser: {e}", status=400)
        
        # Form validation failure
        return HttpResponse(
            f"Invalid form data: {form.errors.as_text()}", 
            status=400
        )
    
    # Handle GET request: Show the HTML form
    else:
        form = TemporalSuperuserCreationForm()
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Create Superuser</title></head>
        <body>
            <h1>Temporal Superuser Creation Form</h1>
            <p style="color: red; border: 1px solid red; padding: 10px;">
                <strong>WARNING:</strong> This endpoint is a major security risk and 
                <strong>MUST BE REMOVED IMMEDIATELY</strong> after creating your superuser.
            </p>
            <form method="post" style="max-width: 400px; margin-top: 20px;">
                {form.as_p()}
                <button type="submit" style="padding: 10px; background-color: #4CAF50; color: white; border: none; cursor: pointer;">
                    Create Superuser
                </button>
            </form>
            <p><strong>Setup required:</strong> You must set an environment variable 
               <code>SUPERUSER_CREATION_KEY</code> in your Render environment 
               and enter that exact value in the form's secret key field.</p>
        </body>
        </html>
        """
        return HttpResponse(html)