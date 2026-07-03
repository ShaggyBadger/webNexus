window.DMSDocumentActionsMixin = function DMSDocumentActionsMixin() {
  return {
    deleteOpen: {},

    documentDetailUrl(documentId) {
      return this.endpoints.documentDetailTemplate.replace(
        "DOC_ID_PLACEHOLDER",
        documentId,
      );
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
