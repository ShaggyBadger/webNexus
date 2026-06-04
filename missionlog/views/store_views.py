import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from tankgauge.models.store_models import Store

logger = logging.getLogger("webnexus")


@login_required
def validate_store(request):
    """
    VALIDATE_STORE_API:
    GET: Resolves if a user-supplied store number or RISO number exists in the database.
    """
    if request.method == "GET":
        query = request.GET.get("q") or request.GET.get("number")
        if not query:
            return JsonResponse(
                {"valid": False, "message": "Query parameter is required."}, status=400
            )

        try:
            val = int(query.strip())
            store = Store.objects.filter(Q(store_num=val) | Q(riso_num=val)).first()
            if store:
                logger.info(
                    f"STORE_VALIDATE_SUCCESS: Found Store {store.store_num} (RISO: {store.riso_num}) for query: '{query}'."
                )
                return JsonResponse(
                    {
                        "valid": True,
                        "id": store.id,
                        "store_num": store.store_num,
                        "riso_num": store.riso_num,
                        "store_name": store.store_name,
                    }
                )
            else:
                logger.info(
                    f"STORE_VALIDATE_NOT_FOUND: No match in DB for store query: '{query}'."
                )
                return JsonResponse({"valid": False})
        except ValueError:
            logger.info(
                f"STORE_VALIDATE_INVALID: Query '{query}' is not a valid integer."
            )
            return JsonResponse(
                {"valid": False, "message": "Store number must be an integer."}
            )
        except Exception as e:
            logger.error(f"STORE_VALIDATE_ERROR: {str(e)}")
            return JsonResponse({"valid": False, "message": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)
