import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from .models import Profile
from .forms import TacticalSignupForm, TacticalLoginForm, TacticalProfileForm, TacticalProfileModelForm

# Configure Tactical Logger for Accounts App
# This logger routes through the central logging configuration defined in settings.py
logger = logging.getLogger('django')

@login_required
def tactical_password_change(request):
    """
    Tactical Password Change view.
    
    OPERATIONAL FLOW:
    1. Authenticated agent requests password change.
    2. On POST, validates the new password against Django's security policy.
    3. Saves new password and updates session hash to prevent logout (security protocol).
    4. Logs success/failure for security audit.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Important: update_session_auth_hash keeps the user logged in after password change
            update_session_auth_hash(request, user)
            logger.info(f"PASSWORD_CHANGED: Agent {user.username} successfully updated credentials.")
            messages.success(request, 'PASSWORD CHANGED SUCCESSFULLY.')
            return redirect('accounts:profile')
        else:
            logger.warning(f"PASSWORD_CHANGE_FAILED: Validation error for Agent {request.user.username}.")
            messages.error(request, 'PASSWORD CHANGE FAILED. Check protocol errors.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/password_change.html', {'form': form})

def tactical_login(request):
    """
    Standard login logic with tactical UI wrapper.
    
    OPERATIONAL FLOW:
    1. Agent provides credentials (Email/Username + Password).
    2. Backend authenticates via EmailOrUsernameBackend (allows dual-id login).
    3. If valid, establishes session and redirects to homepage.
    4. Logs all access attempts (granted/denied) for system monitoring.
    """
    if request.method == 'POST':
        form = TacticalLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info(f"ACCESS_GRANTED: Agent {user.username} logged into system.")
            messages.success(request, f"ACCESS GRANTED. Welcome, {user.username}.")
            return redirect('homepage:homepage')
        else:
            logger.warning(f"ACCESS_DENIED: Failed login attempt for credentials provided.")
            messages.error(request, "ACCESS DENIED. Invalid credentials.")
    else:
        form = TacticalLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def tactical_logout(request):
    """
    Standard logout.
    
    Terminates the current session and clears client-side cookies.
    """
    user = request.user
    if user.is_authenticated:
        logger.info(f"SESSION_TERMINATED: Agent {user.username} logged out.")
    
    logout(request)
    messages.info(request, "SESSION TERMINATED.")
    return redirect('homepage:homepage')

def tactical_signup(request):
    """
    Enlistment view for new agents.
    
    OPERATIONAL FLOW:
    1. Collects email/identity from new agent.
    2. UserCreationForm handles password hashing and security requirements.
    3. Auto-sync signals (accounts/logic/signals.py) generate the internal username.
    4. Logs in the new agent immediately upon successful record creation.
    """
    if request.method == 'POST':
        form = TacticalSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Note: Explicit backend required for immediate login after signup
            login(request, user, backend='accounts.logic.auth_backends.EmailOrUsernameBackend')
            logger.info(f"ENLISTMENT_SUCCESS: New agent {user.email} joined the network.")
            messages.success(request, "ENLISTMENT SUCCESSFUL. Welcome to webNexus.")
            return redirect('homepage:homepage')
        else:
            logger.warning("ENLISTMENT_FAILED: Protocol validation errors during signup.")
            messages.error(request, "ENLISTMENT FAILED. Check protocol errors.")
    else:
        form = TacticalSignupForm()
    
    return render(request, 'accounts/signup.html', {'form': form})

@login_required
def tactical_profile(request):
    """
    Service Record (Profile) dashboard. Read-only view.
    
    Displays agent identity parameters and clearance status.
    """
    user = request.user
    # Profile recovery: ensures the agent has a profile record even if signals failed
    profile, created = Profile.objects.get_or_create(user=user)
    if created:
        logger.info(f"PROFILE_RECOVERY: Generated missing profile record for Agent {user.username}.")
    
    return render(request, 'accounts/profile.html', {
        'user': user,
        'profile': profile
    })

@login_required
def tactical_profile_edit(request):
    """
    Service Record (Profile) update view.
    
    Handles modification of agent identity fields (First/Last name)
    and Profile parameters (Callsign, Map Preference).
    """
    user = request.user
    profile, created = Profile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        user_form = TacticalProfileForm(request.POST, instance=user)
        profile_form = TacticalProfileModelForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            logger.info(f"RECORD_UPDATED: Agent {user.username} updated identity parameters.")
            messages.success(request, "SERVICE RECORD UPDATED.")
            return redirect('accounts:profile')
        else:
            logger.warning(f"RECORD_UPDATE_FAILED: Identity validation errors for Agent {user.username}.")
            messages.error(request, "UPDATE FAILED. Check protocol errors.")
    else:
        user_form = TacticalProfileForm(instance=user)
        profile_form = TacticalProfileModelForm(instance=profile)
    
    return render(request, 'accounts/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user
    })
