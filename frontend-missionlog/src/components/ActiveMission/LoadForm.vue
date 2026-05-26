<template>
  <div class="load-form card bg-black-custom border-secondary p-3 mb-3 text-start">
    <div class="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-2">
      <div class="mono text-light small fw-bold">
        <i class="fas fa-truck-loading text-primary me-2"></i> LOAD RECORD // #{{ load.id ? 'ID_' + load.id : 'NEW_ENTRY' }}
      </div>
      <button @click="deleteLoad" class="btn btn-outline-danger btn-xs mono">
        <i class="fas fa-trash-alt"></i> REMOVE
      </button>
    </div>

    <div class="row g-3">
      <!-- Store Autocomplete -->
      <div class="col-12 col-md-6">
        <label class="form-label mono x-small text-muted-custom mb-1">STORE TARGET *</label>
        <select 
          v-model="storeId" 
          @change="onStoreChange"
          class="tactical-input w-100 mono text-light"
        >
          <option :value="null">-- SELECT STORE --</option>
          <option v-for="s in stores" :key="s.id" :value="s.id">
            {{ s.store_num }} - {{ s.store_name }}
          </option>
        </select>
      </div>

      <!-- Fuel Type Selection -->
      <div class="col-12 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">FUEL CLASSIFICATION *</label>
        <select 
          v-model="fuelTypeId" 
          @change="onFuelTypeChange"
          class="tactical-input w-100 mono text-light"
        >
          <option :value="null">-- SELECT FUEL --</option>
          <option v-for="f in fuelTypes" :key="f.id" :value="f.id">
            {{ f.name }}
          </option>
        </select>
      </div>

      <!-- Pump Price -->
      <div class="col-12 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">PUMP PRICE ($) *</label>
        <input 
          v-model.number="priceAtStore" 
          type="number" 
          step="0.01" 
          class="tactical-input w-100 mono text-light" 
          placeholder="0.00"
        />
      </div>

      <!-- Divider -->
      <div class="col-12 border-bottom border-secondary my-3 opacity-25"></div>

      <!-- BOL Data Title -->
      <div class="col-12">
        <span class="mono x-small text-primary fw-bold">[ BILL_OF_LADEN_INTEL ]</span>
      </div>

      <!-- BOL Gross -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">GROSS GALLONS *</label>
        <input 
          v-model.number="grossGal" 
          type="number" 
          class="tactical-input w-100 mono text-light" 
          placeholder="0"
        />
      </div>

      <!-- BOL Net -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">NET GALLONS *</label>
        <input 
          v-model.number="netGal" 
          type="number" 
          class="tactical-input w-100 mono text-light" 
          placeholder="0"
        />
      </div>

      <!-- BOL Temp -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">TEMPERATURE (F) *</label>
        <input 
          v-model.number="temp" 
          type="number" 
          step="0.1" 
          class="tactical-input w-100 mono text-light" 
          placeholder="60.0"
        />
      </div>

      <!-- BOL Grav -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">SPECIFIC GRAVITY (GRAV) *</label>
        <input 
          v-model.number="grav" 
          type="number" 
          step="0.1" 
          class="tactical-input w-100 mono text-light" 
          placeholder="45.0"
        />
      </div>

      <!-- Divider -->
      <div class="col-12 border-bottom border-secondary my-3 opacity-25"></div>

      <!-- Store Tank Status Title -->
      <div class="col-12">
        <span class="mono x-small text-primary fw-bold">[ STORE_TANK_DYNAMICS ]</span>
      </div>

      <!-- Opening Inches -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">START INCHES *</label>
        <input 
          v-model.number="startInches" 
          @input="onStartInchesChange"
          type="number" 
          step="0.01" 
          class="tactical-input w-100 mono text-light" 
          placeholder="0.00"
        />
      </div>

      <!-- Opening Gallons -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">START GALLONS *</label>
        <div class="position-relative">
          <input 
            v-model.number="startGallons" 
            type="number" 
            class="tactical-input w-100 mono text-light" 
            placeholder="0"
          />
          <span v-if="loadingStartChart" class="position-absolute end-0 top-50 translate-middle-y me-2 spinner-border spinner-border-sm text-primary"></span>
        </div>
      </div>

      <!-- Closing Inches -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">END INCHES *</label>
        <input 
          v-model.number="endInches" 
          @input="onEndInchesChange"
          type="number" 
          step="0.01" 
          class="tactical-input w-100 mono text-light" 
          placeholder="0.00"
        />
      </div>

      <!-- Closing Gallons -->
      <div class="col-6 col-md-3">
        <label class="form-label mono x-small text-muted-custom mb-1">END GALLONS *</label>
        <div class="position-relative">
          <input 
            v-model.number="endGallons" 
            type="number" 
            class="tactical-input w-100 mono text-light" 
            placeholder="0"
          />
          <span v-if="loadingEndChart" class="position-absolute end-0 top-50 translate-middle-y me-2 spinner-border spinner-border-sm text-primary"></span>
        </div>
      </div>

      <!-- Save Indicator / Form actions -->
      <div class="col-12 text-end mt-4">
        <span v-if="isDirty" class="mono x-small text-warning me-3 blink-tactical">💾 DATA MODIFIED // NOT SAVED</span>
        <button 
          @click="saveLoad" 
          class="btn btn-primary btn-sm mono fw-bold px-4"
          :disabled="!isValid"
        >
          {{ load.id ? 'UPDATE_RECORD' : 'LOG_LOAD' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, watch } from 'vue';
import api from '../../api';

export default defineComponent({
  name: 'LoadForm',
  props: {
    load: {
      type: Object,
      required: true
    },
    poId: {
      type: Number,
      required: true
    },
    stores: {
      type: Array as () => any[],
      required: true
    },
    fuelTypes: {
      type: Array as () => any[],
      required: true
    }
  },
  emits: ['refresh'],
  setup(props, { emit }) {
    // Reactive Form values
    const storeId = ref<number | null>(props.load.store_id || null);
    const fuelTypeId = ref<number | null>(props.load.fuel_type_id || null);
    const priceAtStore = ref<number | null>(props.load.price_at_store || null);
    const grossGal = ref<number | null>(props.load.gross_gal || null);
    const netGal = ref<number | null>(props.load.net_gal || null);
    const temp = ref<number>(props.load.temp || 60.0);
    const grav = ref<number>(props.load.grav || 45.0);
    
    const startInches = ref<number | null>(props.load.start_inches || null);
    const startGallons = ref<number | null>(props.load.start_gallons || null);
    const endInches = ref<number | null>(props.load.end_inches || null);
    const endGallons = ref<number | null>(props.load.end_gallons || null);

    const loadingStartChart = ref<boolean>(false);
    const loadingEndChart = ref<boolean>(false);

    // Watch for parent prop updates (important for lists)
    watch(() => props.load, (newVal) => {
      storeId.value = newVal.store_id || null;
      fuelTypeId.value = newVal.fuel_type_id || null;
      priceAtStore.value = newVal.price_at_store || null;
      grossGal.value = newVal.gross_gal || null;
      netGal.value = newVal.net_gal || null;
      temp.value = newVal.temp || 60.0;
      grav.value = newVal.grav || 45.0;
      startInches.value = newVal.start_inches || null;
      startGallons.value = newVal.start_gallons || null;
      endInches.value = newVal.end_inches || null;
      endGallons.value = newVal.end_gallons || null;
    }, { deep: true });

    // Computed Properties
    const selectedFuelTypeName = computed(() => {
      const ft = props.fuelTypes.find(f => f.id === fuelTypeId.value);
      return ft ? ft.name : '';
    });

    const isDirty = computed(() => {
      return storeId.value !== (props.load.store_id || null) ||
             fuelTypeId.value !== (props.load.fuel_type_id || null) ||
             priceAtStore.value !== (props.load.price_at_store || null) ||
             grossGal.value !== (props.load.gross_gal || null) ||
             netGal.value !== (props.load.net_gal || null) ||
             temp.value !== (props.load.temp || 60.0) ||
             grav.value !== (props.load.grav || 45.0) ||
             startInches.value !== (props.load.start_inches || null) ||
             startGallons.value !== (props.load.start_gallons || null) ||
             endInches.value !== (props.load.end_inches || null) ||
             endGallons.value !== (props.load.end_gallons || null);
    });

    const isValid = computed(() => {
      // Only Fuel Type is strictly required to initialize the record
      return fuelTypeId.value !== null;
    });

    // Automatically calculate expected end gallons based on start + gross
    watch([startGallons, grossGal], ([newStartGallons, newGrossGal]) => {
      if (newStartGallons !== null && newGrossGal !== null) {
        // Calculate total expected end volume
        const calculatedEndGallons = newStartGallons + newGrossGal;
        
        // Update the reactive endGallons
        endGallons.value = calculatedEndGallons;
        
        // Trigger reverse inches lookup
        triggerCalibrations('endGallons');
      }
    });

    // Event Handlers
    const onStoreChange = () => {
      triggerCalibrations();
    };

    const onFuelTypeChange = () => {
      triggerCalibrations();
    };

    const triggerCalibrations = async (targetField?: 'startInches' | 'endGallons') => {
      if (!storeId.value || !selectedFuelTypeName.value) return;
      
      const params: any = {
        store_id: storeId.value,
        fuel_type: selectedFuelTypeName.value
      };
      
      if (startInches.value !== null && !isNaN(startInches.value)) params.start_inches = startInches.value;
      
      // If we are specifically calculating end inches based on gallons
      if (targetField === 'endGallons' && endGallons.value !== null && !isNaN(endGallons.value)) {
        params.end_gallons = endGallons.value;
      } else if (endInches.value !== null && !isNaN(endInches.value)) {
        params.end_inches = endInches.value;
      }
      
      if (!params.start_inches && !params.end_inches && !params.end_gallons) return;

      try {
        const response = await api.get('/stores/tank-chart/', { params });
        if (response.data.status === 'success') {
          if (response.data.start_gallons !== undefined) startGallons.value = response.data.start_gallons;
          if (response.data.end_gallons !== undefined) endGallons.value = response.data.end_gallons;
          if (response.data.end_inches !== undefined) endInches.value = response.data.end_inches;
        }
      } catch (error) {
        logger_warn("Tank chart calibration lookup failed.");
      }
    };

    const onStartInchesChange = () => {
      triggerCalibrations();
    };

    const onEndInchesChange = () => {
      triggerCalibrations();
    };

    const logger_warn = (msg: string) => {
      console.log(`[OPERATIONAL_WARN] ${msg}`);
    };

    const saveLoad = async () => {
      if (!isValid.value) return;
      const payload = {
        store_id: storeId.value,
        fuel_type_id: fuelTypeId.value,
        price_at_store: priceAtStore.value,
        gross_gal: grossGal.value,
        net_gal: netGal.value,
        temp: temp.value,
        grav: grav.value,
        start_inches: startInches.value,
        start_gallons: startGallons.value,
        end_inches: endInches.value,
        end_gallons: endGallons.value
      };

      try {
        if (props.load.id) {
          // Update
          await api.put(`/loads/${props.load.id}/`, payload);
        } else {
          // Create
          await api.post(`/pos/${props.poId}/loads/`, payload);
        }
        emit('refresh');
      } catch (error) {
        alert("Failed to save load record.");
      }
    };

    const deleteLoad = async () => {
      if (!props.load.id) {
        // Draft load, just remove from view
        emit('refresh');
        return;
      }
      if (!confirm("Are you sure you want to delete this load delivery record?")) return;
      try {
        await api.delete(`/loads/${props.load.id}/`);
        emit('refresh');
      } catch (error) {
        alert("Failed to delete load record.");
      }
    };

    return {
      storeId,
      fuelTypeId,
      priceAtStore,
      grossGal,
      netGal,
      temp,
      grav,
      startInches,
      startGallons,
      endInches,
      endGallons,
      loadingStartChart,
      loadingEndChart,
      isDirty,
      isValid,
      onStoreChange,
      onFuelTypeChange,
      onStartInchesChange,
      onEndInchesChange,
      saveLoad,
      deleteLoad
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
.blink-tactical {
  animation: blinker 1.5s linear infinite;
}
@keyframes blinker {
  50% { opacity: 0.3; }
}
</style>
