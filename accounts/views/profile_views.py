import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Profile
from ..forms import TacticalProfileForm, TacticalProfileModelForm

# Configure Tactical Logger for Accounts
logger = logging.getLogger('webnexus')

@login_required
def tactical_profile(request):
    """
    SERVICE_RECORD_DASHBOARD:
    Read-only view of the agent's identity, callsign, and clearance level.
    """
    user = request.user
    # Profile recovery: Ensures data integrity even if signals were bypassed
    profile, created = Profile.objects.get_or_create(user=user)
    if created:
        logger.info(f"PROFILE_RECOVERY: Generated missing identity record for Agent {user.username}.")
    
    return render(request, 'accounts/profile.html', {
        'user': user,
        'profile': profile
    })

@login_required
def tactical_profile_edit(request):
    """
    SERVICE_RECORD_UPDATE:
    Handles modification of agent parameters (Name, Callsign, Map Preferences).
    """
    user = request.user
    profile, created = Profile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        user_form = TacticalProfileForm(request.POST, instance=user)
        profile_form = TacticalProfileModelForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            logger.info(f"RECORD_SYNC: Agent {user.username} synchronized identity parameters.")
            messages.success(request, "SERVICE RECORD UPDATED.")
            return redirect('accounts:profile')
        else:
            logger.warning(f"RECORD_SYNC_FAIL: Validation errors for Agent {user.username}.")
            messages.error(request, "UPDATE FAILED. Check protocol errors.")
    else:
        user_form = TacticalProfileForm(instance=user)
        profile_form = TacticalProfileModelForm(instance=profile)
    
    return render(request, 'accounts/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user
    })
