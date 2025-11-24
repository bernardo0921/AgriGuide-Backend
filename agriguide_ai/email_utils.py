# email_utils.py - Create this file in your app directory

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


from django.core.mail import send_mail
import logging


def send_verification_email(recipient_email, code, purpose="verification"):
    """Send verification email using Django's email backend"""
    
    app_name = getattr(settings, 'APP_NAME', 'AgriGuide')
    
    purpose_text = {
        'registration': 'complete your registration',
        'login': 'sign in to your account',
        'password_reset': 'reset your password'
    }
    
    action_text = purpose_text.get(purpose, 'verify your email')
    
    subject = f"Your {app_name} Verification Code"
    
    # Simple text message (uses less memory than HTML)
    message = f"""
Hello,

Your verification code is: {code}

Use this code to {action_text}.

This code expires in 5 minutes.

Security Notice: Never share this code with anyone.

Best regards,
The {app_name} Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [recipient_email],
            fail_silently=False,
        )
        logger.info(f"✅ Email sent to {recipient_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Email failed: {str(e)}")
        return False

def send_welcome_email(recipient_email, username):
    """Send welcome email after successful registration"""
    sender_email = 'ephraimbernard77@gmail.com'
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