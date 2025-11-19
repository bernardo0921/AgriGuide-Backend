# forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User # Import your custom User model

class TemporalSuperuserCreationForm(forms.Form):
    """
    A simple form for creating a superuser with the necessary fields for your custom User model.
    """
    # Standard Fields
    username = forms.CharField(max_length=150, label="Username")
    email = forms.EmailField(required=False, label="Email (Optional)")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    
    # Required by your custom User model (Unique and not blank/null)
    phone_number = forms.CharField(
        max_length=17, 
        label="Phone Number (Required by model)",
        help_text="e.g., +233123456789 (must be unique)"
    )
    
    # TEMPORARY SECURITY FIELD
    secret_key = forms.CharField(
        max_length=255, 
        label="Temporal Secret Key",
        help_text="Enter the SUPERUSER_CREATION_KEY environment variable value."
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        return cleaned_data