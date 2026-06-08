<template>
  <div class="dashboard-hub text-center">
    <div class="mb-5">
      <i class="fas fa-terminal fa-4x text-primary mb-3 pulse-tactical"></i>
      <h1 class="mono text-light display-6 font-weight-bold uppercase">
        MISSION <span class="text-primary">LOGS</span>
      </h1>
      <p class="mono text-muted-custom small">[ TACTICAL_HQ_DASHBOARD // VERSION_{{ version }} ]</p>
    </div>

    <!-- Active Mission Warning/Resume -->
    <div v-if="activeMission" class="card bg-dark-custom border-primary p-4 mb-4 text-center select-panel">
      <div class="mono text-primary small mb-2 blink-tactical">⚠️ ACTIVE_SHIFT_DETECTED</div>
      <h3 class="mono text-light h5 mb-3">OPERATIONAL_START: {{ formatTime(activeMission.shift_start) }}</h3>
      <p class="mono text-muted-custom small mb-4">MI_ODO_START: {{ activeMission.start_miles || '---' }} // ELAPSED_TIME: {{ calculateElapsed(activeMission.shift_start) }}</p>
      
      <button @click="$emit('navigate', 'active')" class="btn btn-primary btn-tactical-lg mono fw-bold w-100">
        RESUME_ACTIVE_SHIFT
      </button>
    </div>

    <!-- Hub Controls -->
    <div class="row g-4 justify-content-center">
      <div class="col-12 col-md-8 d-grid gap-3">
        <!-- Start New Mission (Visible if no active mission or as secondary option) -->
        <div class="card bg-dark-custom border-secondary p-4 text-center mb-2">
          <div v-if="!activeMission" class="mono text-muted-custom small mb-4">[ SHIFT_INITIALIZATION_PROTOCOL ]</div>
          <div v-else class="mono text-muted-custom x-small mb-4">[ START_NEW_MISSION_OVERRIDE ]</div>
          <button @click="$emit('navigate', 'active')" class="btn btn-outline-primary btn-tactical-lg mono fw-bold w-100">
            INITIALIZE_SHIFT
          </button>
        </div>

        <button @click="$emit('navigate', 'history')" class="btn btn-outline-warning btn-tactical-lg mono fw-bold py-3 text-center">
          <i class="fas fa-history me-3"></i> EDIT_PREVIOUS_SHIFTS
        </button>
        
        <button class="btn btn-outline-secondary btn-tactical-lg mono fw-bold py-3 text-center disabled" style="opacity: 0.4;">
          <i class="fas fa-file-invoice me-3"></i> GENERATE_REPORT [LOCKED]
        </button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
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
    const version = ref<string>('0.0.0');
    const startMiles = ref<number | null>(null);

    const fetchAgentInfo = async () => {
        try {
            const response = await api.get('/agent-info/');
            version.value = response.data.version;
        } catch (error) {
            console.error("Failed to fetch agent info");
        }
    };

    onMounted(fetchAgentInfo);

    const formatTime = (isoString: string) => {
      const d = new Date(isoString);
      const hours = String(d.getHours()).padStart(2, '0');
      const mins = String(d.getMinutes()).padStart(2, '0');
      return `${d.toLocaleDateString()} @ ${hours}${mins}L`;
    };

    const calculateElapsed = (isoString: string) => {
      if (!isoString) return '0H 0M';
      const start = new Date(isoString).getTime();
      if (isNaN(start)) return '0H 0M';
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
      version,
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
  0% { text-shadow: 0 0 5px rgba(255, 184, 108, 0.4); }
  100% { text-shadow: 0 0 15px rgba(255, 184, 108, 0.9); }
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
