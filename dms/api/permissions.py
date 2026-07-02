from rest_framework import permissions


class IsStaffOrAdminPermission(permissions.BasePermission):
    """
    Permission class checking if the user is a staff member or administrator.
    """

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and (request.user.is_staff or request.user.is_superuser)
        )
