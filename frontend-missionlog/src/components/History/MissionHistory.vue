<template>
  <div class="mission-history text-start">
    <!-- Header -->
    <div class="mb-5 text-center">
      <i class="fas fa-history fa-4x text-warning mb-3"></i>
      <h1 class="mono text-light display-6 font-weight-bold uppercase">
        MISSION <span class="text-warning">ARCHIVES</span>
      </h1>
      <p class="mono text-muted-custom small">[ RETROACTIVE_AUDITING_CENTER // COMPLETED_LOGS ]</p>
    </div>

    <!-- Toolbar Filters -->
    <div class="card bg-dark-custom border-secondary p-3 mb-4">
      <div class="row align-items-center g-3">
        <div class="col-12 col-md-8">
          <label class="form-label mono x-small text-muted-custom mb-1">FILTER BY DATE RANGE</label>
          <div class="d-flex gap-2 align-items-center">
            <input v-model="startDate" type="date" class="tactical-input w-100 mono text-light" />
            <span class="mono text-muted-custom small">TO</span>
            <input v-model="endDate" type="date" class="tactical-input w-100 mono text-light" />
          </div>
        </div>
        <div class="col-12 col-md-4 text-md-end pt-3">
          <button @click="clearFilters" class="btn btn-outline-secondary btn-sm mono fw-bold w-100 py-2">
            RESET_FILTERS
          </button>
        </div>
      </div>
    </div>

    <!-- Archive Deck -->
    <div v-if="filteredMissions.length > 0" class="d-flex flex-column gap-3">
      <div 
        v-for="m in filteredMissions" 
        :key="m.id" 
        class="card bg-dark-custom border-secondary p-4 tactical-card d-flex flex-column"
      >
        <div class="row align-items-center g-3">
          <div class="col-12 col-md-8">
            <div class="mono text-warning small fw-bold mb-1">[ MISSION_ARCHIVE_ID: #{{ String(m.id).padStart(5, '0') }} ]</div>
            <h3 class="mono text-light h5 mb-2 fw-bold">DEPLOYED: {{ formatTime(m.shift_start) }}</h3>
            <div class="d-flex flex-wrap gap-3 mt-2">
              <span class="mono x-small text-muted-custom bg-black-custom px-2 py-1 border border-secondary">
                DISTANCE: {{ m.total_miles || 0 }} MILES
              </span>
              <span class="mono x-small text-muted-custom bg-black-custom px-2 py-1 border border-secondary">
                STOPS: {{ m.total_stops || 0 }} LOGGED
              </span>
              <span class="mono x-small text-muted-custom bg-black-custom px-2 py-1 border border-secondary">
                ON_DUTY: {{ m.hours_on_duty || 0.0 }} HOURS
              </span>
              <span v-if="m.notes" class="mono x-small text-muted-custom bg-black-custom px-2 py-1 border border-secondary text-truncate" style="max-width: 250px;">
                NOTE: {{ m.notes }}
              </span>
            </div>
          </div>
          <div class="col-12 col-md-4 text-md-end">
            <button @click="$emit('select-mission', m)" class="btn btn-primary btn-tactical mono fw-bold px-4">
              AUDIT_RECORDS
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Empty State -->
    <div v-else class="text-center py-5 bg-black-custom border border-secondary">
      <i class="fas fa-box-open fa-3x text-muted-custom mb-3 opacity-25"></i>
      <p class="mono text-muted-custom small mb-0">[ NO COMPLETED MISSION LOGS RESOLVED IN THIS RANGE ]</p>
    </div>

    <!-- Back to Hub -->
    <div class="mt-4">
      <button @click="$emit('navigate', 'hub')" class="btn btn-outline-secondary btn-tactical-lg mono fw-bold">
        RETURN_TO_HQ
      </button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue';

export default defineComponent({
  name: 'MissionHistory',
  props: {
    missions: {
      type: Array as () => any[],
      required: true
    }
  },
  emits: ['navigate', 'select-mission'],
  setup(props) {
    const startDate = ref<string>('');
    const endDate = ref<string>('');

    const formatTime = (isoString: string) => {
      const d = new Date(isoString);
      const hours = String(d.getHours()).padStart(2, '0');
      const mins = String(d.getMinutes()).padStart(2, '0');
      return `${d.toLocaleDateString()} @ ${hours}${mins}L`;
    };

    const clearFilters = () => {
      startDate.value = '';
      endDate.value = '';
    };

    const filteredMissions = computed(() => {
      // Filter out only completed missions
      let list = props.missions.filter(m => m.is_completed);

      if (startDate.value) {
        const start = new Date(startDate.value).getTime();
        list = list.filter(m => new Date(m.shift_start).getTime() >= start);
      }
      if (endDate.value) {
        // End of the selected day
        const end = new Date(endDate.value).getTime() + 86400000;
        list = list.filter(m => new Date(m.shift_start).getTime() <= end);
      }

      return list;
    });

    return {
      startDate,
      endDate,
      formatTime,
      clearFilters,
      filteredMissions
    };
  }
});
</script>

<style scoped>
.bg-black-custom {
  background-color: #0b0d0f;
}
.tactical-card {
  background-color: #171a1d !important;
  border-left: 4px solid var(--accent-color) !important;
  transition: background-color 0.2s ease;
}
.tactical-card:hover {
  background-color: #1c1f23 !important;
}
</style>
