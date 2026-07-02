window.DMSDocumentActionsMixin = function DMSDocumentActionsMixin() {
  return {
    editOpen: {},
    deleteOpen: {},

    documentDetailUrl(documentId) {
      return this.endpoints.documentDetailTemplate.replace(
        "DOC_ID_PLACEHOLDER",
        documentId,
      );
    },

    toggleEdit(documentId) {
      this.editOpen[documentId] = !this.editOpen[documentId];
    },

    closeEdit(documentId) {
      this.editOpen[documentId] = false;
    },

    isEditOpen(documentId) {
      return !!this.editOpen[documentId];
    },

    toggleDelete(documentId) {
      this.deleteOpen[documentId] = !this.deleteOpen[documentId];
    },

    closeDelete(documentId) {
      this.deleteOpen[documentId] = false;
    },

    isDeleteOpen(documentId) {
      return !!this.deleteOpen[documentId];
    },

    saveEdit(documentId, event) {
      const activeBlock = event.target.closest(".edit-form-block");
      if (!activeBlock) {
        return;
      }

      const title = activeBlock.querySelector(".edit-title-input")?.value || "";
      const description =
        activeBlock.querySelector(".edit-desc-input")?.value || "";
      const tagsText = activeBlock.querySelector(".edit-tags-input")?.value || "";
      const tags = tagsText
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      const isPublic =
        activeBlock.querySelector(".edit-is-public-input")?.checked || false;

      fetch(this.documentDetailUrl(documentId), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrfToken,
        },
        body: JSON.stringify({
          title,
          description,
          tags,
          is_public: isPublic,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            this.showAlert("Document details updated.", "success");
            setTimeout(() => window.location.reload(), 1000);
            return;
          }
          this.showAlert(
            `Update failed: ${data.error?.message || "Unknown error"}`,
            "error",
          );
        })
        .catch(() => {
          this.showAlert("Network error occurred during metadata update.", "error");
        });
    },

    confirmDelete(documentId) {
      fetch(this.documentDetailUrl(documentId), {
        method: "DELETE",
        headers: {
          "X-CSRFToken": this.csrfToken,
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            this.showAlert("Document moved to trash and archived.", "success");
            setTimeout(() => window.location.reload(), 1000);
            return;
          }
          this.showAlert(
            `Archive action failed: ${data.error?.message || "Unknown error"}`,
            "error",
          );
        })
        .catch(() => {
          this.showAlert("Network error during archive request.", "error");
        });
    },
  };
};
