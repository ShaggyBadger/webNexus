function dmsDashboardApp() {
  return {
    endpoints: {
      rawUpload: "",
      finalizeUpload: "",
      documentDetailTemplate: "",
    },
    csrfToken: "",
    statusAlert: {
      visible: false,
      message: "",
      type: "success",
    },
    ...window.DMSUploadMixin(),
    ...window.DMSDocumentActionsMixin(),

    init() {
      this.endpoints.rawUpload = this.$el.dataset.rawUploadUrl || "";
      this.endpoints.finalizeUpload = this.$el.dataset.finalizeUploadUrl || "";
      this.endpoints.documentDetailTemplate =
        this.$el.dataset.documentDetailTemplate || "";
      this.csrfToken =
        document.querySelector('meta[name="csrf-token"]')?.content || "";
    },

    showAlert(message, type = "success") {
      this.statusAlert = {
        visible: true,
        message,
        type,
      };
      setTimeout(() => {
        this.statusAlert.visible = false;
      }, 5000);
    },

    alertClass() {
      return this.statusAlert.type === "error" ? "alert-danger" : "alert-success";
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("dmsDashboardApp", dmsDashboardApp);
});
