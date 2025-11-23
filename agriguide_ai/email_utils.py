# email_utils.py - Create this file in your app directory

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_verification_email(recipient_email, code, purpose="verification"):
    """
    Send a 2FA verification code email
    
    Args:
        recipient_email: Email address to send to
        code: 6-digit verification code
        purpose: Purpose of verification (registration, login, etc.)
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    
    # Get email settings from Django settings
    sender_email = getattr(settings, 'EMAIL_HOST_USER', '')
    sender_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
    app_name = getattr(settings, 'APP_NAME', 'AgriConnect')
    
    if not sender_email or not sender_password:
        logger.error("Email credentials not configured in settings")
        return False
    
    # Customize message based on purpose
    purpose_text = {
        'registration': 'complete your registration',
        'login': 'sign in to your account',
        'password_reset': 'reset your password'
    }
    
    action_text = purpose_text.get(purpose, 'verify your email')
    
    # Create HTML email body
    html_body = f"""
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
                }}
                .code-box {{
                    background-color: #ffffff;
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                    margin: 30px 0;
                }}
                .code {{
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 5px;
                    color: #4CAF50;
                    font-family: 'Courier New', monospace;
                }}
                .warning {{
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #777;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="color: #4CAF50; margin: 0;">🔐 Verification Code</h1>
                </div>
                
                <p>Hello,</p>
                
                <p>You requested a verification code to {action_text} on <strong>{app_name}</strong>.</p>
                
                <div class="code-box">
                    <p style="margin: 0; font-size: 14px; color: #666;">Your verification code is:</p>
                    <div class="code">{code}</div>
                    <p style="margin: 10px 0 0 0; font-size: 12px; color: #999;">This code expires in 5 minutes</p>
                </div>
                
                <p>Enter this code in the verification page to {action_text}.</p>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong> Never share this code with anyone. {app_name} will never ask for this code via phone or email.
                </div>
                
                <p>If you didn't request this code, please ignore this email or contact support if you're concerned about your account security.</p>
                
                <div class="footer">
                    <p>This is an automated message, please do not reply to this email.</p>
                    <p>&copy; 2024 {app_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
    </html>
    """
    
    try:
        # Create message container
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = f"Your {app_name} Verification Code"
        
        # Add HTML body
        message.attach(MIMEText(html_body, 'html'))
        
        # Get SMTP settings
        smtp_server = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
        smtp_port = getattr(settings, 'EMAIL_PORT', 587)
        
        # Create SMTP session
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        
        # Login and send
        server.login(sender_email, sender_password)
        text = message.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        logger.info(f"✅ Verification email sent to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send verification email to {recipient_email}: {str(e)}")
        return False


def send_welcome_email(recipient_email, username):
    """Send welcome email after successful registration"""
    sender_email = getattr(settings, 'EMAIL_HOST_USER', '')
    sender_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
    app_name = getattr(settings, 'APP_NAME', 'AgriConnect')
    
    if not sender_email or not sender_password:
        return False
    
    html_body = f"""
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
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to {app_name}!</h1>
                </div>
                
                <p>Hi {username},</p>
                
                <p>Thank you for registering with {app_name}! Your account has been successfully created.</p>
                
                <p>You can now log in and start using our services.</p>
                
                <p>If you have any questions, feel free to contact our support team.</p>
                
                <p>Best regards,<br>The {app_name} Team</p>
            </div>
        </body>
    </html>
    """
    
    try:
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = f"Welcome to {app_name}!"
        message.attach(MIMEText(html_body, 'html'))
        
        smtp_server = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
        smtp_port = getattr(settings, 'EMAIL_PORT', 587)
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, message.as_string())
        server.quit()
        
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return False