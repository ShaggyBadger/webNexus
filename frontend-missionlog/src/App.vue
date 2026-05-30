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
            
            <ShiftParameters v-model="form.shift_start" />

            <CargoDeliveries 
              :deliveries="form.deliveries"
              :fuelTypes="fuelTypes"
              @validate-store="validateStoreDebounced"
              @add-delivery="addDelivery"
              @remove-delivery="removeDelivery"
              @add-fuel-entry="addFuelEntry"
              @remove-fuel-entry="removeFuelEntry"
            />

            <TruckFuelEntry v-model="form.truck_fuel" />

            <MissionMetrics 
              :form="form"
              :mileageMode="mileageMode"
              :computedTotalMiles="computedTotalMiles"
              @update:mileage-mode="val => mileageMode = val"
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
                @click="submitShiftLog(false)"
                class="btn btn-outline-primary btn-tactical-lg mono fw-bold w-100"
                :disabled="submitting"
              >
                {{ submitting ? 'SYNCING...' : 'SAVE_OPERATIONAL_PROGRESS' }}
              </button>
              
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
        <div v-else-if="currentView === 'audit' && selectedMission" class="historical-audit-view">
          <div class="text-start mb-3">
            <button @click="navigate('history')" class="btn btn-outline-secondary btn-sm mono fw-bold">
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
                @click="startEditingMission" 
                class="btn btn-outline-warning btn-tactical mono fw-bold px-4 w-100 w-md-auto"
              >
                <i class="fas fa-edit me-2"></i> EDIT_LOGGED_SHIFTS
              </button>

              <!-- Deletion Confirmation Deck -->
              <div v-if="showDeleteConfirm" class="card bg-black-custom p-3 border border-danger w-100 mb-0">
                <p class="mono text-danger mb-2 x-small">[ WARNING: PERMANENTLY ERASE DEBRIEF FROM ARCHIVES? CANNOT BE UNDONE. ]</p>
                <div class="d-flex gap-2 justify-content-center">
                  <button type="button" @click="deleteMission" class="btn btn-danger btn-xs mono fw-bold px-3">CONFIRM_ERASE</button>
                  <button type="button" @click="showDeleteConfirm = false" class="btn btn-outline-secondary btn-xs mono px-3">CANCEL</button>
                </div>
              </div>
              <button 
                v-else
                type="button" 
                @click="showDeleteConfirm = true" 
                class="btn btn-outline-danger btn-tactical mono fw-bold px-4 w-100 w-md-auto"
              >
                <i class="fas fa-trash me-2"></i> ERASE_MISSION_LOG
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import api from './api';
import DashboardHub from './components/DashboardHub.vue';
import MissionHistory from './components/History/MissionHistory.vue';
import ShiftParameters from './components/ActiveMission/ShiftParameters.vue';
import CargoDeliveries from './components/ActiveMission/CargoDeliveries.vue';
import TruckFuelEntry from './components/ActiveMission/TruckFuelEntry.vue';
import MissionMetrics from './components/ActiveMission/MissionMetrics.vue';

interface FuelType {
  id: number;
  name: string;
  color_name: string;
  color_hex: string;
}

interface FuelEntry {
  fuel_type_id: number;
  gallons: string;
}

interface Delivery {
  store_number_or_riso: string;
  storeValid: boolean | null;
  storeName: string;
  loading: boolean;
  debounceTimer: number | null;
  fuel_entries: FuelEntry[];
}

export default defineComponent({
  name: 'App',
  components: {
    DashboardHub,
    MissionHistory,
    ShiftParameters,
    CargoDeliveries,
    TruckFuelEntry,
    MissionMetrics
  },
  setup() {
    const currentView = ref<string>('hub');
    const loadingGlobal = ref<boolean>(true);
    const agentName = ref<string>('RECOGNIZING...');
    const fuelTypes = ref<FuelType[]>([]);
    const historicalMissions = ref<any[]>([]);
    const activeMissionData = ref<any | null>(null);
    const selectedMission = ref<any | null>(null);
    const isEditing = ref<number | null>(null);
    const showDeleteConfirm = ref<boolean>(false);

    // Form inputs state
    const mileageMode = ref<'direct' | 'odo'>('direct');
    const submitting = ref<boolean>(false);
    const submissionError = ref<string>('');
    const submissionSuccess = ref<boolean>(false);

    const form = ref({
      shift_start: '',
      hours_on_duty: '',
      total_miles: '',
      start_miles: '',
      end_miles: '',
      notes: '',
      truck_fuel: { gallons: '', price_per_gallon: '' },
      deliveries: [] as Delivery[]
    });

    const activeMissionId = computed(() => activeMissionData.value?.id || null);

    const defaultFuelTypeId = computed(() => {
      const reg = fuelTypes.value.find(f => f.name.toUpperCase() === 'REGULAR');
      return reg ? reg.id : (fuelTypes.value[0]?.id || 1);
    });

    const computedTotalMiles = computed(() => {
      if (mileageMode.value === 'odo') {
        const start = parseInt(form.value.start_miles);
        const end = parseInt(form.value.end_miles);
        if (!isNaN(start) && !isNaN(end)) {
          return end - start;
        }
        return null;
      }
      return parseInt(form.value.total_miles) || null;
    });

    const hasInvalidStores = computed(() => {
      return form.value.deliveries.some(d => d.storeValid === false);
    });

    const groupedDeliveries = computed(() => {
      if (!selectedMission.value) return [];
      
      const storesMap: Record<number, { store_num: number; store_name: string; fuels: { name: string; gallons: number; color: string }[] }> = {};
      
      const orders = selectedMission.value.order_numbers || [];
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

    const navigate = (view: string) => {
      currentView.value = view;
      submissionSuccess.value = false;
      submissionError.value = '';
      showDeleteConfirm.value = false;
      if (view === 'hub') {
        refreshActiveMission();
        resetForm();
        isEditing.value = null;
      } else if (view === 'history') {
        refreshHistoricalMissions();
      } else if (view === 'active') {
        if (!isEditing.value && !activeMissionId.value) {
          resetForm();
          // Pre-populate date time
          const now = new Date();
          const offset = now.getTimezoneOffset() * 60000;
          form.value.shift_start = new Date(now.getTime() - offset).toISOString().slice(0, 16);
          // Default to one empty delivery
          addDelivery();
        } else if (activeMissionId.value && !isEditing.value) {
          // Resume active mission
          populateFormFromMission(activeMissionData.value);
        }
      }
    };

    const resetForm = () => {
      form.value = {
        shift_start: '',
        hours_on_duty: '',
        total_miles: '',
        start_miles: '',
        end_miles: '',
        notes: '',
        truck_fuel: { gallons: '', price_per_gallon: '' },
        deliveries: []
      };
      mileageMode.value = 'direct';
    };

    const fetchAgentInfo = async () => {
      try {
        const response = await api.get('/agent-info/');
        agentName.value = response.data.callsign || response.data.username.toUpperCase();
      } catch (error) {
        agentName.value = 'UNKNOWN_ENTITY';
      }
    };

    const loadCoreData = async () => {
      try {
        const fuelResp = await api.get('/fuel-types/');
        fuelTypes.value = fuelResp.data;
      } catch (error) {
        console.error("Failed to load standardized fuel parameters.", error);
      }
    };

    const refreshActiveMission = async () => {
      try {
        const response = await api.get('/missions/active/');
        if (response.data.active) {
          activeMissionData.value = response.data.mission;
        } else {
          activeMissionData.value = null;
        }
      } catch (error) {
        console.error("Failed to resolve active mission.");
      }
    };

    const refreshHistoricalMissions = async () => {
      try {
        const response = await api.get('/missions/');
        historicalMissions.value = response.data;
      } catch (error) {
        console.error("Failed to fetch historical database archives.", error);
      }
    };

    // Store validation routines
    const validateStoreDebounced = (index: number) => {
      const deliv = form.value.deliveries[index];
      const val = deliv.store_number_or_riso.trim();

      // Clear any pending validation timers
      if (deliv.debounceTimer) {
        clearTimeout(deliv.debounceTimer);
      }

      if (val === '') {
        deliv.storeValid = null;
        deliv.storeName = '';
        deliv.loading = false;
        return;
      }

      deliv.loading = true;
      deliv.storeValid = null;

      deliv.debounceTimer = window.setTimeout(async () => {
        try {
          const response = await api.get('/stores/validate/', {
            params: { q: val }
          });
          if (response.data.valid) {
            deliv.storeValid = true;
            deliv.storeName = response.data.store_name;
          } else {
            deliv.storeValid = false;
            deliv.storeName = '';
          }
        } catch (err) {
          deliv.storeValid = false;
          deliv.storeName = '';
        } finally {
          deliv.loading = false;
        }
      }, 500);
    };

    // Deliveries controls
    const addDelivery = () => {
      form.value.deliveries.push({
        store_number_or_riso: '',
        storeValid: null,
        storeName: '',
        loading: false,
        debounceTimer: null,
        fuel_entries: [
          { fuel_type_id: defaultFuelTypeId.value, gallons: '' }
        ]
      });
    };

    const removeDelivery = (index: number) => {
      const deliv = form.value.deliveries[index];
      if (deliv.debounceTimer) clearTimeout(deliv.debounceTimer);
      form.value.deliveries.splice(index, 1);
    };

    const addFuelEntry = (deliveryIndex: number) => {
      form.value.deliveries[deliveryIndex].fuel_entries.push({
        fuel_type_id: defaultFuelTypeId.value,
        gallons: ''
      });
    };

    const removeFuelEntry = (deliveryIndex: number, fuelIndex: number) => {
      form.value.deliveries[deliveryIndex].fuel_entries.splice(fuelIndex, 1);
    };

    const submitShiftLog = async (complete: boolean) => {
      submitting.value = true;
      submissionError.value = '';
      submissionSuccess.value = false;

      // --- VALIDATION PHASE ---
      if (!form.value.shift_start) {
        submissionError.value = "VALIDATION_ERROR: SHIFT START TIME IS REQUIRED.";
        submitting.value = false;
        return;
      }

      if (complete) {
        if (!form.value.hours_on_duty || String(form.value.hours_on_duty).trim() === "") {
          submissionError.value = "VALIDATION_ERROR: HOURS ON DUTY MUST BE LOGGED FOR FINALIZATION.";
          submitting.value = false;
          return;
        }

        const miles = computedTotalMiles.value;
        if (miles === null || isNaN(miles)) {
          submissionError.value = "VALIDATION_ERROR: TOTAL MILEAGE IS REQUIRED FOR FINALIZATION.";
          submitting.value = false;
          return;
        }
      }

      // Filter out entirely empty delivery blocks
      const activeDeliveries = form.value.deliveries.filter(d => {
        const hasStore = String(d.store_number_or_riso || "").trim() !== "";
        const hasGallons = d.fuel_entries.some(f => String(f.gallons || "").trim() !== "");
        return hasStore || hasGallons;
      });

      // Deep validation of active deliveries
      for (const d of activeDeliveries) {
        if (d.loading) {
          submissionError.value = "VALIDATION_ERROR: STORE VALIDATION IN PROGRESS. PLEASE WAIT.";
          submitting.value = false;
          return;
        }
        if (!d.store_number_or_riso || String(d.store_number_or_riso).trim() === "") {
          submissionError.value = "VALIDATION_ERROR: ONE OR MORE DELIVERIES ARE MISSING A STORE NUMBER.";
          submitting.value = false;
          return;
        }
        if (d.storeValid === false) {
          submissionError.value = `VALIDATION_ERROR: STORE '${d.store_number_or_riso}' IS NOT RECOGNIZED BY HQ.`;
          submitting.value = false;
          return;
        }
        
        const validFuelEntries = d.fuel_entries.filter(f => String(f.gallons || "").trim() !== "");
        if (validFuelEntries.length === 0) {
          submissionError.value = `VALIDATION_ERROR: STORE ${d.store_number_or_riso} HAS NO VOLUME (GALLONS) LOGGED.`;
          submitting.value = false;
          return;
        }
      }

      // --- PAYLOAD CONSTRUCTION ---
      const startMiles = mileageMode.value === 'odo' ? parseInt(form.value.start_miles) : null;
      const endMiles = mileageMode.value === 'odo' ? parseInt(form.value.end_miles) : null;

      const payload: any = {
        shift_start: form.value.shift_start,
        is_completed: complete,
        hours_on_duty: form.value.hours_on_duty,
        total_miles: computedTotalMiles.value,
        start_miles: startMiles,
        end_miles: endMiles,
        notes: form.value.notes,
        truck_fuel: (form.value.truck_fuel.gallons && form.value.truck_fuel.price_per_gallon) ? form.value.truck_fuel : null,
        deliveries: activeDeliveries.map(d => ({
          store_number_or_riso: String(d.store_number_or_riso || "").trim(),
          fuel_entries: d.fuel_entries
            .filter(f => String(f.gallons || "").trim() !== "")
            .map(f => ({
              fuel_type_id: f.fuel_type_id,
              gallons: String(f.gallons || "").trim()
            }))
        }))
      };

      try {
        let response;
        const targetId = isEditing.value || activeMissionId.value;
        if (targetId) {
          response = await api.put(`/missions/post-trip/${targetId}/`, payload);
        } else {
          response = await api.post('/missions/post-trip/', payload);
        }

        if (response.data.status === 'success') {
          submissionSuccess.value = true;
          window.scrollTo({ top: 0, behavior: 'smooth' });
          window.setTimeout(() => {
            if (complete) {
              navigate('hub');
            } else {
              submissionSuccess.value = false;
              refreshActiveMission();
            }
          }, 1500);
        }
      } catch (error: any) {
        submissionError.value = error.response?.data?.message || "OPERATIONAL_FAILURE: SERVER REJECTED DATA STREAM.";
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } finally {
        submitting.value = false;
      }
    };

    const populateFormFromMission = (m: any) => {
      const d = new Date(m.shift_start);
      const offset = d.getTimezoneOffset() * 60000;
      form.value.shift_start = new Date(d.getTime() - offset).toISOString().slice(0, 16);
      
      form.value.hours_on_duty = m.hours_on_duty ? String(m.hours_on_duty) : '';
      form.value.notes = m.notes || '';
      
      if (m.start_miles || m.end_miles) {
        mileageMode.value = 'odo';
        form.value.start_miles = m.start_miles ? String(m.start_miles) : '';
        form.value.end_miles = m.end_miles ? String(m.end_miles) : '';
        form.value.total_miles = '';
      } else {
        mileageMode.value = 'direct';
        form.value.total_miles = m.total_miles ? String(m.total_miles) : '';
        form.value.start_miles = '';
        form.value.end_miles = '';
      }

      if (m.fuel_logs && m.fuel_logs.length > 0) {
        form.value.truck_fuel.gallons = String(m.fuel_logs[0].gallons);
        form.value.truck_fuel.price_per_gallon = String(m.fuel_logs[0].price_per_gallon);
      } else {
        form.value.truck_fuel = { gallons: '', price_per_gallon: '' };
      }
      
      const deliveries: Delivery[] = [];
      const orders = m.order_numbers || [];
      for (const ord of orders) {
        for (const po of ord.purchase_orders || []) {
          for (const ld of po.loads || []) {
            if (!ld.store_num) continue;
            let existing = deliveries.find(d => d.store_number_or_riso === String(ld.store_num));
            if (!existing) {
              existing = {
                store_number_or_riso: String(ld.store_num),
                storeValid: true,
                storeName: ld.store_name || 'Unlisted Store',
                loading: false,
                debounceTimer: null,
                fuel_entries: []
              };
              deliveries.push(existing);
            }
            existing.fuel_entries.push({
              fuel_type_id: ld.fuel_type_id,
              gallons: String(ld.gross_gal || 0)
            });
          }
        }
      }
      
      form.value.deliveries = deliveries.length > 0 ? deliveries : [
          { store_number_or_riso: '', storeValid: null, storeName: '', loading: false, debounceTimer: null, fuel_entries: [{ fuel_type_id: defaultFuelTypeId.value, gallons: '' }] }
      ];
    };

    const viewHistoricalMission = (mission: any) => {
      selectedMission.value = mission;
      currentView.value = 'audit';
    };

    const startEditingMission = () => {
      if (!selectedMission.value) return;
      isEditing.value = selectedMission.value.id;
      populateFormFromMission(selectedMission.value);
      currentView.value = 'active';
    };

    const deleteMission = async () => {
      if (!selectedMission.value) return;
      try {
        await api.delete(`/missions/${selectedMission.value.id}/`);
        refreshHistoricalMissions();
        navigate('history');
      } catch (error) {
        console.error("Failed to delete mission archive.", error);
        submissionError.value = "CRITICAL_FAILURE: SYSTEM COULD NOT ERASE ARCHIVE.";
      }
    };

    const formatDateTime = (isoString: string) => {
      if (!isoString) return '-';
      const d = new Date(isoString);
      return d.toLocaleString();
    };

    onMounted(async () => {
      try {
        loadingGlobal.value = true;
        await Promise.all([
          fetchAgentInfo(),
          loadCoreData(),
          refreshActiveMission()
        ]);
      } catch (err) {
        console.error("INITIALIZATION_FAILURE: TACTICAL_HQ_UNREACHABLE.", err);
      } finally {
        loadingGlobal.value = false;
      }
    });

    return {
      currentView,
      loadingGlobal,
      agentName,
      fuelTypes,
      historicalMissions,
      activeMissionData,
      activeMissionId,
      selectedMission,
      isEditing,
      showDeleteConfirm,
      mileageMode,
      submitting,
      submissionError,
      submissionSuccess,
      form,
      computedTotalMiles,
      hasInvalidStores,
      groupedDeliveries,
      navigate,
      validateStoreDebounced,
      addDelivery,
      removeDelivery,
      addFuelEntry,
      removeFuelEntry,
      submitShiftLog,
      viewHistoricalMission,
      startEditingMission,
      deleteMission,
      formatDateTime
    };
  }
});
</script>

<style>
/* Base Camp CSS Style Overrides */
:root {
  --bg-color: #121417;
  --bg-card: #1c1f23;
  --primary-color: #8da35d;
  --accent-color: #e94560;
  --navbar-border: #2d3139;
  --muted-text-color: #9ea8b6;
}

body {
  background-color: var(--bg-color) !important;
  color: #f8f9fa !important;
}

.bg-dark-custom {
  background-color: var(--bg-card) !important;
}

.bg-black-custom {
  background-color: #0b0d0f !important;
}

.text-primary {
  color: var(--primary-color) !important;
}

.text-warning {
  color: #ffb86c !important;
}

.text-muted-custom {
  color: var(--muted-text-color) !important;
  opacity: 0.85;
}

.border-primary {
  border-color: var(--primary-color) !important;
}

.border-secondary {
  border-color: var(--navbar-border) !important;
}

.tactical-input {
  background-color: #0b0d0f !important;
  color: white !important;
  border: 1px solid var(--navbar-border) !important;
  border-radius: 0 !important;
  font-family: "JetBrains Mono", monospace !important;
  padding: 0.75rem 1rem !important;
}

.tactical-input:focus {
  border-color: var(--primary-color) !important;
  box-shadow: 0 0 10px rgba(141, 163, 93, 0.2) !important;
  outline: none;
}

.tactical-input-table {
  background-color: transparent !important;
  color: white !important;
  font-family: "JetBrains Mono", monospace !important;
  padding: 0.5rem 0.75rem !important;
  outline: none;
}

.tactical-input-table:focus {
  background-color: rgba(141, 163, 93, 0.05) !important;
}

.rocker-switch {
  padding: 0;
  border-radius: 0;
  overflow: hidden;
}

.rocker-btn {
  border: none !important;
  color: var(--muted-text-color) !important;
  background: #171a1d !important;
  transition: all 0.2s ease;
  min-width: 80px;
  min-height: 40px !important;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rocker-btn:hover {
  background: #1c2126 !important;
  color: white !important;
}

.rocker-btn.active {
  background: var(--primary-color) !important;
  color: #121417 !important;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.4), 0 0 10px rgba(141, 163, 93, 0.3) !important;
}

.btn-tactical-lg {
  border-radius: 0 !important;
  padding: 1rem 1.5rem !important;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.btn-tactical {
  border-radius: 0 !important;
  padding: 0.65rem 1.25rem !important;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.btn-primary {
  background-color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
  color: #121417 !important;
}

.btn-primary:hover, .btn-primary:active, .btn-primary:focus {
  background-color: #798d4d !important;
  border-color: #798d4d !important;
}

.btn-outline-primary {
  color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
}

.btn-outline-primary:hover, .btn-outline-primary:active, .btn-outline-primary.active {
  background-color: var(--primary-color) !important;
  color: #121417 !important;
}

.btn-outline-secondary {
  color: var(--muted-text-color) !important;
  border-color: var(--navbar-border) !important;
}

.btn-outline-secondary:hover {
  background-color: rgba(255,255,255,0.05) !important;
  color: white !important;
}

.btn-outline-warning {
  color: #ffb86c !important;
  border-color: #ffb86c !important;
}

.btn-outline-warning:hover {
  background-color: #ffb86c !important;
  color: #121417 !important;
}

.btn-outline-danger {
  color: var(--accent-color) !important;
  border-color: var(--accent-color) !important;
}

.btn-outline-danger:hover {
  background-color: var(--accent-color) !important;
  color: white !important;
}

.btn-xs {
  font-size: 0.7rem;
  padding: 0.25rem 0.6rem;
  border-radius: 0;
}

.mono {
  font-family: "JetBrains Mono", monospace !important;
}

.x-small {
  font-size: 0.75rem;
}

.uppercase {
  text-transform: uppercase;
}

/* --- MOBILE FIRST TOUCH OPTIMIZATIONS --- */
@media (max-width: 768px) {
  .btn:not(.btn-xs) {
    min-height: 52px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
  }

  .tactical-input {
    min-height: 52px;
    font-size: 1rem !important; /* Prevents iOS zoom on focus */
  }

  .btn-xs {
    min-height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .container-fluid {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }

  nav .btn-xs {
    padding: 0.5rem 0.8rem !important;
    font-size: 0.65rem !important;
  }
}

/* --- TACTICAL SECTION DIVIDERS --- */
.section-divider {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 5rem !important; /* Significant vertical separation */
  margin-bottom: 2.5rem !important;
}

.divider-line {
  flex-grow: 1;
  height: 1px;
  background-color: var(--navbar-border);
  opacity: 0.3;
}

.divider-text {
  font-size: 0.8rem;
  color: var(--primary-color);
  letter-spacing: 3px;
  white-space: nowrap;
  background-color: #0b0d0f;
  padding: 0.5rem 1.5rem;
  border: 1px solid var(--navbar-border);
  box-shadow: 0 0 15px rgba(141, 163, 93, 0.1);
}

.card {
  margin-bottom: 2rem !important;
}

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
</style>
