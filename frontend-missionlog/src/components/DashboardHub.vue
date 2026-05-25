<template>
  <div class="dashboard-hub text-center">
    <div class="mb-5">
      <i class="fas fa-terminal fa-4x text-primary mb-3 pulse-tactical"></i>
      <h1 class="mono text-light display-6 font-weight-bold uppercase">
        MISSION <span class="text-primary">LOGS</span>
      </h1>
      <p class="mono text-muted-custom small">[ TACTICAL_HQ_DASHBOARD // VERSION_3.0 ]</p>
    </div>

    <!-- Active Mission Warning/Resume -->
    <div v-if="activeMission" class="card bg-dark-custom border-primary p-4 mb-4 text-center select-panel">
      <div class="mono text-primary small mb-2 blink-tactical">⚠️ ACTIVE MISSION IN PROGRESS</div>
      <h3 class="mono text-light h5 mb-3">MISSION INITIALIZED AT {{ formatTime(activeMission.shift_start) }}</h3>
      <p class="mono text-muted-custom small mb-4">Odometer Start: {{ activeMission.start_miles }} MI // Current Elapsed: {{ calculateElapsed(activeMission.shift_start) }}</p>
      
      <button @click="$emit('navigate', 'active')" class="btn btn-primary btn-tactical-lg mono fw-bold w-100">
        CONTINUE_ACTIVE_MISSION
      </button>
    </div>

    <!-- Hub Controls -->
    <div class="row g-4 justify-content-center">
      <!-- Start New Mission -->
      <div v-if="!activeMission" class="col-12 col-md-8">
        <div class="card bg-dark-custom border-secondary p-4 text-center">
          <div class="mono text-muted-custom small mb-4">[ MISSION_INITIALIZATION_PROTOCOL ]</div>
          
          <button @click="startNewMission" class="btn btn-primary btn-tactical-lg mono fw-bold w-100">
            START_NEW_SHIFT
          </button>
        </div>
      </div>

      <!-- General Options -->
      <div class="col-12 col-md-8 d-grid gap-3">
        <button v-if="activeMission" @click="$emit('navigate', 'active')" class="btn btn-outline-primary btn-tactical-lg mono fw-bold py-3 text-start">
          <i class="fas fa-play me-3"></i> 1. CONTINUE_CURRENT_SHIFT
        </button>

        <button @click="$emit('navigate', 'history')" class="btn btn-outline-warning btn-tactical-lg mono fw-bold py-3 text-start">
          <i class="fas fa-history me-3"></i> 2. EDIT_PREVIOUS_SHIFTS
        </button>
        
        <button class="btn btn-outline-secondary btn-tactical-lg mono fw-bold py-3 text-start disabled" style="opacity: 0.4;">
          <i class="fas fa-file-invoice me-3"></i> 3. GENERATE_REPORT [LOCKED]
        </button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';
import api from '../api';

export default defineComponent({
  name: 'DashboardHub',
  props: {
    activeMission: {
      type: Object,
      default: null
    }
  },
  emits: ['navigate', 'mission-started'],
  setup(_, { emit }) {
    const startMiles = ref<number | null>(null);

    const formatTime = (isoString: string) => {
      const d = new Date(isoString);
      const hours = String(d.getHours()).padStart(2, '0');
      const mins = String(d.getMinutes()).padStart(2, '0');
      return `${d.toLocaleDateString()} @ ${hours}${mins}L`;
    };

    const calculateElapsed = (isoString: string) => {
      const start = new Date(isoString).getTime();
      const elapsedMs = Date.now() - start;
      const hours = Math.floor(elapsedMs / 3600000);
      const minutes = Math.floor((elapsedMs % 3600000) / 60000);
      return `${hours}H ${minutes}M`;
    };

    const startNewMission = async () => {
      try {
        const response = await api.post('/missions/', {
          start_miles: startMiles.value || null
        });
        if (response.data.status === 'success') {
          emit('mission-started', response.data.mission);
          emit('navigate', 'active');
        }
      } catch (error: any) {
        alert(error.response?.data?.message || "Failed to initialize mission.");
      }
    };

    return {
      startMiles,
      formatTime,
      calculateElapsed,
      startNewMission
    };
  }
});
</script>

<style scoped>
.pulse-tactical {
  animation: pulse 2s infinite alternate;
}
@keyframes pulse {
  0% { text-shadow: 0 0 5px rgba(141, 163, 93, 0.4); }
  100% { text-shadow: 0 0 15px rgba(141, 163, 93, 0.9); }
}
.blink-tactical {
  animation: blinker 1.5s linear infinite;
}
@keyframes blinker {
  50% { opacity: 0.3; }
}
.select-panel {
  background-color: #171a1d !important;
  border-left: 4px solid var(--primary-color) !important;
}
</style>
