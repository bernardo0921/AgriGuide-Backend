# microsoft_email_utils.py - Microsoft Graph API Email Implementation

import httpx
from datetime import datetime, timedelta
from django.conf import settings
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class MicrosoftGraphEmailClient:
    """
    Microsoft Graph API client for sending emails via Microsoft 365.
    Replaces Gmail SMTP for authentication emails.
    """
    
    BASE_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self):
        self.tenant_id = getattr(settings, 'MICROSOFT_TENANT_ID', '')
        self.client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'MICROSOFT_CLIENT_SECRET', '')
        self.default_sender = getattr(settings, 'MICROSOFT_DEFAULT_SENDER', 'info@ideationaxis.com')
        self.app_name = getattr(settings, 'APP_NAME', 'AgriGuide')
        
        self._access_token = None
        self._token_expiry = None
        
        # Validate configuration
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            logger.warning("⚠️ Microsoft Graph credentials not configured")
    
    async def _get_access_token(self, force_refresh: bool = False) -> str:
        """Get Microsoft Graph API access token."""
        if not force_refresh and self._access_token and self._token_expiry:
            if datetime.utcnow() < self._token_expiry - timedelta(minutes=5):
                return self._access_token
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to get MS Graph token: {response.text}")
                raise Exception(f"Failed to get access token: {response.text}")
            
            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            
            logger.info(f"✅ MS Graph token obtained, expires in {expires_in}s")
            return self._access_token
    
    async def clear_token_cache(self):
        """Force clear token cache."""
        self._access_token = None
        self._token_expiry = None
        logger.info("🔄 MS Graph token cache cleared")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        retry_with_refresh: bool = True
    ) -> bool:
        """
        Send email via Microsoft Graph API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            retry_with_refresh: Retry once with fresh token on 403
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            token = await self._get_access_token()
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Build message
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body_html
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": to_email}}
                    ]
                },
                "saveToSentItems": "true"
            }
            
            # Send email using the default authorized sender
            url = f"{self.BASE_URL}/users/{self.default_sender}/sendMail"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=message,
                    timeout=30.0
                )
                
                # Handle 403 with token refresh
                if response.status_code == 403 and retry_with_refresh:
                    logger.warning("⚠️ Email send got 403, refreshing token...")
                    await self.clear_token_cache()
                    return await self.send_email(
                        to_email, subject, body_html, retry_with_refresh=False
                    )
                
                if response.status_code not in [200, 202]:
                    error_detail = response.text
                    logger.error(f"❌ Failed to send email: {response.status_code} - {error_detail}")
                    
                    if response.status_code == 403:
                        logger.error(
                            "Access denied. Ensure: "
                            "1) App has 'Mail.Send' permission with admin consent. "
                            f"2) Sender mailbox '{self.default_sender}' exists in M365 tenant."
                        )
                    return False
                
                logger.info(f"✅ Email sent to {to_email}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Email send exception: {str(e)}", exc_info=True)
            return False


# Singleton instance
_graph_client = None


def get_graph_client() -> MicrosoftGraphEmailClient:
    """Get or create the Microsoft Graph client singleton."""
    global _graph_client
    if _graph_client is None:
        _graph_client = MicrosoftGraphEmailClient()
    return _graph_client


# Synchronous wrapper functions for Django views
import asyncio


def send_verification_email(recipient_email: str, code: str, purpose: str = "verification") -> bool:
    """
    Send verification email using Microsoft Graph API.
    Synchronous wrapper for async function.
    
    Args:
        recipient_email: Recipient's email address
        code: 6-digit verification code
        purpose: Purpose of verification (registration, login, password_reset)
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    client = get_graph_client()
    
    purpose_text = {
        'registration': 'complete your registration',
        'login': 'sign in to your account',
        'password_reset': 'reset your password'
    }
    
    action_text = purpose_text.get(purpose, 'verify your email')
    subject = f"Your {client.app_name} Verification Code"
    
    # HTML email body
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #ddd;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                color: #4CAF50;
            }}
            .code-box {{
                background-color: #4CAF50;
                color: white;
                padding: 20px;
                text-align: center;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 5px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .warning {{
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 5px;
                padding: 15px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Verification Code</h1>
            </div>
            
            <p>Hello,</p>
            
            <p>Your verification code to {action_text} is:</p>
            
            <div class="code-box">{code}</div>
            
            <p>This code expires in <strong>5 minutes</strong>.</p>
            
            <div class="warning">
                <strong>🔒 Security Notice:</strong> Never share this code with anyone. 
                Our team will never ask for your verification code.
            </div>
            
            <p>If you didn't request this code, please ignore this email.</p>
            
            <div class="footer">
                <p>Best regards,<br>The {client.app_name} Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            client.send_email(recipient_email, subject, html_body)
        )
        loop.close()
        
        if result:
            logger.info(f"✅ Verification email sent to {recipient_email}")
        else:
            logger.error(f"❌ Failed to send verification email to {recipient_email}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Exception sending verification email: {str(e)}", exc_info=True)
        return False


def send_welcome_email(recipient_email: str, username: str) -> bool:
    """
    Send welcome email after successful registration.
    Synchronous wrapper for async function.
    
    Args:
        recipient_email: Recipient's email address
        username: User's username
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    client = get_graph_client()
    
    subject = f"Welcome to {client.app_name}! 🎉"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #ddd;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                color: #4CAF50;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #4CAF50;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
                text-align: center;
            }}
            .features {{
                background-color: white;
                border-radius: 5px;
                padding: 20px;
                margin: 20px 0;
            }}
            .feature-item {{
                margin: 10px 0;
                padding-left: 25px;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Welcome to {client.app_name}!</h1>
            </div>
            
            <p>Hi {username},</p>
            
            <p>Thank you for registering with {client.app_name}! Your account has been successfully created, and we're excited to have you join our community.</p>
            
            <div class="features">
                <h3>What's Next?</h3>
                <div class="feature-item">✅ Complete your profile</div>
                <div class="feature-item">🌾 Connect with other farmers</div>
                <div class="feature-item">📚 Access educational resources</div>
                <div class="feature-item">💬 Get AI-powered farming tips</div>
            </div>
            
            <p>You can now log in and start exploring all the features we offer.</p>
            
            <p>If you have any questions or need assistance, feel free to contact our support team.</p>
            
            <div class="footer">
                <p>Best regards,<br>The {client.app_name} Team</p>
                <p style="font-size: 12px; color: #999;">
                    This email was sent to {recipient_email} because you created an account on {client.app_name}.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            client.send_email(recipient_email, subject, html_body)
        )
        loop.close()
        
        if result:
            logger.info(f"✅ Welcome email sent to {recipient_email}")
        else:
            logger.error(f"❌ Failed to send welcome email to {recipient_email}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Exception sending welcome email: {str(e)}", exc_info=True)
        return False