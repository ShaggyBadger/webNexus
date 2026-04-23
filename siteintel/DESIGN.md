# Design Document: Site Intelligence System (Store Management & Beyond)

## 1. Reason for Update

The original design document established a solid foundation for enabling field agents to add and update store data. However, it did not sufficiently address long-term data integrity, multi-user input, and controlled updates to the system of record.

As the feature scope evolved, it became clear that this system is not just a data entry tool, but the **authoritative source of truth for store and tank intelligence**. This requires a more structured approach to how data is created, modified, validated, and persisted.

This update refines the design to:

* Prevent accidental or unauthorized overwrites of critical data
* Support multiple user contributions without conflict
* Introduce a controlled approval workflow
* Ensure the system scales without data corruption or duplication

---

## 2. Commander’s Intent

Establish and maintain a single, authoritative source of truth for all store and tank data by enabling authenticated field agents to verify, correct, and expand existing records or create new ones when necessary. All changes must be submitted as proposed updates, requiring human confirmation and administrative approval before affecting canonical data. The system will prevent duplication, enforce consistent store identity, and preserve a complete audit trail while allowing contributors to view their own pending updates without compromising overall data integrity.

---

## 3. Key Design Changes

### 3.1 Separation of Canonical Data and Proposed Updates

**Change:**
Introduce a clear separation between approved store data and user-submitted changes.

* The existing `Store` model will represent **canonical, approved data only**
* A new structure (e.g., `StoreUpdate`) will capture **all user-submitted changes**

**Why:**
The original design allowed direct editing of store records, which creates risk of:

* Data corruption
* Conflicting edits
* Loss of historical context

This separation ensures:

* Canonical data remains stable and trusted
* Multiple users can submit updates simultaneously
* All changes are reviewable before being applied

### 3.2 Approval Workflow for Data Integrity

**Change:**
All modifications to store data must go through an approval process before updating the canonical record.

* Updates are created in a **pending state**
* Administrative users review and either:
  * Approve → apply changes to the `Store`
  * Reject → discard or archive the proposal

**Why:**
This enforces control over the system of record and ensures:

* Only verified data becomes authoritative
* Errors or bad submissions do not propagate
* Accountability is maintained for all changes

### 3.3 User-Specific Visibility of Pending Updates

**Change:**
Users who submit updates will be able to see their own proposed changes reflected in the UI, even if those changes are not yet approved.

**Why:**
This improves field usability by:

* Giving immediate feedback to the submitting agent
* Avoiding confusion about whether their update was recorded
* Allowing continued workflow without waiting for approval

At the same time, this does not impact other users or the canonical dataset.

### 3.4 Reinforced Store Identity and Duplication Prevention

**Change:**
Formalize store identity rules and duplication safeguards.

* Store Number / RISO serves as the primary logical identifier
* GPS proximity is used as a **secondary matching heuristic**
* System will:
  * Check for existing store numbers before creation
  * Warn users if a new store is within a defined proximity threshold of an existing one

**Why:**
The original design referenced proximity detection but did not define identity rules. Without this:

* Duplicate stores will emerge
* Data relationships (especially tanks) will fragment

This change ensures consistency and long-term reliability.

### 3.5 Scoped Separation into Dedicated Application Domain

**Change:**
Evolve this feature into a dedicated application domain (`siteintel`) rather than embedding it entirely within the existing tank-related system.

**Why:**
The scope now includes:

* Store metadata
* Geospatial validation
* Tank configuration
* Future expansion into notes, mapping overlays, and site intelligence

Separating this domain ensures:

* Clear ownership of responsibilities
* Maintainable architecture
* Scalability for future enhancements (Phase 2 and beyond)

---

## 4. Additional Implementation Clarifications

### 4.1 GPS and Proximity Handling

* A proximity threshold (initially ~250 feet) will be used to identify candidate stores
* Matches are **never automatically selected**
* Users must confirm whether a detected store is correct

This enforces human validation at critical decision points.

### 4.2 Tank Assignment Strategy (The Tank Picker)

To manage the high volume of existing tank charts and align with physical site hardware, the system utilizes a specialized selection process:

1.  **Fuel Type Selection:** User selects the product (Regular, Diesel, etc.).
2.  **Capacity Pulse:** User enters the approximate capacity observed on-site or from a chart.
3.  **Tolerance Search:** The system queries `TankType` records within a **+/- 10% tolerance** of the entered capacity.
4.  **Selection:** The user chooses the matching `TankType` from the filtered list.
5.  **Escape Hatch (Chart Missing):** If no matching chart is found, the user selects "CHART NOT FOUND."
    *   The system records the **Reported Capacity** and **Fuel Type** as an `UNVERIFIED` tank entry.
    *   This flags the site for administrative review to locate or create the missing tank chart.

### 4.3 Physical Tank Numbering & Swapping

To align with Veeder-Root and other ATG (Automatic Tank Gauge) systems:
*   **Tank Index:** Every tank mapping will include a **Physical Tank Number** (e.g., 1, 2, 3) as reported by the on-site machine.
*   **Manual Re-indexing:** The UI will allow users to manually adjust or "swap" these numbers. If the database order does not match the physical machine order, the agent can re-index the tanks directly to ensure the digital twin matches the physical reality.

### 4.4 Map Interaction (Phase 1 Scope)

* GPS coordinates captured on entry
* Map displayed with draggable marker for precision adjustment
* Coordinates updated after user interaction completes

Advanced mapping features (drawing tools, path overlays) are explicitly deferred to Phase 2.

### 4.5 Access Control

* Viewing store data may remain broadly accessible
* Creating or editing data requires authentication
* Approval capabilities are restricted to administrative users

### 4.6 Audit and Logging

* All proposed updates must be tracked with:
  * submitting user
  * timestamp
  * status (pending, approved, rejected)
* Approved changes should be traceable back to their originating update

This ensures full accountability and traceability.

---

## 5. Implementation Status (Current: Version 1.0.0)

### 5.1 Phase 1: COMPLETE
*   **Core Models:** `Location`, `LocationType`, `StoreUpdate`, and `TankUpdate` implemented.
*   **Canonical Linkage:** `tankgauge.Store` linked to `siteintel.Location`; `tank_index` added to mappings.
*   **Tactical UI:** 
    *   **Dashboard:** Centralized hub for site search and management.
    *   **Proposal Form:** AJAX-driven identification, GPS capture, and physical tank indexing.
    *   **Mapping:** Leaflet.js integration with CartoDB Dark Matter tiles and draggable markers.
    *   **Tank Picker:** +/- 10% tolerance search for matching tank charts.
*   **Approval Workflow:** Admin action "[ APPROVE & APPLY ]" for atomic data synchronization.

### 5.2 Phase 2: PLANNED
*   Introduction of additional location types (Fuel Racks, Yards).
*   Advanced mapping overlays and drawing tools.
*   Field intelligence notes expansion.

---

## 6. Summary

This update shifts the system from a simple CRUD interface to a **controlled data management platform**. The primary focus is now on preserving data integrity while enabling efficient field contributions.

Phase 1 will prioritize:

* Accurate store identification
* Safe update workflows
* Reliable tank mapping (with physical indexing)

Future phases will expand into richer site intelligence without compromising the integrity of the core dataset.

The system must remain disciplined: **no unverified data enters the source of truth without deliberate approval.**

---

## 6. Addendum: Expansion to Site Intelligence Architecture

### 6.1 Purpose of Addendum

This addendum introduces a forward-looking architectural adjustment to support future expansion of the system beyond store-only data management. While Phase 1 remains focused on building and maintaining the store database, it is necessary to establish a structural foundation that prevents fragmentation as additional operational locations are introduced.

The system is expected to expand to include:

* Fuel racks (supply/load points)
* Yards (parking/staging areas)
* Additional site types as operational needs evolve

This addendum ensures that expansion can occur without duplicating models, logic, or user interface patterns.

### 6.2 Core Concept: Site Intelligence Model

The system will evolve from a **store-centric model** to a broader **site intelligence model**, where all physical operational locations are treated as part of a unified structure.

A new foundational entity, referred to as **Location**, will represent any physical site relevant to operations.

Examples include:

* Stores (delivery destinations)
* Fuel racks (supply origins)
* Yards (vehicle staging areas)

All locations share common attributes such as:

* Geographic coordinates
* Name and identifying information
* General notes and field intelligence

### 6.3 Relationship to Existing Store Model

The existing `Store` model will remain in place and will be treated as a **specialized extension of Location**, not a separate or duplicated structure.

* `Location` will contain shared, cross-site data (e.g., GPS coordinates, address)
* `Store` will retain store-specific data (e.g., store number, tank relationships)

This approach allows:

* Preservation of existing data and logic
* Gradual migration of shared fields to a common layer
* Clean separation between general site data and store-specific details

### 6.4 Introduction of Location Classification

A classification mechanism (e.g., `LocationType`) will be introduced to distinguish between different kinds of sites.

Initial types include:

* Store
* Fuel Rack
* Yard

This classification will drive system behavior, allowing the application to conditionally display or enable features based on site type.

Examples:

* Stores → include tank configuration and delivery-related data
* Fuel racks → may include loading or supplier-related data (future)
* Yards → may include parking notes or layout information (future)

### 6.5 Behavior and UI Implications

The user interface will be structured around a **shared location view**, with conditional sections enabled based on location type.

* All locations will support:
  * Map visualization
  * GPS-based positioning
  * Notes and general intelligence
  * Update and approval workflows

* Type-specific features will be layered on top:
  * Tank management (Stores only, Phase 1)
  * Additional overlays and drawings (Phase 2)

This ensures consistency in user experience while allowing specialization where needed.

### 6.6 Phased Implementation Strategy

This architectural shift is **foundational but not blocking** for Phase 1.

#### Phase 1 (Current Focus)

* Maintain and improve the existing Store system
* Implement update/approval workflow
* Introduce Location model and link it to Store (non-breaking)
* Begin storing shared data at the Location level where practical

#### Phase 2 (Future Expansion)

* Introduce additional location types (Fuel Rack, Yard)
* Expand UI to support type-specific data
* Add advanced mapping features (e.g., overlays, drawn paths)

### 6.7 Design Principles Reinforced

This addendum reinforces the following principles:

* **Single Source of Truth:** All site data flows through a controlled, unified structure
* **No Structural Duplication:** Avoid creating parallel models with overlapping responsibilities
* **Incremental Evolution:** Introduce new architecture without breaking existing functionality
* **Type-Driven Behavior:** System capabilities are determined by classification, not hardcoded branching
* **Scalability:** The system must support additional site types without redesign

### 6.8 Summary

This addendum establishes a clear path from a store-focused system to a scalable site intelligence platform. By introducing a shared Location foundation and type-based behavior, the system can expand to support broader operational needs without sacrificing data integrity, maintainability, or development velocity.

Phase 1 execution remains focused and unchanged in scope, while this structure ensures future growth can occur cleanly and deliberately.
