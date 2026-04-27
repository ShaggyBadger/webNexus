import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from .models import Profile
from .forms import TacticalSignupForm, TacticalLoginForm, TacticalProfileForm, TacticalProfileModelForm

# Configure Tactical Logger for Accounts
logger = logging.getLogger('webnexus')

@login_required
def tactical_password_change(request):
    """
    TACTICAL_CREDENTIAL_OVERRIDE:
    Updates the agent's authentication credentials while maintaining session integrity.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # TACTICAL: Maintain active session after password swap
            update_session_auth_hash(request, user)
            logger.info(f"AUTH_SECURITY: Agent {user.username} updated credentials successfully.")
            messages.success(request, 'PASSWORD CHANGED SUCCESSFULLY.')
            return redirect('accounts:profile')
        else:
            logger.warning(f"AUTH_SECURITY_FAIL: Credential update rejected for Agent {request.user.username}.")
            messages.error(request, 'PASSWORD CHANGE FAILED. Check protocol errors.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/password_change.html', {'form': form})

def tactical_login(request):
    """
    TACTICAL_ACCESS_CONTROL:
    Authenticates agents using multi-identifier logic (Email or Username).
    Establishes secure session links.
    """
    if request.method == 'POST':
        form = TacticalLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info(f"ACCESS_GRANTED: Agent {user.username} established secure link.")
            messages.success(request, f"ACCESS GRANTED. Welcome, {user.username}.")
            return redirect('homepage:homepage')
        else:
            logger.warning("ACCESS_DENIED: Unauthorized link attempt detected.")
            messages.error(request, "ACCESS DENIED. Invalid credentials.")
    else:
        form = TacticalLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def tactical_logout(request):
    """
    TACTICAL_DISCONNECT:
    Terminates active session and synchronizes system state.
    """
    user = request.user
    if user.is_authenticated:
        logger.info(f"ACCESS_TERMINATED: Agent {user.username} disconnected.")
    
    logout(request)
    messages.info(request, "SESSION TERMINATED.")
    return redirect('homepage:homepage')

def tactical_signup(request):
    """
    AGENT_ENLISTMENT:
    Registers new operators and initializes tactical profiles via signals.
    Automatically establishes session link upon successful registration.
    """
    if request.method == 'POST':
        form = TacticalSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # TACTICAL: Auto-login requires explicit backend reference for signals-driven systems
            login(request, user, backend='accounts.logic.auth_backends.EmailOrUsernameBackend')
            logger.info(f"ENLISTMENT_SUCCESS: New agent {user.email} initialized.")
            messages.success(request, "ENLISTMENT SUCCESSFUL. Welcome to webNexus.")
            return redirect('homepage:homepage')
        else:
            logger.warning("ENLISTMENT_FAILED: Registration protocol validation error.")
            messages.error(request, "ENLISTMENT FAILED. Check protocol errors.")
    else:
        form = TacticalSignupForm()
    
    return render(request, 'accounts/signup.html', {'form': form})

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
