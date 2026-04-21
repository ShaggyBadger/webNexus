
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thejoshproject.settings")
import django
django.setup()

from django.contrib.auth.models import User

def reproduce_deletion_error():
    print("--- Starting Deletion Reproduction ---")
    
    # 1. Create a dummy user
    test_username = "test_delete_user@example.com"
    if User.objects.filter(username=test_username).exists():
        User.objects.filter(username=test_username).delete()
    
    user = User.objects.create_user(username=test_username, email=test_username, password="password123")
    print(f"Created user: {user.username} (ID: {user.id})")
    
    # 2. Attempt to delete
    try:
        print(f"Attempting to delete user ID: {user.id}")
        user.delete()
        print("[SUCCESS] User deleted without errors.")
    except Exception as e:
        print(f"[FAILURE] Deletion failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reproduce_deletion_error()
