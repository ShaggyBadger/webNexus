document.addEventListener("DOMContentLoaded", () => {
  const checkinButtons = document.querySelectorAll(".manual-checkin-btn");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

  checkinButtons.forEach((button) => {
    button.addEventListener("click", async function () {
      const rackId = this.getAttribute("data-rack-id");
      const originalText = this.innerText;

      this.disabled = true;
      this.innerText = "RECORDING...";

      try {
        let lat = null;
        let lon = null;
        let accuracy = null;

        if (navigator.geolocation) {
          const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
              timeout: 5000,
            });
          }).catch(() => null);

          if (position) {
            lat = position.coords.latitude;
            lon = position.coords.longitude;
            accuracy = position.coords.accuracy;
          }
        }

        const response = await fetch("/siteintel/api/rack-checkin/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            rack_id: rackId,
            lat,
            lon,
            accuracy,
          }),
        });

        if (!response.ok) {
          throw new Error("Check-in failed");
        }

        this.innerText = "CHECK-IN SUCCESS";
        this.classList.replace("btn-outline-warning", "btn-success");
        setTimeout(() => window.location.reload(), 2000);
      } catch (error) {
        console.error("RACK_LIST_CHECKIN_ERROR", error);
        this.innerText = "ERROR - RETRY";
        this.disabled = false;
      } finally {
        if (!this.classList.contains("btn-success")) {
          this.innerText = originalText;
        }
      }
    });
  });
});
