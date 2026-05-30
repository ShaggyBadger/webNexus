<template>
  <div class="truck-fuel-entry mb-5">
    <div class="mono text-muted-custom small mb-3 text-start">[ TRUCK_FUEL_LOG ]</div>
    <div class="card bg-black-custom border-secondary p-3">
      <div class="row g-3">
        <div class="col-12 col-sm-6">
          <label class="form-label mono x-small text-primary fw-bold mb-1">GALLONS PUMPED</label>
          <input 
            type="text" 
            inputmode="decimal" 
            :value="modelValue.gallons"
            @input="updateField('gallons', ($event.target as HTMLInputElement).value)"
            class="tactical-input w-100 mono text-light"
            placeholder="0.00"
          />
        </div>
        <div class="col-12 col-sm-6">
          <label class="form-label mono x-small text-primary fw-bold mb-1">PRICE PER GALLON ($)</label>
          <input 
            type="text" 
            inputmode="decimal" 
            :value="modelValue.price_per_gallon"
            @input="updateField('price_per_gallon', ($event.target as HTMLInputElement).value)"
            class="tactical-input w-100 mono text-light"
            placeholder="0.000"
          />
        </div>
      </div>
      <div v-if="computedTotal" class="mt-3 text-end">
        <span class="mono x-small text-muted-custom">TOTAL_COST: </span>
        <span class="mono small text-primary fw-bold">${{ computedTotal }}</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, type PropType } from 'vue';

export default defineComponent({
  name: 'TruckFuelEntry',
  props: {
    modelValue: {
      type: Object as PropType<{ gallons: string; price_per_gallon: string }>,
      required: true
    }
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const computedTotal = computed(() => {
      const g = parseFloat(props.modelValue.gallons);
      const p = parseFloat(props.modelValue.price_per_gallon);
      if (!isNaN(g) && !isNaN(p)) {
        return (g * p).toFixed(2);
      }
      return null;
    });

    const updateField = (field: 'gallons' | 'price_per_gallon', value: string) => {
      emit('update:modelValue', {
        ...props.modelValue,
        [field]: value
      });
    };

    return {
      computedTotal,
      updateField
    };
  }
});
</script>
