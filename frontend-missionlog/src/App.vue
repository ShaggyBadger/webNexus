<template>
  <div class="missionlog-spa py-5 px-3">
    <div class="container-fluid" style="max-width: 800px;">
      <!-- Navigation Command Bar -->
      <nav class="d-flex justify-content-between align-items-center mb-4 border border-secondary p-2 bg-black-custom">
        <div class="d-flex gap-3 align-items-center">
          <div class="d-none d-md-flex gap-2 align-items-center me-2">
            <i class="fas fa-microchip text-primary"></i>
            <span class="mono text-light x-small fw-bold">[ CORE_SYS ]</span>
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
          </div>
        </div>
        <div class="d-flex">
          <a href="/" class="btn btn-outline-secondary btn-xs mono fw-bold px-3">
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
          :activeMission="activeMissionData"
          @navigate="navigate"
        />

        <!-- Active Monolithic Form View -->
        <div v-else-if="currentView === 'active'" class="active-mission-view">
          <!-- Back button -->
          <div class="text-start mb-3">
            <button @click="navigate('hub')" class="btn btn-outline-secondary btn-sm mono fw-bold">
              <i class="fas fa-arrow-left me-2"></i> RETREAT_TO_LAUNCHER
            </button>
          </div>

          <!-- Top Header -->
          <div class="card bg-dark-custom border-secondary p-4 text-center mb-4">
            <h2 class="mono text-light h4 uppercase">[ {{ (isEditing || activeMissionId) ? 'ACTIVE_MISSION_CONSOLE' : 'SHIFT_INITIALIZATION' }} ]</h2>
            <div class="mono text-primary x-small mt-1">[ PROTOCOL: {{ (isEditing || activeMissionId) ? 'REAL_TIME_INGESTION' : 'NEW_DEPLOYMENT' }} ]</div>
          </div>

          <!-- Monolithic Form -->
          <form @submit.prevent="() => {}" class="card bg-dark-custom border-secondary p-4 mb-5">
            
            <ShiftParameters v-model="form.shift_start" @auto-save="submitShiftLog(false)" />

            <CargoDeliveries 
              :deliveries="form.deliveries"
              :fuelTypes="fuelTypes"
              @validate-store="validateStoreDebounced"
              @add-delivery="addDelivery"
              @remove-delivery="removeDelivery"
              @add-fuel-entry="addFuelEntry"
              @remove-fuel-entry="removeFuelEntry"
              @auto-save="submitShiftLog(false)"
            />

            <TruckFuelEntry v-model="form.truck_fuel" @update:model-value="submitShiftLog(false)" />

            <MissionMetrics 
              :form="form"
              :mileageMode="mileageMode"
              :computedTotalMiles="computedTotalMiles"
              @update:mileage-mode="val => { mileageMode = val; submitShiftLog(false); }"
              @auto-save="submitShiftLog(false)"
            />

            <!-- Submit Status Indicators -->
            <div v-if="submissionError" class="alert alert-danger bg-black-custom border-danger mono x-small text-danger mb-3">
              ❌ INGESTION_ERROR: {{ submissionError }}
            </div>
            <div v-if="submissionSuccess" class="alert alert-success bg-black-custom border-primary mono x-small text-primary mb-3">
              ✓ SECURED: DATA_STREAM_SYNC_COMPLETE.
            </div>

            <!-- Submit action buttons -->
            <div class="d-flex flex-column gap-3">
              <button 
                type="button" 
                @click="submitShiftLog(true)"
                class="btn btn-primary btn-tactical-lg mono fw-bold w-100"
                :disabled="submitting"
              >
                {{ submitting ? 'FINALIZING...' : 'COMMIT_MISSION_TO_ARCHIVES' }}
              </button>
            </div>
          </form>
        </div>

        <!-- Historical Archive View -->
        <MissionHistory 
          v-else-if="currentView === 'history'" 
          :missions="historicalMissions"
          @navigate="navigate"
          @select-mission="viewHistoricalMission"
        />

        <!-- Read Only Historical Mission Audit View -->
        <MissionAudit 
          v-else-if="currentView === 'audit' && selectedMission"
          :selectedMission="selectedMission"
          @navigate="navigate"
          @edit="startEditingMission"
          @delete="deleteMission"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, onMounted } from 'vue';
import { useMissionLog } from './composables/useMissionLog';

import DashboardHub from './components/DashboardHub.vue';
import MissionHistory from './components/History/MissionHistory.vue';
import MissionAudit from './components/History/MissionAudit.vue';
import ShiftParameters from './components/ActiveMission/ShiftParameters.vue';
import CargoDeliveries from './components/ActiveMission/CargoDeliveries.vue';
import TruckFuelEntry from './components/ActiveMission/TruckFuelEntry.vue';
import MissionMetrics from './components/ActiveMission/MissionMetrics.vue';

export default defineComponent({
  name: 'App',
  components: {
    DashboardHub,
    MissionHistory,
    MissionAudit,
    ShiftParameters,
    CargoDeliveries,
    TruckFuelEntry,
    MissionMetrics
  },
  setup() {
    const missionLog = useMissionLog();

    onMounted(() => {
      missionLog.initialize();
    });

    return {
      ...missionLog
    };
  }
});
</script>

<style>
/* Styles moved to style.css */
</style>
