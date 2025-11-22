# agriguide_ai/ai_tip_views.py
import google.generativeai as genai
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from datetime import datetime, timedelta
import os
import logging
import random

# Import prompts from separate file
from .prompts import (
    get_tip_instruction,
    DEFAULT_FALLBACK_TIPS,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES
)

logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')


def validate_language(language: str) -> str:
    """Validate and return the language, defaulting if invalid"""
    if not language:
        return DEFAULT_LANGUAGE
    lang = language.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE
    return lang


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_daily_farming_tip(request):
    """
    Get daily farming tip from Gemini AI
    Tips are cached for 48 hours per language
    Supports language parameter: ?language=english or ?language=sesotho
    """
    print("=" * 80)
    print("🌾 FARMING TIP REQUEST RECEIVED")
    print("=" * 80)
    
    try:
        # Get and validate language parameter
        language = validate_language(request.GET.get('language'))
        
        # Generate cache key based on current date AND language
        today = datetime.now().date()
        cache_key = f'farming_tip_{today}_{language}'
        
        print(f"📅 Today's date: {today}")
        print(f"🌍 Language: {language}")
        print(f"🔑 Cache key: {cache_key}")
        
        # Try to get cached tip
        cached_tip = cache.get(cache_key)
        
        if cached_tip:
            print(f"✅ CACHED TIP FOUND for {today} in {language}")
            print(f"📝 Cached tip: {cached_tip[:100]}...")
            logger.info(f"Returning cached tip for {today} in {language}")
            return Response({
                'tip': cached_tip,
                'cached': True,
                'language': language,
                'date': today.isoformat()
            })
        
        print(f"❌ No cached tip found. Generating new tip in {language}...")
        
        # Check if API key is configured
        if not GEMINI_API_KEY:
            print("🚨 ERROR: GEMINI_API_KEY is not set!")
            raise ValueError("GEMINI_API_KEY not configured")
        
        print(f"🔑 API Key present: {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-5:]}")
        
        # Get language-specific tip instruction
        tip_prompt = get_tip_instruction(language)
        
        # Generate new tip using Gemini
        print(f"🤖 Calling Gemini API for {language} tip...")
        logger.info(f"Generating new tip for {today} in {language}")
        
        response = model.generate_content(
            tip_prompt,
            generation_config={
                'temperature': 0.8,
                'top_p': 0.9,
                'max_output_tokens': 150,
            }
        )
        
        print(f"✅ Gemini API response received")
        print(f"📊 Response type: {type(response)}")
        
        tip = response.text.strip()
        
        print(f"✅ Generated tip: {tip}")
        print(f"📏 Tip length: {len(tip)} characters")
        
        # Cache the tip for 48 hours
        cache.set(cache_key, tip, timeout=60 * 60 * 48)
        print(f"💾 Tip cached for 48 hours with key: {cache_key}")
        
        logger.info(f"Successfully generated and cached new tip in {language}")
        
        print("=" * 80)
        print("✅ SUCCESS - Returning AI-generated tip")
        print("=" * 80)
        
        return Response({
            'tip': tip,
            'cached': False,
            'language': language,
            'date': today.isoformat()
        })
        
    except Exception as e:
        print("=" * 80)
        print("🚨 ERROR OCCURRED")
        print("=" * 80)
        print(f"❌ Error type: {type(e).__name__}")
        print(f"❌ Error message: {str(e)}")
        
        import traceback
        print(f"📋 Full traceback:")
        print(traceback.format_exc())
        
        logger.error(f"Error generating farming tip: {str(e)}")
        
        # Try to get yesterday's tip as fallback (same language)
        yesterday = (datetime.now() - timedelta(days=1)).date()
        yesterday_cache_key = f'farming_tip_{yesterday}_{language}'
        yesterday_tip = cache.get(yesterday_cache_key)
        
        print(f"🔍 Checking for yesterday's tip ({yesterday}) in {language}...")
        
        if yesterday_tip:
            print(f"✅ Found yesterday's tip as fallback")
            print(f"📝 Yesterday's tip: {yesterday_tip[:100]}...")
            logger.info(f"Returning yesterday's tip as fallback in {language}")
            return Response({
                'tip': yesterday_tip,
                'cached': True,
                'fallback': True,
                'language': language,
                'date': yesterday.isoformat()
            })
        
        print(f"❌ No yesterday's tip found in {language}")
        
        # Return random default tip for the specified language
        fallback_tips = DEFAULT_FALLBACK_TIPS.get(language, DEFAULT_FALLBACK_TIPS['english'])
        fallback_tip = random.choice(fallback_tips)
        
        print(f"🔄 Using default fallback tip in {language}")
        print(f"📝 Fallback tip: {fallback_tip[:100]}...")
        logger.info(f"Returning default fallback tip in {language}")
        
        print("=" * 80)
        print("⚠️ FALLBACK - Returning default tip")
        print("=" * 80)
        
        return Response({
            'tip': fallback_tip,
            'cached': False,
            'fallback': True,
            'language': language,
            'date': datetime.now().date().isoformat()
        })