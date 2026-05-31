<template>
  <div class="historical-audit-view">
    <div class="text-start mb-3">
      <button @click="$emit('navigate', 'history')" class="btn btn-outline-secondary btn-sm mono fw-bold">
        <i class="fas fa-arrow-left me-2"></i> RETURN_TO_ARCHIVES
      </button>
    </div>

    <div class="card bg-dark-custom border-secondary p-4 mb-5">
      <div class="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-2">
        <h3 class="mono text-light h5 uppercase">[ MISSION_AUDIT // DEBRIEF_ID: {{ selectedMission.id }} ]</h3>
        <span class="badge bg-black-custom text-primary border border-primary px-3 py-2 mono small">[ COMPLETED ]</span>
      </div>

      <!-- Tactical Parameter Table -->
      <div class="table-responsive mb-4 mx-auto" style="max-width: 600px;">
        <table class="table table-bordered border-secondary bg-black-custom mono x-small text-light mb-0">
          <thead>
            <tr class="bg-dark-custom text-primary text-uppercase">
              <th scope="col" class="py-2 px-3">OPERATIONAL PARAMETER</th>
              <th scope="col" class="py-2 px-3 text-end">LOGGED VALUE</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="py-2 px-3 text-muted-custom">DEPARTURE TIME</td>
              <td class="py-2 px-3 text-end fw-bold">{{ formatDateTime(selectedMission.shift_start) }}</td>
            </tr>
            <tr>
              <td class="py-2 px-3 text-muted-custom">DEBRIEF SIGN-OFF</td>
              <td class="py-2 px-3 text-end fw-bold">{{ formatDateTime(selectedMission.shift_end) }}</td>
            </tr>
            <tr>
              <td class="py-2 px-3 text-muted-custom">DURATION LOGGED</td>
              <td class="py-2 px-3 text-end text-warning fw-bold">{{ selectedMission.hours_on_duty }} HOURS</td>
            </tr>
            <tr>
              <td class="py-2 px-3 text-muted-custom">MILES TRAVELED</td>
              <td class="py-2 px-3 text-end text-primary fw-bold">
                {{ selectedMission.total_miles }} MILES
                <span v-if="selectedMission.start_miles" class="text-muted-custom small ms-1">(Odo: {{ selectedMission.start_miles }} → {{ selectedMission.end_miles }})</span>
              </td>
            </tr>
            <tr>
              <td class="py-2 px-3 text-muted-custom">UNIQUE STORES VISITED</td>
              <td class="py-2 px-3 text-end text-warning fw-bold">{{ selectedMission.total_stops }} STORES</td>
            </tr>
            <tr v-if="selectedMission.fuel_logs && selectedMission.fuel_logs.length > 0">
              <td class="py-2 px-3 text-muted-custom">TRUCK FUEL USED</td>
              <td class="py-2 px-3 text-end text-primary fw-bold">
                {{ selectedMission.fuel_logs[0].gallons }} GAL @ ${{ selectedMission.fuel_logs[0].price_per_gallon }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Load Deliveries summary -->
      <div class="mono text-muted-custom small mb-2 text-start">[ FIELD_CARGO_RECORDS_BY_SITE ]</div>
      <div class="card bg-black-custom border-secondary p-3 mb-4">
        <div v-if="groupedDeliveries.length === 0" class="mono text-muted-custom x-small text-center py-2">
          [ NO RECORDED CARGO RECORDS FOR THIS SHIFT ]
        </div>
        <div v-else>
          <div v-for="site in groupedDeliveries" :key="site.store_num" class="border-bottom border-secondary py-3 last-border-none">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="mono text-primary fw-bold">✓ STORE {{ site.store_num }}</span>
              <span class="mono text-muted-custom x-small">{{ site.store_name }}</span>
            </div>
            <!-- Nested fuels delivered -->
            <div class="d-flex flex-wrap gap-2 ps-3">
              <span 
                v-for="(fuel, fIdx) in site.fuels" 
                :key="fIdx"
                class="badge px-3 py-2 mono" 
                :style="{ backgroundColor: fuel.color || '#1c1f23', color: '#000' }"
              >
                {{ fuel.gallons }} GAL {{ fuel.name.toUpperCase() }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Notes summary -->
      <div v-if="selectedMission.notes" class="text-start mb-4">
        <div class="mono text-muted-custom small mb-1">[ FIELD_MEMORANDUM_RECORDS ]</div>
        <div class="card bg-black-custom border-secondary p-3 mono text-light x-small">
          {{ selectedMission.notes }}
        </div>
      </div>

      <!-- Tactical Command Actions Deck -->
      <div class="d-flex flex-column flex-md-row justify-content-center align-items-center gap-3 border-top border-secondary pt-4 mt-4">
        <button 
          type="button" 
          @click="$emit('edit')" 
          class="btn btn-outline-warning btn-tactical mono fw-bold px-4 w-100 w-md-auto"
        >
          <i class="fas fa-edit me-2"></i> EDIT_LOGGED_SHIFTS
        </button>

        <!-- Deletion Confirmation Deck -->
        <div v-if="showDeleteConfirmLocal" class="card bg-black-custom p-3 border border-danger w-100 mb-0">
          <p class="mono text-danger mb-2 x-small">[ WARNING: PERMANENTLY ERASE DEBRIEF FROM ARCHIVES? CANNOT BE UNDONE. ]</p>
          <div class="d-flex gap-2 justify-content-center">
            <button type="button" @click="$emit('delete')" class="btn btn-danger btn-xs mono fw-bold px-3">CONFIRM_ERASE</button>
            <button type="button" @click="showDeleteConfirmLocal = false" class="btn btn-outline-secondary btn-xs mono px-3">CANCEL</button>
          </div>
        </div>
        <button 
          v-else
          type="button" 
          @click="showDeleteConfirmLocal = true" 
          class="btn btn-outline-danger btn-tactical mono fw-bold px-4 w-100 w-md-auto"
        >
          <i class="fas fa-trash me-2"></i> ERASE_MISSION_LOG
        </button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref } from 'vue';

export default defineComponent({
  name: 'MissionAudit',
  props: {
    selectedMission: {
      type: Object,
      required: true
    }
  },
  emits: ['navigate', 'edit', 'delete'],
  setup(props) {
    const showDeleteConfirmLocal = ref(false);

    const formatDateTime = (isoString: string) => {
      if (!isoString) return '-';
      const d = new Date(isoString);
      return d.toLocaleString();
    };

    const groupedDeliveries = computed(() => {
      if (!props.selectedMission) return [];
      
      const storesMap: Record<number, { store_num: number; store_name: string; fuels: { name: string; gallons: number; color: string }[] }> = {};
      
      const orders = props.selectedMission.order_numbers || [];
      for (const ord of orders) {
        const pos = ord.purchase_orders || [];
        for (const po of pos) {
          const loads = po.loads || [];
          for (const ld of loads) {
            if (!ld.store_num) continue;
            if (!storesMap[ld.store_num]) {
              storesMap[ld.store_num] = {
                store_num: ld.store_num,
                store_name: ld.store_name || 'Unlisted Store',
                fuels: []
              };
            }
            storesMap[ld.store_num].fuels.push({
              name: ld.fuel_type_name,
              gallons: ld.gross_gal || 0,
              color: ld.fuel_type_color || '#8da35d'
            });
          }
        }
      }
      return Object.values(storesMap);
    });

    return {
      showDeleteConfirmLocal,
      formatDateTime,
      groupedDeliveries
    };
  }
});
</script>
