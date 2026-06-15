from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.shortcuts import redirect
from django.views.decorators.http import require_POST


@staff_member_required
@require_POST
def trigger_sync_tank_estimates(request):
    """Run batch estimation sync from the admin dashboard."""
    try:
        call_command("sync_tank_estimates")
        messages.success(request, "Tank estimate sync completed successfully.")
    except Exception as exc:
        messages.error(request, f"Tank estimate sync failed: {exc}")

    return redirect("admin:index")
