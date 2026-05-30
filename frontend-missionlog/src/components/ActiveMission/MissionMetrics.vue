<template>
  <div class="mission-metrics mb-5">
    <!-- OPERATIONAL METRICS -->
    <div class="mono text-muted-custom small mb-3 text-center">[ OPERATIONAL_METRICS ]</div>
    <div class="table-responsive mb-4 mx-auto" style="max-width: 600px;">
      <table class="table table-bordered border-secondary bg-black-custom mono x-small text-light mb-0">
        <thead>
          <tr class="bg-dark-custom text-primary text-uppercase">
            <th scope="col" class="py-2 px-3">PARAMETER</th>
            <th scope="col" class="py-2 px-3 text-end">INPUT_VALUE</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="py-2 px-3 align-middle text-muted-custom">HOURS ON DUTY</td>
            <td class="py-0 px-0">
              <input 
                type="text" 
                inputmode="decimal" 
                v-model="form.hours_on_duty" 
                class="tactical-input-table w-100 mono text-light text-end border-0" 
                placeholder="0.0"
              />
            </td>
          </tr>
          <tr>
            <td class="py-2 px-3 align-middle text-muted-custom">MILEAGE MODE</td>
            <td class="py-2 px-3 text-end">
              <div class="rocker-switch d-inline-flex flex-nowrap border border-secondary bg-black-custom">
                <button 
                  type="button" 
                  @click="$emit('update:mileage-mode', 'direct')"
                  class="rocker-btn btn btn-xs mono fw-bold px-3" 
                  :class="{ 'active': mileageMode === 'direct' }"
                >
                  DIRECT
                </button>
                <button 
                  type="button" 
                  @click="$emit('update:mileage-mode', 'odo')"
                  class="rocker-btn btn btn-xs mono fw-bold px-3 border-start border-secondary" 
                  :class="{ 'active': mileageMode === 'odo' }"
                >
                  ODO
                </button>
              </div>
            </td>
          </tr>
          <template v-if="mileageMode === 'direct'">
            <tr>
              <td class="py-2 px-3 align-middle text-muted-custom">TOTAL MILES</td>
              <td class="py-0 px-0">
                <input 
                  type="text" 
                  inputmode="numeric" 
                  v-model="form.total_miles"
                  class="tactical-input-table w-100 mono text-light text-end border-0"
                  placeholder="0"
                />
              </td>
            </tr>
          </template>
          <template v-else>
            <tr>
              <td class="py-2 px-3 align-middle text-muted-custom">STARTING ODOMETER</td>
              <td class="py-0 px-0">
                <input 
                  type="text" 
                  inputmode="numeric" 
                  v-model="form.start_miles"
                  class="tactical-input-table w-100 mono text-light text-end border-0"
                  placeholder="START"
                />
              </td>
            </tr>
            <tr>
              <td class="py-2 px-3 align-middle text-muted-custom">ENDING ODOMETER</td>
              <td class="py-0 px-0">
                <input 
                  type="text" 
                  inputmode="numeric" 
                  v-model="form.end_miles"
                  class="tactical-input-table w-100 mono text-light text-end border-0"
                  placeholder="END"
                />
              </td>
            </tr>
            <tr v-if="computedTotalMiles !== null">
              <td class="py-2 px-3 align-middle text-muted-custom text-primary">[ COMPUTED TOTAL ]</td>
              <td class="py-2 px-3 text-end text-primary fw-bold">{{ computedTotalMiles }} MILES</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- GENERAL DEBRIEF NOTES -->
    <div class="mono text-muted-custom small mb-3 text-start">[ DEBRIEF_MEMORANDUM ]</div>
    <div class="mb-4">
      <textarea 
        v-model="form.notes"
        rows="3"
        class="tactical-input w-100 mono text-light text-center"
        placeholder="SITE QUIRKS, ROADBLOCKS, PUMP OBSERVATIONS..."
      ></textarea>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue';

export default defineComponent({
  name: 'MissionMetrics',
  props: {
    form: {
      type: Object as PropType<any>,
      required: true
    },
    mileageMode: {
      type: String as PropType<string>,
      required: true
    },
    computedTotalMiles: {
      type: Number as PropType<number | null>,
      required: false,
      default: null
    }
  },
  emits: ['update:mileage-mode']
});
</script>
