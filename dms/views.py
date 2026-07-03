from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views.generic import TemplateView

from dms.models import Category, Collection, Document, Tag
from dms.services.search_service import DocumentSearchService


class DashboardView(TemplateView):
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

        is_staff_user = bool(
            self.request.user.is_authenticated
            and (self.request.user.is_staff or self.request.user.is_superuser)
        )
        is_authenticated_user = bool(self.request.user.is_authenticated)
        is_public_only = not is_authenticated_user

        if not is_staff_user:
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


class DocumentMetadataEditView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Template view to edit metadata for a single document.
    """

    template_name = "dms/document_edit.html"

    def test_func(self) -> bool:
        return bool(self.request.user.is_staff or self.request.user.is_superuser)

    def get_document(self, ulid: str) -> Document:
        return get_object_or_404(Document, id=ulid)

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        document = self.get_document(self.kwargs["ulid"])
        context["document"] = document
        context["categories"] = Category.objects.filter(active=True)
        context["collections"] = Collection.objects.all()
        context["error_message"] = kwargs.get("error_message", "")
        return context

    def post(self, request: HttpRequest, ulid: str) -> HttpResponse:
        document = self.get_document(ulid)

        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        category_id = request.POST.get("category")
        collection_ids = request.POST.getlist("collections")
        tags_input = request.POST.get("tags", "")
        requires_login = request.POST.get("requires_login") == "on"

        if not title:
            return self.render_to_response(
                self.get_context_data(
                    error_message="Title is required.",
                )
            )

        category = None
        if category_id:
            category = Category.objects.filter(id=category_id, active=True).first()
            if category is None:
                return self.render_to_response(
                    self.get_context_data(
                        error_message="Selected category is invalid.",
                    )
                )

        document.title = title
        document.description = description
        document.category = category
        document.is_public = not requires_login
        document.version += 1
        document.save()

        collections = Collection.objects.filter(id__in=collection_ids)
        document.collections.set(collections)

        tag_names = [
            tag_name.strip() for tag_name in tags_input.split(",") if tag_name.strip()
        ]
        tag_objects = []
        for tag_name in tag_names:
            tag_slug = slugify(tag_name)
            tag_object, _ = Tag.objects.get_or_create(
                slug=tag_slug,
                defaults={"name": tag_name},
            )
            if tag_object.name != tag_name:
                tag_object.name = tag_name
                tag_object.save(update_fields=["name"])
            tag_objects.append(tag_object)

        document.tags.set(tag_objects)

        return redirect("dms:dashboard")


class DocumentUploadView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Template view for dedicated two-phase document upload.
    """

    template_name = "dms/upload.html"

    def test_func(self) -> bool:
        return bool(self.request.user.is_staff or self.request.user.is_superuser)

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(active=True)
        context["collections"] = Collection.objects.all()
        return context
