from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from accounts.models import Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically creates a Profile for every new User.
    """
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensures the Profile is saved whenever the User is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(pre_save, sender=User)
def sync_username_to_email(sender, instance, **kwargs):
    """
    Sets the username to the email address if an email is provided.
    Ensures that the username always matches the email, but avoids 
    creating duplicates that would trigger an IntegrityError.
    """
    if instance.email:
        # Only set if the username is not already the email
        if instance.username != instance.email:
            # Check if another user already has this email as their username
            if not User.objects.filter(username=instance.email).exclude(pk=instance.pk).exists():
                instance.username = instance.email
