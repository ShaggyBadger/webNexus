window.DMSDocumentActionsMixin = function DMSDocumentActionsMixin() {
  return {
    deleteOpen: {},
    emailState: {},

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

    setEmailInput(documentId, value) {
      if (!this.emailState[documentId]) {
        this.emailState[documentId] = {
          email: "",
          sending: false,
          error: "",
          success: false,
        };
      }
      this.emailState[documentId].email = value;
    },

    getEmailState(documentId) {
      if (!this.emailState[documentId]) {
        this.emailState[documentId] = {
          email: "",
          sending: false,
          error: "",
          success: false,
        };
      }
      return this.emailState[documentId];
    },

    sendDocumentEmail(documentId) {
      const state = this.getEmailState(documentId);
      if (state.sending) {
        return;
      }

      state.sending = true;
      state.error = "";
      state.success = false;

      fetch(`/dms/api/v1/documents/${documentId}/email/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrfToken,
        },
        body: JSON.stringify({ email: state.email.trim() }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            state.success = true;
            this.showAlert("Document email sent.", "success");
            return;
          }
          state.error = data.error?.message || "Failed to send email.";
          this.showAlert(state.error, "error");
        })
        .catch(() => {
          state.error = "Network error sending document email.";
          this.showAlert(state.error, "error");
        })
        .finally(() => {
          state.sending = false;
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
