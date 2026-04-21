# Tactical Authentication System (Accounts) - Design Document (v2.4.0)

## Objective
Establish a secure, modular, and flexible "Field Identity" system that prioritizes email-based login while remaining compatible with standard Django conventions and future tactical requirements.

## Core Strategy: "Standard Foundation, Tactical Extension"
Instead of a complex custom user model, we use the battle-tested Django default `User` model and extend it via a `Profile` model. This ensures maximum compatibility and easier future migrations.

### 1. Identity Logic
- **Primary Identifier:** Email address.
- **Username Synchronization:** During registration, we programmatically set `username = email` via signals.
- **Dual-Mode Login:** A custom authentication backend allows users to enter either their `email` or their `username` (internal ID).

### 2. Service Record Architecture (New in v2.4.0)
The profile system follows a "Read-First, Edit-Explicit" pattern to prevent accidental modifications in the field.
- **Read-Only Service Record:** Displays agent identity and clearance status.
- **Editable Update Record:** A separate view for modifying basic identity parameters.
- **Verification Protocol:** "Field Agent Verification" (Clearance Level) is a server-side flag controlled exclusively by Command Level (Admin) users.

### 3. Production Security (v2.4.0)
- **HTTPS Enforcement:** The system automatically forces secure connections in production (`DEBUG=False`).
- **Secure Cookie Protocol:** Session IDs and CSRF tokens are marked as `Secure`, preventing transmission over unencrypted channels.

## Modularity ROEs (Rules of Engagement)
- **Logic Isolation:** All synchronization logic (email-to-username) and authentication backend code reside in `accounts/logic/`.
- **Data Separation:** Core auth data stays in `auth_user`. Tactical metadata (Field Verification, Driver ID) resides in `accounts/models.py`.
- **Documentation Standards:** All views and forms must include "OPERATIONAL FLOW" docstrings to guide future maintenance.

## Key Files & Structure
- `accounts/models.py`: 
    - `Profile`: One-to-one link to `User`. Stores field status and tactical metadata.
- `accounts/logic/auth_backends.py`: Custom backend for Dual-ID login (Email or Username).
- `accounts/logic/signals.py`: Automates `Profile` creation and `username=email` syncing.
- `accounts/forms.py`: Tactical forms optimized for field input (large touch targets, monospaced fonts).
- `accounts/admin.py`: Custom "WarMaster" console for unified user and profile management.

## Implementation Status

### Phase 1: Stabilization (Complete)
1. Revert `AUTH_USER_MODEL` to default in `settings.py`.
2. Implement `EmailOrUsernameBackend` and `Profile` model.
3. Configure auto-sync signals.

### Phase 2: Tactical Extension (Complete)
1. **Service Record Dashboard**: Implemented read-only and edit views with military-style UI.
2. **Operational Logging**: Added robust event tracking for logins and record updates.
3. **Security Hardening**: Enabled HTTPS protocols and secure cookie handling for production.
4. **UI Streamlining**: Reduced navbar clutter and implemented Tactical Amber theme.
