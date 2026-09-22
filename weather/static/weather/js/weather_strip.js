const WEATHER_CONDITION_ICONS = {
  storm: "⚡",
  precipitation: "☂",
  snow: "❄",
  fog: "≈",
  partlyCloudy: "◐",
  cloudy: "☁",
  clear: "☀",
};

function weatherIcon(weatherCode) {
  if ([95, 96, 99].includes(weatherCode)) return WEATHER_CONDITION_ICONS.storm;
  if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(weatherCode)) {
    return WEATHER_CONDITION_ICONS.precipitation;
  }
  if ([71, 73, 75, 77, 85, 86].includes(weatherCode)) {
    return WEATHER_CONDITION_ICONS.snow;
  }
  if ([45, 48].includes(weatherCode)) return WEATHER_CONDITION_ICONS.fog;
  if (weatherCode === 2) return WEATHER_CONDITION_ICONS.partlyCloudy;
  if (weatherCode === 3) return WEATHER_CONDITION_ICONS.cloudy;
  return WEATHER_CONDITION_ICONS.clear;
}

function weatherStrip() {
  return {
    status: "WAITING FOR LOCATION",
    current: null,
    hourly: [],
    events: [],
    advisory: null,
    source: null,
    weatherAgeSeconds: 0,
    latitude: null,
    longitude: null,
    requestSequence: 0,
    controller: null,

    init() {
      document.addEventListener("webnexus:gps_pulse", (event) => {
        const coordinates = event.detail || {};
        this.loadWeather(coordinates.lat, coordinates.lon);
      });
    },

    async loadWeather(latitude, longitude) {
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;
      if (
        this.latitude !== null &&
        Math.abs(this.latitude - latitude) < 0.00001 &&
        Math.abs(this.longitude - longitude) < 0.00001
      ) {
        return;
      }

      this.latitude = latitude;
      this.longitude = longitude;
      const sequence = ++this.requestSequence;
      this.controller?.abort();
      this.controller = new AbortController();
      this.status = "LOADING";

      try {
        const token = document.querySelector('meta[name="csrf-token"]')?.content;
        const response = await fetch("/weather/api/current/", {
          method: "POST",
          credentials: "same-origin",
          signal: this.controller.signal,
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
            ...(token ? { "X-CSRFToken": token } : {}),
          },
          body: JSON.stringify({ latitude, longitude }),
        });
        const payload = await response.json();
        if (sequence !== this.requestSequence) return;
        if (!response.ok || payload.error) throw new Error(payload.error?.code);

        const data = payload.data;
        this.current = data.current;
        this.hourly = data.hourly || [];
        this.events = data.events || [];
        this.advisory = data.advisory || { level: "NORMAL" };
        this.source = data.source;
        this.weatherAgeSeconds = data.age_seconds || 0;
        this.status = this.advisory.level === "ADVERSE" ? "ALERT" : "READY";
      } catch (error) {
        if (error.name === "AbortError" || sequence !== this.requestSequence) return;
        // Permit the next GPS pulse to retry a transient weather failure.
        this.latitude = null;
        this.longitude = null;
        this.current = null;
        this.hourly = [];
        this.events = [];
        this.status = "WEATHER UNAVAILABLE";
      }
    },

    get hasWeather() {
      return this.current !== null;
    },

    get currentLine() {
      if (!this.current) return "WX: WEATHER UNAVAILABLE";
      const temperature = `${this.numberWithUnit(this.current.temperature, "F")} ${this.temperatureTrendIcon}`;
      const wind = this.numberWithUnit(this.current.wind_speed, "MPH");
      const direction = this.compassDirection(this.current.wind_direction);
      const prefix = this.advisory?.level === "ADVERSE" ? "ALERT" : "";
      const windText = wind ? `WIND ${wind}${direction ? ` ${direction}` : ""}` : "";
      return [this.conditionIcon, prefix, temperature, this.current.condition, windText]
        .filter(Boolean)
        .join(" | ");
    },

    get conditionIcon() {
      return weatherIcon(this.current?.weather_code);
    },

    get temperatureTrendIcon() {
      const currentTemperature = Number(this.current?.temperature);
      const nextTemperature = Number(this.hourly[1]?.temperature);
      if (!Number.isFinite(currentTemperature) || !Number.isFinite(nextTemperature)) return "→";
      if (nextTemperature > currentTemperature + 0.5) return "↑";
      if (nextTemperature < currentTemperature - 0.5) return "↓";
      return "→";
    },

    get freshnessLine() {
      if (!this.hasWeather) return "";
      if (this.source === "stale") return "STALE DATA";
      const ageMinutes = Math.floor((this.ageSeconds || 0) / 60);
      return ageMinutes ? `UPDATED ${ageMinutes}M AGO` : "UPDATED NOW";
    },

    get ageSeconds() {
      return this.weatherAgeSeconds || 0;
    },

    numberWithUnit(value, unit) {
      return Number.isFinite(Number(value)) ? `${Math.round(value)} ${unit}` : "";
    },

    compassDirection(degrees) {
      if (!Number.isFinite(Number(degrees))) return "";
      return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][
        Math.round(Number(degrees) / 45) % 8
      ];
    },
  };
}

if (typeof document !== "undefined") {
  document.addEventListener("alpine:init", () => {
    Alpine.data("weatherStrip", weatherStrip);
  });
}
