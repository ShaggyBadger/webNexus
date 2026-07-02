function homepageHub() {
  return {
    clockLabel: "00:00:00L",
    intervalId: null,

    init() {
      this.updateClock();
      this.intervalId = window.setInterval(() => this.updateClock(), 1000);
    },

    updateClock() {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, "0");
      const minutes = String(now.getMinutes()).padStart(2, "0");
      const seconds = String(now.getSeconds()).padStart(2, "0");
      this.clockLabel = `${hours}:${minutes}:${seconds}L`;
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("homepageHub", homepageHub);
});
