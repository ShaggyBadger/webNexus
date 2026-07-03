window.DMSUploadMixin = function DMSUploadMixin() {
  return {
    maxUploadSizeBytes: 50 * 1024 * 1024,
    uploadOpen: false,
    upload: {
      phase: "raw",
      inProgress: false,
      progressPercent: 0,
      tempId: "",
      form: {
        title: "",
        category: "",
        description: "",
        collections: [],
        contentType: "",
        objectId: "",
        tags: "",
        requiresLogin: false,
      },
    },

    toggleUpload() {
      this.uploadOpen = !this.uploadOpen;
      if (this.uploadOpen) {
        this.resetUploadPanel();
      }
    },

    closeUploadPanel() {
      this.uploadOpen = false;
    },

    resetUploadPanel() {
      this.upload.phase = "raw";
      this.upload.inProgress = false;
      this.upload.progressPercent = 0;
      this.upload.tempId = "";
      this.upload.form = {
        title: "",
        category: "",
        description: "",
        collections: [],
        contentType: "",
        objectId: "",
        tags: "",
        requiresLogin: false,
      };
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = "";
      }
    },

    onDrop(event) {
      const files = event.dataTransfer?.files || [];
      if (files.length > 0) {
        this.handleFileUpload(files[0]);
      }
    },

    onFileChange(event) {
      const files = event.target?.files || [];
      if (files.length > 0) {
        this.handleFileUpload(files[0]);
      }
    },

    handleFileUpload(file) {
      if (file.size > this.maxUploadSizeBytes) {
        const maxMb = Math.floor(this.maxUploadSizeBytes / (1024 * 1024));
        this.showAlert(
          `FILE TOO LARGE: ${file.name} exceeds ${maxMb}MB. Compress or split the file before upload.`,
          "error",
        );
        if (this.$refs.fileInput) {
          this.$refs.fileInput.value = "";
        }
        return;
      }

      this.upload.inProgress = true;
      this.upload.progressPercent = 0;

      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", this.endpoints.rawUpload, true);
      xhr.setRequestHeader("X-CSRFToken", this.csrfToken);

      xhr.upload.onprogress = (progressEvent) => {
        if (progressEvent.lengthComputable) {
          this.upload.progressPercent = Math.round(
            (progressEvent.loaded / progressEvent.total) * 100,
          );
        }
      };

      xhr.onload = () => {
        let response = {};
        try {
          response = JSON.parse(xhr.responseText || "{}");
        } catch (error) {
          response = {};
        }

        const responseData = response.data || response;
        const tempId = responseData.temp_id || responseData.tempId || "";
        const originalName = responseData.original_name || responseData.originalName || "";

        if (xhr.status === 201 && tempId) {
          this.upload.inProgress = false;
          this.showAlert(
            "PHASE A: Raw ingestion complete. Fill metadata to finalize.",
            "success",
          );
          this.upload.tempId = tempId;
          const filename = originalName;
          const extensionIndex = filename.lastIndexOf(".");
          this.upload.form.title =
            extensionIndex > 0 ? filename.substring(0, extensionIndex) : filename;
          this.upload.phase = "finalize";
          return;
        }

        this.upload.inProgress = false;
        const errorMessage =
          response.error?.message ||
          response.message ||
          `Raw ingestion failed (HTTP ${xhr.status}).`;
        this.showAlert(`PHASE A FAILED: ${errorMessage}`, "error");
        this.resetUploadPanel();
      };

      xhr.onerror = () => {
        this.upload.inProgress = false;
        this.showAlert("Network connection error during raw ingestion.", "error");
        this.resetUploadPanel();
      };

      xhr.send(formData);
    },

    submitFinalize() {
      const payload = {
        temp_id: this.upload.tempId,
        title: this.upload.form.title,
        description: this.upload.form.description,
        category: this.upload.form.category || null,
        collections: this.upload.form.collections,
        content_type: this.upload.form.contentType || null,
        object_id: this.upload.form.objectId || null,
        is_public: !this.upload.form.requiresLogin,
        tags: this.upload.form.tags
          .split(",")
          .map((item) => item.trim())
          .filter((item) => item.length > 0),
      };

      fetch(this.endpoints.finalizeUpload, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrfToken,
        },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            this.showAlert(
              "PHASE B SUCCESS: Document fully indexed. Reloading...",
              "success",
            );
            setTimeout(() => window.location.reload(), 1500);
            return;
          }
          this.showAlert(
            `PHASE B FAILED: ${data.error?.message || "Unknown error"}`,
            "error",
          );
        })
        .catch(() => {
          this.showAlert("Network error during finalize upload.", "error");
        });
    },
  };
};
