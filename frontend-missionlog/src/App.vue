<template>
  <div class="missionlog-spa py-5 px-3">
    <div class="container-fluid" style="max-width: 800px;">
      <!-- Navigation Command Bar -->
      <nav class="d-flex justify-content-between align-items-center mb-4 border border-secondary p-2 bg-black-custom">
        <div class="d-flex gap-2 align-items-center">
          <i class="fas fa-microchip text-primary"></i>
          <span class="mono text-light x-small fw-bold">[ CORE_SYS // AGENT: {{ agentName }} // STATUS: ONLINE ]</span>
        </div>
        <div class="d-flex gap-2">
          <button 
            @click="navigate('hub')" 
            class="btn btn-outline-primary btn-xs mono fw-bold"
            :class="{ active: currentView === 'hub' }"
          >
            LAUNCHER
          </button>
          <button 
            @click="navigate('history')" 
            class="btn btn-outline-primary btn-xs mono fw-bold"
            :class="{ active: currentView === 'history' }"
          >
            ARCHIVES
          </button>
          <a href="/" class="btn btn-outline-danger btn-xs mono fw-bold">
            EXIT_TO_HQ
          </a>
        </div>
      </nav>

      <!-- Global Spinner -->
      <div v-if="loadingGlobal" class="text-center py-5">
        <div class="spinner-border text-primary pulse-tactical mb-3" style="width: 3rem; height: 3rem;"></div>
        <div class="mono text-primary small blink-tactical">[ ESTABLISHING_COMMS_LINK ]</div>
      </div>

      <!-- Views Switcher -->
      <div v-else>
        <!-- Dashboard Hub View -->
        <DashboardHub 
          v-if="currentView === 'hub'" 
          :active-mission="activeMission"
          @navigate="navigate"
          @mission-started="onMissionStarted"
        />

        <!-- Active Mission View -->
        <div v-else-if="currentView === 'active' && currentMission" class="active-mission-view">
          <!-- Back button -->
          <div class="text-start mb-3">
            <button @click="navigate('hub')" class="btn btn-outline-secondary btn-sm mono fw-bold">
              <i class="fas fa-arrow-left me-2"></i> RETREAT_TO_LAUNCHER
            </button>
          </div>

          <!-- Top Header -->
          <ActiveHeader :mission="currentMission" />

          <!-- PHASE 01: PRE-MISSION PARAMETERS -->
          <div class="section-divider mb-4 mt-5">
            <div class="divider-line"></div>
            <div class="divider-text mono uppercase">PHASE 01 // PARAMETERS</div>
            <div class="divider-line"></div>
          </div>

          <!-- TOP BLOCK: MISSION_PARAMETERS (Time & Start Odo) -->
          <div class="card bg-dark-custom border-secondary p-4 mb-4 text-center">
            <div class="mono text-muted-custom small mb-3">[ MISSION_PARAMETERS_INITIALIZATION ]</div>
            <div class="row g-3 justify-content-center">
              <div class="col-12 col-md-6">
                <label class="form-label mono x-small text-primary fw-bold mb-1">SHIFT START TIME (ADJUSTABLE)</label>
                <input 
                  type="datetime-local" 
                  v-model="startTimeAdjust"
                  class="tactical-input w-100 mono text-light text-center"
                />
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label mono x-small text-primary fw-bold mb-1">STARTING ODOMETER (MILES)</label>
                <input 
                  v-model.number="currentMission.start_miles" 
                  type="number" 
                  class="tactical-input w-100 mono text-light text-center" 
                  placeholder="0"
                />
              </div>
              <div class="col-12 mt-3">
                <button @click="saveMissionMetrics" class="btn btn-outline-primary btn-sm mono fw-bold px-5">
                  SAVE_PARAMETERS
                </button>
              </div>
            </div>
          </div>

          <!-- PHASE 02: FIELD OPERATIONS -->
          <div class="section-divider mb-4 mt-5">
            <div class="divider-line"></div>
            <div class="divider-text mono uppercase">PHASE 02 // OPERATIONS</div>
            <div class="divider-line"></div>
          </div>

          <!-- Truck Fuel Logs Panel -->
          <TruckFuelLogs 
            :mission-id="currentMission.id" 
            :fuel-logs="currentMission.fuel_logs"
            @refresh="refreshActiveMission"
          />

          <!-- POs and Loads Deck -->
          <PurchaseOrders 
            :mission-id="currentMission.id"
            :order-numbers="currentMission.order_numbers"
            :stores="stores"
            :fuel-types="fuelTypes"
            @refresh="refreshActiveMission"
          />

          <!-- PHASE 03: POST-MISSION DEBRIEF -->
          <div class="section-divider mb-4 mt-5">
            <div class="divider-line"></div>
            <div class="divider-text mono uppercase">PHASE 03 // DEBRIEF</div>
            <div class="divider-line"></div>
          </div>

          <!-- Checkout / Debrief Console -->
          <div class="card bg-dark-custom border-secondary p-4 text-center mb-5">
            <div class="mono text-muted-custom small mb-4">[ MISSION_DEBRIEF_DECK ]</div>
            
            <div class="row g-4 justify-content-center">
              <!-- MILEAGE SECTION -->
              <div class="col-12 col-md-4">
                <label class="form-label mono x-small text-primary fw-bold mb-2">ENDING ODOMETER (MILES)</label>
                <input 
                  v-model.number="endMiles" 
                  @input="onEndMilesChange"
                  type="number" 
                  class="tactical-input w-100 mono text-light text-center" 
                  placeholder="0"
                />
              </div>

              <div class="col-12 col-md-4">
                <label class="form-label mono x-small text-primary fw-bold mb-2">TOTAL MILES TRAVELED</label>
                <input 
                  v-model.number="totalMiles" 
                  @input="onTotalMilesChange"
                  type="number" 
                  class="tactical-input w-100 mono text-light text-center" 
                  placeholder="0"
                />
              </div>

              <!-- HOURS SECTION -->
              <div class="col-12 col-md-4">
                <label class="form-label mono x-small text-warning fw-bold mb-2">TOTAL HOURS (FROM LOGS)</label>
                <input 
                  v-model.number="hoursOnDuty" 
                  type="number" 
                  step="0.01"
                  class="tactical-input w-100 mono text-light border-warning-custom text-center" 
                  placeholder="0.00"
                />
              </div>

              <!-- General Debrief Notes -->
              <div class="col-12 mt-3">
                <label class="form-label mono small text-muted-custom mb-2">OPERATIONAL NOTES / FIELD OBSERVATIONS</label>
                <textarea 
                  v-model="notes" 
                  rows="3" 
                  class="tactical-input w-100 mono text-light text-center" 
                  placeholder="SITE QUIRKS, MANIFOLD DEFECTS, TRAFFIC..."
                ></textarea>
              </div>

              <!-- Terminate active/Unsaved (Delete shift) -->
              <div class="col-12 d-flex flex-column flex-md-row justify-content-center align-items-center gap-3 mt-4">
                <button
                  @click="saveFinalDebrief" 
                  class="btn btn-primary btn-tactical mono fw-bold px-5 order-first order-md-1"
                >
                  {{ currentMission.is_completed ? 'SAVE_CHANGES' : 'DECLARE_MISSION_COMPLETE' }}
                </button>

                <!-- Confirmation UI -->
                <div v-if="showConfirmSignOff" class="card bg-black-custom p-3 border border-warning">
                  <p class="mono text-warning mb-2">ARE YOU SURE? THIS ACTION FINALIZES ALL LOGS.</p>
                  <div class="d-flex gap-2 justify-content-center">
                    <button @click="confirmSignOff" class="btn btn-warning mono fw-bold">CONFIRM_SIGN_OFF</button>
                    <button @click="showConfirmSignOff = false" class="btn btn-outline-secondary mono">CANCEL</button>
                  </div>
                </div>
                <button 
                  v-if="currentMission.is_completed" 
                  @click="exitAudits" 
                  class="btn btn-outline-secondary btn-tactical mono fw-bold px-4 order-md-2"
                >
                  CLOSE_AUDIT
                </button>

                <button 
                  v-if="!showConfirmAbort"
                  @click="abortMission" 
                  class="btn btn-outline-danger btn-sm mono fw-bold px-4 order-last order-md-0"
                >
                  {{ currentMission.is_completed ? 'DELETE_PERMANENTLY' : 'ABORT_MISSION (DELETE)' }}
                </button>
                <div v-else class="card bg-black-custom p-3 border border-danger">
                  <p class="mono text-danger mb-2">CRITICAL: PERMANENTLY DELETE MISSION DATA?</p>
                  <div class="d-flex gap-2 justify-content-center">
                    <button @click="confirmAbortMission" class="btn btn-danger mono fw-bold">CONFIRM_ABORT</button>
                    <button @click="showConfirmAbort = false" class="btn btn-outline-secondary mono">CANCEL</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Historical Archive View -->
        <MissionHistory 
          v-else-if="currentView === 'history'" 
          :missions="historicalMissions"
          @navigate="navigate"
          @select-mission="auditHistoricalMission"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import api from './api';

import DashboardHub from './components/DashboardHub.vue';
import ActiveHeader from './components/ActiveMission/ActiveHeader.vue';
import TruckFuelLogs from './components/ActiveMission/TruckFuelLogs.vue';
import PurchaseOrders from './components/ActiveMission/PurchaseOrders.vue';
import MissionHistory from './components/History/MissionHistory.vue';

export default defineComponent({
  name: 'App',
  components: {
    DashboardHub,
    ActiveHeader,
    TruckFuelLogs,
    PurchaseOrders,
    MissionHistory
  },
  setup() {
    const currentView = ref<string>('hub');
    const loadingGlobal = ref<boolean>(true);
    const agentName = ref<string>('RECOGNIZING...');

    // Lists
    const stores = ref<any[]>([]);
    const fuelTypes = ref<any[]>([]);
    const historicalMissions = ref<any[]>([]);

    // State missions
    const activeMission = ref<any | null>(null);
    const currentMission = ref<any | null>(null);

    // Form inputs (checkout)
    const endMiles = ref<number | null>(null);
    const totalMiles = ref<number | null>(null);
    const hoursOnDuty = ref<number | null>(null);
    const startTimeAdjust = ref<string>('');
    const notes = ref<string>('');

    const navigate = (view: string) => {
      currentView.value = view;
      if (view === 'hub') {
        refreshActiveMissionState();
      } else if (view === 'history') {
        refreshHistoricalMissions();
      }
    };

    const fetchAgentInfo = async () => {
      try {
        const response = await api.get('/agent-info/');
        agentName.value = response.data.callsign || response.data.username.toUpperCase();
      } catch (error) {
        agentName.value = 'UNKNOWN_ENTITY';
      }
    };

    const loadCoreData = async () => {
      try {
        // Fetch Stores
        const storesResp = await api.get('/stores/');
        stores.value = storesResp.data;

        // Fetch Fuel Types
        const fuelResp = await api.get('/fuel-types/');
        fuelTypes.value = fuelResp.data;
      } catch (error) {
        console.error("Failed to load stores or fuel types initializer.", error);
      }
    };

    const refreshActiveMissionState = async () => {
      try {
        const response = await api.get('/missions/active/');
        if (response.data.active) {
          syncMissionState(response.data.mission);
        } else {
          activeMission.value = null;
          currentMission.value = null;
        }
      } catch (error) {
        console.error("Failed to check active mission state.", error);
      }
    };

    const syncMissionState = (mission: any) => {
      activeMission.value = mission;
      currentMission.value = mission;
      notes.value = mission.notes || '';
      endMiles.value = mission.end_miles || null;
      hoursOnDuty.value = mission.hours_on_duty || null;
      
      // Calculate total miles from current start/end
      if (mission.start_miles !== null && mission.end_miles !== null) {
        totalMiles.value = mission.end_miles - mission.start_miles;
      } else {
        totalMiles.value = null;
      }

      // Sync start time adjust (local ISO)
      if (mission.shift_start) {
        const d = new Date(mission.shift_start);
        const offset = d.getTimezoneOffset() * 60000;
        const localIso = new Date(d.getTime() - offset).toISOString().slice(0, 16);
        startTimeAdjust.value = localIso;
      }
    };

    const refreshActiveMission = async () => {
      if (!currentMission.value) return;
      try {
        const response = await api.get(`/missions/${currentMission.value.id}/`);
        syncMissionState(response.data);
      } catch (error) {
        console.error("Failed to refresh active mission payload.", error);
      }
    };

    const refreshHistoricalMissions = async () => {
      try {
        const response = await api.get('/missions/');
        historicalMissions.value = response.data;
      } catch (error) {
        console.error("Failed to query historical archives.", error);
      }
    };

    const onMissionStarted = (mission: any) => {
      syncMissionState(mission);
    };

    const onEndMilesChange = () => {
      if (currentMission.value && currentMission.value.start_miles !== null && endMiles.value !== null) {
        totalMiles.value = endMiles.value - currentMission.value.start_miles;
      }
    };

    const onTotalMilesChange = () => {
      if (!currentMission.value) return;
      if (totalMiles.value !== null) {
        if (currentMission.value.start_miles !== null) {
          // Adjust end miles to match total
          endMiles.value = currentMission.value.start_miles + totalMiles.value;
        } else if (endMiles.value !== null) {
          // Adjust start miles to match total
          currentMission.value.start_miles = endMiles.value - totalMiles.value;
        }
      }
    };

    const saveMissionMetrics = async () => {
      if (!currentMission.value) return;
      try {
        await api.put(`/missions/${currentMission.value.id}/`, {
          start_miles: currentMission.value.start_miles,
          shift_start: new Date(startTimeAdjust.value).toISOString()
        });
        alert("Mission parameters updated successfully.");
        refreshActiveMission();
      } catch (error) {
        alert("Failed to save parameters.");
      }
    };

    const showConfirmSignOff = ref<boolean>(false);
    const showConfirmAbort = ref<boolean>(false);

    const saveFinalDebrief = async () => {
      if (!currentMission.value) return;

      const payload = {
        end_miles: endMiles.value,
        notes: notes.value,
        hours_on_duty: hoursOnDuty.value
      };

      if (currentMission.value.is_completed) {
        try {
          await api.put(`/missions/${currentMission.value.id}/`, payload);
          refreshActiveMission();
        } catch (error) {
          // Inline error
        }
        return;
      }

      showConfirmSignOff.value = true;
    };

    const confirmSignOff = async () => {
        if (!currentMission.value) return;

        const payload = {
            end_miles: endMiles.value,
            notes: notes.value,
            hours_on_duty: hoursOnDuty.value
        };

        try {
            const response = await api.post(`/missions/${currentMission.value.id}/complete/`, payload);
            if (response.data.status === 'success') {
                activeMission.value = null;
                currentMission.value = null;
                showConfirmSignOff.value = false;
                navigate('hub');
            }
        } catch (error) {
            // Inline error feedback
        }
    };

    const abortMission = async () => {
      if (!currentMission.value) return;
      showConfirmAbort.value = true;
    };

    const confirmAbortMission = async () => {
      if (!currentMission.value) return;
      try {
        await api.delete(`/missions/${currentMission.value.id}/`);
        activeMission.value = null;
        currentMission.value = null;
        showConfirmAbort.value = false;
        navigate('hub');
      } catch (error) {
        // Inline error
      }
    };
    const auditHistoricalMission = (mission: any) => {
      syncMissionState(mission);
      currentView.value = 'active';
    };

    const exitAudits = () => {
      currentMission.value = null;
      navigate('history');
    };

    onMounted(async () => {
      loadingGlobal.value = true;
      await fetchAgentInfo();
      await loadCoreData();
      await refreshActiveMissionState();
      loadingGlobal.value = false;
    });

    return {
      currentView,
      loadingGlobal,
      agentName,
      stores,
      fuelTypes,
      historicalMissions,
      activeMission,
      currentMission,
      endMiles,
      totalMiles,
      hoursOnDuty,
      startTimeAdjust,
      notes,
      navigate,
      onMissionStarted,
      onEndMilesChange,
      onTotalMilesChange,
      refreshActiveMission,
      saveMissionMetrics,
      saveFinalDebrief,
      showConfirmSignOff,
      confirmSignOff,
      showConfirmAbort,
      abortMission,
      confirmAbortMission,
      auditHistoricalMission,
      exitAudits
    };
  }
});
</script>

<style>
/* Base Camp CSS Style Overrides */
:root {
  --bg-color: #121417;
  --bg-card: #1c1f23;
  --primary-color: #8da35d;
  --accent-color: #e94560;
  --navbar-border: #2d3139;
  --muted-text-color: #9ea8b6;
}

body {
  background-color: var(--bg-color) !important;
  color: #f8f9fa !important;
}

.bg-dark-custom {
  background-color: var(--bg-card) !important;
}

.bg-black-custom {
  background-color: #0b0d0f !important;
}

.text-primary {
  color: var(--primary-color) !important;
}

.text-warning {
  color: #ffb86c !important;
}

.text-muted-custom {
  color: var(--muted-text-color) !important;
  opacity: 0.85;
}

.border-primary {
  border-color: var(--primary-color) !important;
}

.border-secondary {
  border-color: var(--navbar-border) !important;
}

.tactical-input {
  background-color: #0b0d0f !important;
  color: white !important;
  border: 1px solid var(--navbar-border) !important;
  border-radius: 0 !important;
  font-family: "JetBrains Mono", monospace !important;
  padding: 0.75rem 1rem !important;
}

.tactical-input:focus {
  border-color: var(--primary-color) !important;
  box-shadow: 0 0 10px rgba(141, 163, 93, 0.2) !important;
  outline: none;
}

.btn-tactical-lg {
  border-radius: 0 !important;
  padding: 1rem 1.5rem !important;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.btn-tactical {
  border-radius: 0 !important;
  padding: 0.65rem 1.25rem !important;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.btn-primary {
  background-color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
  color: #121417 !important;
}

.btn-primary:hover, .btn-primary:active, .btn-primary:focus {
  background-color: #798d4d !important;
  border-color: #798d4d !important;
}

.btn-outline-primary {
  color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
}

.btn-outline-primary:hover, .btn-outline-primary:active, .btn-outline-primary.active {
  background-color: var(--primary-color) !important;
  color: #121417 !important;
}

.btn-outline-secondary {
  color: var(--muted-text-color) !important;
  border-color: var(--navbar-border) !important;
}

.btn-outline-secondary:hover {
  background-color: rgba(255,255,255,0.05) !important;
  color: white !important;
}

.btn-outline-warning {
  color: #ffb86c !important;
  border-color: #ffb86c !important;
}

.btn-outline-warning:hover {
  background-color: #ffb86c !important;
  color: #121417 !important;
}

.btn-outline-danger {
  color: var(--accent-color) !important;
  border-color: var(--accent-color) !important;
}

.btn-outline-danger:hover {
  background-color: var(--accent-color) !important;
  color: white !important;
}

.btn-xs {
  font-size: 0.7rem;
  padding: 0.25rem 0.6rem;
  border-radius: 0;
}

.mono {
  font-family: "JetBrains Mono", monospace !important;
}

.x-small {
  font-size: 0.75rem;
}

.uppercase {
  text-transform: uppercase;
}

/* --- MOBILE FIRST TOUCH OPTIMIZATIONS --- */
@media (max-width: 768px) {
  .btn:not(.btn-xs) {
    min-height: 52px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
  }

  .tactical-input {
    min-height: 52px;
    font-size: 1rem !important; /* Prevents iOS zoom on focus */
  }

  .btn-xs {
    min-height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .container-fluid {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }

  nav .btn-xs {
    padding: 0.5rem 0.8rem !important;
    font-size: 0.65rem !important;
  }
}

/* --- TACTICAL SECTION DIVIDERS --- */
.section-divider {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 5rem !important; /* Significant vertical separation */
  margin-bottom: 2.5rem !important;
}

.divider-line {
  flex-grow: 1;
  height: 1px;
  background-color: var(--navbar-border);
  opacity: 0.3;
}

.divider-text {
  font-size: 0.8rem;
  color: var(--primary-color);
  letter-spacing: 3px;
  white-space: nowrap;
  background-color: #0b0d0f;
  padding: 0.5rem 1.5rem;
  border: 1px solid var(--navbar-border);
  box-shadow: 0 0 15px rgba(141, 163, 93, 0.1);
}

.card {
  margin-bottom: 2rem !important;
}
</style>
