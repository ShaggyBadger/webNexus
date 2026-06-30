from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from io import StringIO


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


@staff_member_required
@require_POST
def trigger_resolve_tank_conflicts(request):
    """
    Dry-run or commit the resolve_tank_conflicts management command from the admin panel.
    Pass ?commit=1 in the POST body to apply changes; omit for a dry-run preview.
    """
    commit = request.POST.get("commit") == "1"
    out = StringIO()
    try:
        kwargs = {"stdout": out, "commit": commit}
        call_command("resolve_tank_conflicts", **kwargs)
        output = out.getvalue()
        if commit:
            messages.success(
                request,
                f"Tank conflict resolution completed (COMMIT mode).\n{output}",
            )
        else:
            messages.info(
                request,
                f"Tank conflict resolution DRY-RUN complete (no changes written).\n{output}",
            )
    except Exception as exc:
        messages.error(request, f"resolve_tank_conflicts failed: {exc}")

    return redirect("admin:index")


@staff_member_required
@require_POST
def trigger_sanitize_veeder_readings(request):
    """
    Dry-run or commit the sanitize_veeder_readings management command from admin.
    Pass commit=1 to apply deletions. Pass delete_suspicious=1 to also delete
    soft-suspicious rows.
    """
    commit = request.POST.get("commit") == "1"
    delete_suspicious = request.POST.get("delete_suspicious") == "1"
    out = StringIO()
    try:
        kwargs = {
            "stdout": out,
            "commit": commit,
            "delete_suspicious": delete_suspicious,
        }
        call_command("sanitize_veeder_readings", **kwargs)
        output = out.getvalue()
        if commit:
            messages.success(
                request,
                "Veeder reading sanitization completed (COMMIT mode).\n" f"{output}",
            )
        else:
            messages.info(
                request,
                "Veeder reading sanitization DRY-RUN complete (no changes written).\n"
                f"{output}",
            )
    except Exception as exc:
        messages.error(request, f"sanitize_veeder_readings failed: {exc}")

    return redirect("admin:index")
