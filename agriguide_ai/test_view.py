# ============================================
# STEP 1: Add this view to one of your views.py files
# ============================================

from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.http import require_http_methods

User = get_user_model()

@require_http_methods(["GET", "POST"])
def create_superuser_view(request):
    """
    Temporary view to create a superuser.
    REMOVE THIS AFTER CREATING YOUR SUPERUSER!
    """
    # Security check - only allow if no superusers exist
    if User.objects.filter(is_superuser=True).exists():
        return render(request, 'create_superuser.html', {
            'error': 'A superuser already exists. This form is disabled for security.'
        })
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validation
        if not all([username, email, password, password_confirm]):
            messages.error(request, 'All fields are required.')
            return render(request, 'create_superuser.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'create_superuser.html')
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'create_superuser.html')
        
        try:
            # Create superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            messages.success(request, f'Superuser "{username}" created successfully! You can now log in to the admin panel.')
            return redirect('/admin/')  # Redirect to admin login
        except Exception as e:
            messages.error(request, f'Error creating superuser: {str(e)}')
    
    return render(request, 'create_superuser.html')


# ============================================
# STEP 2: Add this URL pattern to your urls.py
# ============================================

# In your main urls.py, add:
"""
from django.urls import path
from yourapp.views import create_superuser_view  # Import your view

urlpatterns = [
    # ... your other URLs
    path('create-superuser-temp/', create_superuser_view, name='create_superuser'),
]
"""


# ============================================
# STEP 3: Create this template
# Save as: templates/create_superuser.html
# ============================================

TEMPLATE_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Create Superuser</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            max-width: 450px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .warning {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin: 20px 0;
            border-radius: 4px;
            font-size: 14px;
            color: #856404;
        }
        .error {
            background: #f8d7da;
            border-left: 4px solid #dc3545;
            padding: 12px;
            margin: 20px 0;
            border-radius: 4px;
            font-size: 14px;
            color: #721c24;
        }
        .success {
            background: #d4edda;
            border-left: 4px solid #28a745;
            padding: 12px;
            margin: 20px 0;
            border-radius: 4px;
            font-size: 14px;
            color: #155724;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 6px;
            color: #555;
            font-weight: 500;
            font-size: 14px;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 15px;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        button:active {
            transform: translateY(0);
        }
        .info {
            margin-top: 20px;
            padding: 15px;
            background: #e7f3ff;
            border-radius: 6px;
            font-size: 13px;
            color: #004085;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 Create Superuser</h1>
        
        <div class="warning">
            <strong>⚠️ Security Notice:</strong> This is a temporary form. Remove it after creating your superuser!
        </div>

        {% if error %}
        <div class="error">
            {{ error }}
        </div>
        {% endif %}

        {% if messages %}
            {% for message in messages %}
                <div class="{% if message.tags %}{{ message.tags }}{% endif %}">
                    {{ message }}
                </div>
            {% endfor %}
        {% endif %}

        {% if not error %}
        <form method="POST">
            {% csrf_token %}
            
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autocomplete="username">
            </div>
            
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required autocomplete="email">
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autocomplete="new-password" minlength="8">
            </div>
            
            <div class="form-group">
                <label for="password_confirm">Confirm Password</label>
                <input type="password" id="password_confirm" name="password_confirm" required autocomplete="new-password" minlength="8">
            </div>
            
            <button type="submit">Create Superuser</button>
        </form>

        <div class="info">
            <strong>📝 Next Steps:</strong>
            <ol style="margin-left: 20px; margin-top: 8px;">
                <li>After creating the superuser, log in to /admin/</li>
                <li>Remove this URL and view from your code</li>
                <li>Redeploy your application</li>
            </ol>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

# Save the template content above to: templates/create_superuser.html