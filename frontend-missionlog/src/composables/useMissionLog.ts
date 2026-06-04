import { ref, computed } from 'vue';
import api from '../api';

export interface FuelType {
  id: number;
  name: string;
  color_name: string;
  color_hex: string;
}

export interface FuelEntry {
  fuel_type_id: number;
  gallons: string;
}

export interface Delivery {
  store_number_or_riso: string;
  storeValid: boolean | null;
  storeName: string;
  loading: boolean;
  debounceTimer: number | null;
  fuel_entries: FuelEntry[];
}

export function useMissionLog() {
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
        const now = new Date();
        const offset = now.getTimezoneOffset() * 60000;
        form.value.shift_start = new Date(now.getTime() - offset).toISOString().slice(0, 16);
        addDelivery();
      } else if (activeMissionId.value && !isEditing.value) {
        populateFormFromMission(activeMissionData.value);
      }
    }
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

  const validateStoreDebounced = (index: number) => {
    const deliv = form.value.deliveries[index];
    const val = deliv.store_number_or_riso.trim();

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

  const submitShiftLog = async (complete: boolean) => {
    submitting.value = true;
    submissionError.value = '';
    submissionSuccess.value = false;

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

    const activeDeliveries = form.value.deliveries.filter(d => {
      const hasStore = String(d.store_number_or_riso || "").trim() !== "";
      const hasGallons = d.fuel_entries.some(f => String(f.gallons || "").trim() !== "");
      return hasStore || hasGallons;
    });

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
        try {
          response = await api.post('/missions/post-trip/', payload);
        } catch (postError: any) {
          // Handle Duplicate Active Mission Safeguard
          if (postError.response?.data?.code === 'ACTIVE_EXISTS') {
            console.warn("ACTIVE_MISSION_EXISTS: RE-SYNCING CONTEXT.");
            await refreshActiveMission();
            const newId = activeMissionId.value;
            if (newId) {
                response = await api.put(`/missions/post-trip/${newId}/`, payload);
            } else {
                throw postError;
            }
          } else {
            throw postError;
          }
        }
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

  const initialize = async () => {
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
  };

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
    initialize
  };
}
