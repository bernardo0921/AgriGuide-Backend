# views.py (Add these to your existing views.py)
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings


def mobile_app_page(request):
    """
    Render the mobile app landing page
    """
    context = {
        'apk_available': True,
        'apk_version': '1.0.0',  # Update this manually when you upload new version
        'apk_size': '25',  # Size in MB - update manually
        'last_updated': 'November 2024',  # Update manually
    }
    
    return render(request, 'mobile_app.html', context)


def download_apk(request):
    """
    Redirect to the APK file on S3 for download
    """
    # Your S3 APK URL - Update this with your actual S3 URL
    # Format: https://your-bucket.s3.region.amazonaws.com/media/apk/agriguide.apk
    # Or if using CloudFront: https://your-cloudfront-domain.net/media/apk/agriguide.apk
    
    apk_url = f"https://agri-guide.s3.eu-north-1.amazonaws.com/media/apk/base.apk"
    
    return redirect(apk_url)


def get_apk_info(request):
    """
    API endpoint to get APK information (version, size, etc.)
    """
    # Update these values manually when you upload a new APK
    apk_info = {
        'available': True,
        'filename': 'agriguide.apk',
        'version': '1.0.0',
        'size': '25 MB',
        'download_url': '/download-apk/',
        'uploaded_at': '2024-11-27',
        'changelog': 'Initial release with AI advisory, community features, and learning center',
    }
    
    return JsonResponse(apk_info)


def legal_page(request):
    """
    Render the legal page with terms of service, privacy policy, etc.
    """
    return render(request, 'legal.html')


def terms_of_service(request):
    """
    Render the terms of service page.
    """
    return render(request, 'terms_of_service.html')


def privacy_policy(request):
    """
    Render the privacy policy page.
    """
    return render(request, 'privacy_policy.html')


def help_and_feedback(request):
    """
    Render the help and feedback page.
    """
    return render(request, 'help_and_feedback.html')