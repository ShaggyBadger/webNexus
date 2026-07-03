function dmsUploadPageApp() {
  return {
    endpoints: {
      rawUpload: "",
      finalizeUpload: "",
    },
    csrfToken: "",
    statusAlert: {
      visible: false,
      message: "",
      type: "success",
    },
    ...window.DMSUploadMixin(),

    init() {
      this.endpoints.rawUpload = this.$el.dataset.rawUploadUrl || "";
      this.endpoints.finalizeUpload = this.$el.dataset.finalizeUploadUrl || "";
      this.csrfToken =
        document.querySelector('meta[name="csrf-token"]')?.content || "";
      this.uploadOpen = true;
      this.resetUploadPanel();
      this.uploadOpen = true;
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
  Alpine.data("dmsUploadPageApp", dmsUploadPageApp);
});
