# Tactical Site Intelligence: Future Wishlist

This document tracks identified architectural and operational improvements for the `webNexus` site intelligence system.

## 1. Ambiguous Tank Resolution
*   **Problem:** `get_tank_mapping` uses `.first()`, which fails at sites with multiple tanks of the same fuel type.
*   **Fix:** Refactor logic to prioritize `tank_index` (ATG physical number) over fuel type strings.

## 2. Manifolded Tanks (Linked Systems)
*   **Problem:** Some sites have tanks connected via pipe (manifolded) that act as a single volume.
*   **Fix:** Add `is_manifolded` (Boolean) and `manifold_group` (Integer) to `StoreTankMapping` and `TankUpdate`. Update calculation logic to aggregate volumes for manifolded groups.

## 3. Lifecycle Management (Active/Decommissioned)
*   **Problem:** No way to mark a tank as "Out of Service" without deleting the record.
*   **Fix:** Add `is_active` (Boolean) to `StoreTankMapping` and `TankUpdate`.

## 4. Enhanced Site Metadata
*   **Problem:** Missing standard operational data like site contact info or emergency status.
*   **Fix:** Add `phone_number`, `operational_status` (OPEN/CLOSED/MAINTENANCE), and `site_notes` to `Store` and `Location` models.
