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

