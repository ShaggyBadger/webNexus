<template>
  <div class="cargo-deliveries mb-5">
    <div class="mono text-muted-custom small mb-3 text-start">[ RETAIL_CARGO_DELIVERIES ]</div>
    
    <div v-if="deliveries.length === 0" class="mono text-muted-custom small py-3 border border-dashed mb-4 text-center">
      [ NO DELIVERIES RECORDED. PRESS 'ADD STORE DELIVERY' BELOW. ]
    </div>

    <div v-for="(deliv, dIdx) in deliveries" :key="dIdx" class="card bg-black-custom border-secondary p-3 mb-4 text-start">
      <div class="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-2">
        <span class="mono x-small text-warning fw-bold">DELIVERY #{{ String(dIdx + 1).padStart(2, '0') }}</span>
      </div>

      <!-- Store input with realtime async validation -->
      <div class="mb-3">
        <label class="form-label mono x-small text-primary fw-bold mb-1">STORE / RISO NUMBER</label>
        <input 
          type="text" 
          inputmode="numeric" 
          v-model="deliv.store_number_or_riso"
          @input="$emit('validate-store', dIdx)"
          class="tactical-input w-100 mono text-light"
          placeholder="e.g. 4022"
          :style="{ borderColor: deliv.storeValid === true ? '#8da35d' : (deliv.storeValid === false ? '#e94560' : '') }"
        />
        
        <!-- Validation status -->
        <div class="mt-1 d-flex align-items-center gap-2">
          <span v-if="deliv.loading" class="mono x-small text-muted-custom blink-tactical">[ VALIDATING_SITE... ]</span>
          <span v-else-if="deliv.storeValid === true" class="mono x-small text-primary fw-bold">✓ SECURE: {{ deliv.storeName }}</span>
          <span v-else-if="deliv.storeValid === false" class="mono x-small text-danger fw-bold">✗ HOSTILE: STORE NOT FOUND IN DATABASE</span>
          <span v-else class="mono x-small text-muted-custom">[ TYPE TO COMMENCE SECURE VALIDATION ]</span>
        </div>
      </div>

      <!-- Fuel Entries for this Store -->
      <div class="table-responsive mb-2">
        <table class="table table-sm table-bordered border-secondary bg-black-custom mono x-small text-light mb-0">
          <thead>
            <tr class="text-primary text-uppercase" style="font-size: 0.6rem;">
              <th class="py-1 px-2">FUEL_TYPE</th>
              <th class="py-1 px-2 text-center">VOLUME</th>
              <th class="py-1 px-2 text-end">ACT</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(fEntry, fIdx) in deliv.fuel_entries" :key="fIdx">
              <td class="py-0 px-0">
                <select v-model="fEntry.fuel_type_id" class="tactical-input-table w-100 border-0 py-2">
                  <option v-for="ft in fuelTypes" :key="ft.id" :value="ft.id">{{ ft.name }}</option>
                </select>
              </td>
              <td class="py-0 px-0">
                <input 
                  type="text" 
                  inputmode="numeric" 
                  v-model="fEntry.gallons"
                  class="tactical-input-table w-100 text-center border-0 py-2"
                  placeholder="GAL"
                />
              </td>
              <td class="py-2 px-2 text-end align-middle">
                <button 
                  type="button" 
                  @click="$emit('remove-fuel-entry', dIdx, fIdx)" 
                  class="btn btn-outline-danger btn-xs"
                  :disabled="deliv.fuel_entries.length <= 1"
                  style="min-height: auto; padding: 2px 6px;"
                >
                  ✗
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Add Fuel Type and Remove Store -->
      <div class="d-flex justify-content-between align-items-center mt-3 pt-2 border-top border-secondary">
        <button type="button" @click="$emit('remove-delivery', dIdx)" class="btn btn-outline-danger btn-xs mono">
          <i class="fas fa-trash-alt me-1"></i> DISCARD_SITE
        </button>
        <button type="button" @click="$emit('add-fuel-entry', dIdx)" class="btn btn-outline-primary btn-xs mono fw-bold">
          + ADD_FUEL_VARIANT
        </button>
      </div>
    </div>

    <!-- Add Delivery block -->
    <button type="button" @click="$emit('add-delivery')" class="btn btn-outline-warning w-100 mono fw-bold mb-4 py-3">
      + ADD STORE DELIVERY
    </button>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'CargoDeliveries',
  props: {
    deliveries: {
      type: Array as () => any[],
      required: true
    },
    fuelTypes: {
      type: Array as () => any[],
      required: true
    }
  },
  emits: ['validate-store', 'add-delivery', 'remove-delivery', 'add-fuel-entry', 'remove-fuel-entry']
});
</script>
