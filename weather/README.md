# Weather

`weather` provides location-aware current weather for the homepage. It listens
for the existing Tactical GPS pulse, reuses nearby recent forecasts, and stores
provider responses for operational history and future analytics.

## Responsibilities

- `models.py` stores provider request history, response payloads, status, and
  the singleton quota lock.
- `services/open_meteo_client.py` calls the Open-Meteo forecast API.
- `services/weather_service.py` validates coordinates, applies the 15-minute
  and 15-mile cache policy, enforces the rolling provider budget, and records
  request outcomes.
- `services/weather_presenter.py` converts provider data into the browser
  contract, including current conditions and the next 12 hourly points.
- `services/weather_advisory.py` derives deterministic operational advisory
  levels from weather conditions.
- `views.py`, `serializers.py`, and `urls.py` expose the current-weather API.
- `templates/` and `static/` render the compact Alpine.js homepage weather
  line.
- `tests.py` covers provider URL construction, normalization, cache reuse,
  validation, quota exhaustion, malformed responses, and template integration.

## Data Flow

1. Tactical GPS obtains a location after user permission and emits
   `webnexus:gps_pulse`.
2. The Alpine weather component posts the coordinates to
   `/weather/api/current/`.
3. The service returns a successful response from within 15 miles when it is
   no more than 15 minutes old.
4. Otherwise, one provider request is reserved, fetched, normalized, and
   stored in `WeatherRequest`.
5. The homepage displays a single compact weather status line and freshness
   state.

Provider calls are serialized through the quota lock so simultaneous cache
   misses do not create duplicate calls. The provider response is retained as
   raw JSON so later analytics can use the original data.

## Configuration

These settings are defined in `thejoshproject/settings.py` and may be
overridden with environment variables:

- `WEATHER_CACHE_RADIUS_MILES`, default `15`
- `WEATHER_PROVIDER_MAX_ATTEMPTS`, default `400`
- `WEATHER_PROVIDER_WINDOW_HOURS`, default `24`
- `WEATHER_CURRENT_THROTTLE_RATE`, default `30/min`

The current provider is Open-Meteo and does not require an API key for the
configured forecast request. The endpoint is currently public because the
homepage weather line is intended to work for anonymous visitors. Any change
to that boundary must account for the shared provider budget.

## Current Boundary

The app currently provides forecast JSON and a compact homepage summary. It
does not provide radar imagery, radar tiles, map overlays, or severe-weather
alert feeds.

Future work may add radar and related weather visualization. Radar should be
treated as a separate provider and data flow because radar updates more often
than the 15-minute forecast cache and will likely require map tile rendering,
provider attribution, and separate retention rules.

## Maintenance

- Preserve the 15-minute freshness and 15-mile proximity cache behavior unless
  the provider budget strategy changes.
- Keep provider payload normalization separate from the homepage presentation.
- Do not expose raw provider payloads directly in the browser contract.
- Establish a retention policy before production weather history becomes large.
- Add focused tests for any provider, quota, cache, or UI contract changes.

## Focused Verification

```bash
python manage.py test weather
python manage.py check
python manage.py makemigrations --check --dry-run
node --check weather/static/weather/js/weather_strip.js
```
