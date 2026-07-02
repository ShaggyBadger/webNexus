from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.views.generic import TemplateView

from dms.models import Category, Collection, Tag
from dms.services.search_service import DocumentSearchService


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Template view to display the DMS dashboard.
    """

    template_name = "dms/dashboard.html"
    page_size = 10

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(active=True)
        context["tags"] = Tag.objects.all()

        collections = Collection.objects.all()
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            collections = collections.filter(is_public=True)
        context["collections"] = collections

        search_query = self.request.GET.get("q")
        category_id = self.request.GET.get("category")
        collection_id = self.request.GET.get("collection")
        tag_id = self.request.GET.get("tag")
        tag_slug = self.request.GET.get("tag_slug")
        state_filter = self.request.GET.get("state")
        status_filter = self.request.GET.get("status", "ACTIVE")

        is_public_only = not (
            self.request.user.is_staff or self.request.user.is_superuser
        )
        if is_public_only:
            status_filter = "ACTIVE"

        queryset = DocumentSearchService.search_documents(
            search_query=search_query,
            category_id=category_id,
            collection_id=collection_id,
            status=status_filter,
            state=state_filter,
            tag_id=tag_id,
            tag_slug=tag_slug,
            is_public_only=is_public_only,
        )

        paginator = Paginator(queryset, self.page_size)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["documents"] = page_obj.object_list
        context["documents_page"] = page_obj
        context["documents_count"] = paginator.count
        return context
