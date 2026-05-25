<template>
  <div class="truck-fuel-logs card bg-dark-custom border-secondary p-4 mb-4">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h3 class="mono text-light h5 mb-0 fw-bold">
        <i class="fas fa-gas-pump text-primary me-2"></i> TRUCK FUEL PURCHASES
      </h3>
      <button 
        @click="showForm = !showForm" 
        class="btn btn-outline-primary btn-sm mono fw-bold"
      >
        {{ showForm ? 'HIDE_FORM' : 'ADD_FUEL_RECORD' }}
      </button>
    </div>

    <!-- Collapsible Form -->
    <div v-if="showForm" class="card bg-black-custom p-3 border border-secondary mb-3 text-start">
      <div class="row g-3">
        <div class="col-12 col-sm-6">
          <label class="form-label mono x-small text-muted-custom mb-1">GALLONS PUMPED</label>
          <input 
            v-model.number="gallons" 
            type="number" 
            step="0.01" 
            class="tactical-input w-100 mono text-light" 
            placeholder="0.00"
          />
        </div>
        <div class="col-12 col-sm-6">
          <label class="form-label mono x-small text-muted-custom mb-1">PRICE PER GALLON ($)</label>
          <input 
            v-model.number="price" 
            type="number" 
            step="0.001" 
            class="tactical-input w-100 mono text-light" 
            placeholder="0.000"
          />
        </div>
        <div class="col-12 text-end mt-3">
          <button 
            @click="submitFuelLog" 
            class="btn btn-primary btn-sm mono fw-bold"
            :disabled="!gallons || !price"
          >
            CONFIRM_PURCHASE
          </button>
        </div>
      </div>
    </div>

    <!-- Fuel Logs List -->
    <div v-if="fuelLogs.length > 0" class="table-responsive">
      <table class="table table-dark table-striped table-bordered mono small mb-0">
        <thead>
          <tr class="text-primary text-center">
            <th>GALLONS</th>
            <th>PRICE/GAL</th>
            <th>TOTAL COST</th>
            <th>ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in fuelLogs" :key="log.id" class="text-center align-middle">
            <td class="text-light">{{ log.gallons.toFixed(2) }} GAL</td>
            <td class="text-light">${{ log.price_per_gallon.toFixed(3) }}</td>
            <td class="text-light font-weight-bold">${{ (log.gallons * log.price_per_gallon).toFixed(2) }}</td>
            <td>
              <button 
                @click="deleteLog(log.id)" 
                class="btn btn-outline-danger btn-xs py-0 px-2 mono"
              >
                <i class="fas fa-trash-alt"></i> REMOVE
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="text-center py-3 bg-black-custom border border-secondary">
      <p class="mono text-muted-custom small mb-0">[ NO FUEL STOPS LOGGED FOR THIS MISSION ]</p>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';
import api from '../../api';

export default defineComponent({
  name: 'TruckFuelLogs',
  props: {
    missionId: {
      type: Number,
      required: true
    },
    fuelLogs: {
      type: Array as () => any[],
      required: true
    }
  },
  emits: ['refresh'],
  setup(props, { emit }) {
    const showForm = ref<boolean>(false);
    const gallons = ref<number | null>(null);
    const price = ref<number | null>(null);

    const submitFuelLog = async () => {
      if (!gallons.value || !price.value) return;
      try {
        const response = await api.post(`/missions/${props.missionId}/fuel-logs/`, {
          gallons: gallons.value,
          price_per_gallon: price.value
        });
        if (response.data.status === 'success') {
          gallons.value = null;
          price.value = null;
          showForm.value = false;
          emit('refresh');
        }
      } catch (error) {
        alert("Failed to submit truck fuel log.");
      }
    };

    const deleteLog = async (id: number) => {
      if (!confirm("Are you sure you want to delete this fuel purchase log?")) return;
      try {
        const response = await api.delete(`/fuel-logs/${id}/`);
        if (response.data.status === 'success') {
          emit('refresh');
        }
      } catch (error) {
        alert("Failed to delete fuel log.");
      }
    };

    return {
      showForm,
      gallons,
      price,
      submitFuelLog,
      deleteLog
    };
  }
});
</script>

<style scoped>
.bg-black-custom {
  background-color: #0b0d0f;
}
.btn-xs {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
}
</style>
