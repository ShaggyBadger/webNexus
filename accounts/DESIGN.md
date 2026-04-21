# Tactical Authentication System (Accounts) - Design Document (v2.0)

## Objective
Establish a secure, modular, and flexible "Field Identity" system that prioritizes email-based login while remaining compatible with standard Django conventions and future "Driver ID" requirements.

## Core Strategy: "Standard Foundation, Tactical Extension"
Instead of a complex custom user model, we use the battle-tested Django default `User` model and extend it via a `Profile` model. This ensures maximum compatibility and easier future migrations.

### 1. Identity Logic
- **Primary Identifier:** Email address.
- **Username Synchronization:** During registration, we programmatically set `username = email`.
- **Flexible Login:** A custom authentication backend allows users to enter either their `email` or their `username` (or a future Driver ID) in the login field.

## Modularity ROEs (Rules of Engagement)
- **Logic Isolation:** All synchronization logic (email-to-username) and authentication backend code reside in `accounts/logic/`.
- **Data Separation:** Core auth data stays in `auth_user`. Tactical metadata (Callsign, Driver ID, Unit Assignment) resides in `accounts/models.py` within the `Profile` model.
- **Componentized UI:** Mobile-first login/signup forms use fragments in `accounts/templates/accounts/components/`.

## Key Files & Structure
- `accounts/models.py`: 
    - `Profile`: One-to-one link to `User`. Stores `callsign`, `driver_id`, and field status.
- `accounts/logic/auth_backends.py`: Custom backend for Dual-ID login (Email or Username).
- `accounts/logic/signals.py`: Automates `Profile` creation and `username=email` syncing.
- `accounts/forms.py`: Tactical forms optimized for field input (large touch targets, monospaced fonts).

## Implementation Phases

### Phase 1: Stabilization (Immediate)
1. Revert `AUTH_USER_MODEL` to default in `settings.py`.
2. Remove `CustomUser` and `CustomUserManager`.
3. Clear broken `accounts` migrations to restore a clean state.
4. Verify `warMaster` admin access.

### Phase 2: Tactical Extension
1. Create `Profile` model with `callsign`.
2. Implement `EmailOrUsernameBackend`.
3. Create signals to ensure every new user gets a `Profile` and has `username` synced to `email`.
4. Update Signup form to require `email` and `callsign`.
