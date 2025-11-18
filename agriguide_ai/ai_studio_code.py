# To run this code you need to install the following dependencies:
# pip install requests edge-tts

import base64
import mimetypes
import os
import re
import struct
import requests
import asyncio
import edge_tts
import io

EDGE_TTS_VOICE = "en-US-AriaNeural"

# Optional: Use local Ollama for text generation
OLLAMA_API_URL = os.environ.get('OLLAMA_API_URL', 'http://localhost:11434/api/generate')
USE_OLLAMA = os.environ.get('USE_OLLAMA', 'false').lower() == 'true'


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")


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


def generate_text_simple(prompt: str) -> str:
    """Generate agriculture-focused text (no API key needed)"""
    if USE_OLLAMA:
        try:
            payload = {"model": "mistral", "prompt": prompt, "stream": False, "temperature": 0.7}
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "").strip()
                if text:
                    return text
        except Exception as e:
            print(f"Ollama not available: {str(e)}")
    
    # Fallback responses
    prompt_lower = prompt.lower()
    agriculture_responses = {
        "pest": "To control pests effectively, use integrated pest management (IPM). This includes crop rotation, beneficial insects, and targeted pesticide use.",
        "crop": "For better crop yields, ensure proper soil preparation, adequate water, and crop rotation.",
        "weather": "Check local weather forecasts and plan irrigation accordingly.",
        "soil": "Healthy soil is crucial. Test regularly and add compost or organic matter.",
        "fertilizer": "Use fertilizers based on soil test results.",
        "watering": "Water early morning or evening. Deep but infrequent watering encourages strong root growth.",
        "disease": "Plant diseases spread quickly. Use disease-resistant varieties and maintain good airflow.",
        "harvest": "Harvest at the right time for best quality.",
    }
    
    for keyword, response_text in agriculture_responses.items():
        if keyword in prompt_lower:
            return response_text
    
    return "Hello! I'm AgriGuide AI. I can help with pest management, crops, soil health, irrigation, and more. What would you like to know?"


def generate():
    """Generate agricultural advice with text-to-speech"""
    prompt = """Read aloud in a warm, welcoming tone. 
You are AgriGuide AI, a friendly agricultural advisor. 
Provide helpful tips about farming, pest control, crop management, or weather updates."""

    # Generate text response
    text_response = generate_text_simple(prompt)
    print(f"Generated text: {text_response}\n")
    
    # Generate speech
    audio_data = asyncio.run(generate_speech(text_response, "en-US-AriaNeural"))
    
    # Save audio file
    save_binary_file("agriguide_response.wav", audio_data)
    print(f"Audio saved successfully!")


if __name__ == "__main__":
    generate()


