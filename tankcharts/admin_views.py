from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from io import StringIO


@staff_member_required
@require_POST
def trigger_generate_all_tank_charts(request):
    """
    Staff action to trigger batch tank chart generation from admin panel.
    """
    force = request.POST.get("force") == "1"
    dry_run = request.POST.get("dry_run") == "1"
    out = StringIO()

    try:
        kwargs = {"stdout": out, "force": force, "dry_run": dry_run}
        call_command("generate_all_tank_charts", **kwargs)
        output = out.getvalue()
        if dry_run:
            messages.info(
                request,
                f"Batch chart generation DRY-RUN completed.\n{output}",
            )
        else:
            messages.success(
                request,
                f"Batch chart generation completed successfully.\n{output}",
            )
    except Exception as exc:
        messages.error(request, f"Batch chart generation failed: {exc}")

    return redirect("admin:index")
