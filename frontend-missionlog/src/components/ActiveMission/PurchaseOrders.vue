<template>
  <div class="purchase-orders card bg-dark-custom border-secondary p-4 mb-4">
    <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
      <h3 class="mono text-light h5 mb-0 fw-bold">
        <i class="fas fa-file-invoice text-primary me-2"></i> PURCHASE ORDERS & CARGO LOADS
      </h3>
      <button @click="showAddPo = !showAddPo" class="btn btn-outline-primary btn-sm mono fw-bold">
        {{ showAddPo ? 'CANCEL_PO' : 'ADD_PURCHASE_ORDER' }}
      </button>
    </div>

    <!-- Add PO Form -->
    <div v-if="showAddPo" class="card bg-black-custom p-3 border border-secondary mb-4 text-start">
      <div class="row align-items-end g-3">
        <div class="col-12 col-sm-8">
          <label class="form-label mono x-small text-muted-custom mb-1">PURCHASE ORDER NUMBER *</label>
          <input 
            v-model.number="newPoNumber" 
            type="number" 
            class="tactical-input w-100 mono text-light" 
            placeholder="ENTER PO ID NUMBER"
          />
        </div>
        <div class="col-12 col-sm-4 text-end">
          <button 
            @click="submitNewPo" 
            class="btn btn-primary btn-tactical mono fw-bold w-100"
            :disabled="!newPoNumber"
          >
            CONFIRM_PO
          </button>
        </div>
      </div>
    </div>

    <!-- PO List Accordion -->
    <div v-if="purchaseOrders.length > 0" class="po-deck d-flex flex-column gap-3 text-start">
      <div 
        v-for="po in purchaseOrders" 
        :key="po.id" 
        class="po-card border"
        :class="expandedPOs[po.id] ? 'border-primary' : 'border-secondary'"
      >
        <!-- Header -->
        <div 
          @click="togglePo(po.id)" 
          class="po-header p-3 d-flex justify-content-between align-items-center cursor-pointer bg-black-custom"
        >
          <div class="d-flex align-items-center gap-3">
            <i class="fas" :class="expandedPOs[po.id] ? 'fa-chevron-down text-primary' : 'fa-chevron-right text-muted-custom'"></i>
            <span class="mono text-light fw-bold">PO #{{ po.po_number }}</span>
            <span class="badge bg-secondary mono x-small">{{ po.loads.length }} LOAD(S)</span>
          </div>
          <div>
            <button @click.stop="deletePo(po.id)" class="btn btn-outline-danger btn-xs mono">
              <i class="fas fa-trash-alt"></i> DELETE_PO
            </button>
          </div>
        </div>

        <!-- Body -->
        <div v-if="expandedPOs[po.id]" class="po-body p-3 border-top border-secondary">
          <!-- Loads Lists -->
          <div v-if="po.loads.length > 0" class="d-flex flex-column gap-3">
            <LoadForm 
              v-for="load in po.loads" 
              :key="load.id" 
              :load="load" 
              :po-id="po.id"
              :stores="stores"
              :fuel-types="fuelTypes"
              @refresh="$emit('refresh')"
            />
          </div>
          <div v-else class="text-center py-3 bg-black-custom border border-secondary mb-3">
            <span class="mono text-muted-custom small">[ NO CARGO LOADS LOGGED FOR THIS PURCHASE ORDER ]</span>
          </div>

          <!-- Add Load to PO -->
          <div class="text-end">
            <button @click="addDraftLoad(po.id)" class="btn btn-outline-primary btn-sm mono fw-bold">
              <i class="fas fa-plus me-2"></i> ADD_CARGO_LOAD
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="text-center py-5 bg-black-custom border border-secondary">
      <i class="fas fa-file-invoice fa-3x text-muted-custom mb-3 opacity-25"></i>
      <p class="mono text-muted-custom small mb-0">[ NO ACTIVE PURCHASE ORDERS REGISTERED ]</p>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, reactive, watch } from 'vue';
import api from '../../api';
import LoadForm from './LoadForm.vue';

export default defineComponent({
  name: 'PurchaseOrders',
  components: { LoadForm },
  props: {
    missionId: {
      type: Number,
      required: true
    },
    purchaseOrders: {
      type: Array as () => any[],
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
    const showAddPo = ref<boolean>(false);
    const newPoNumber = ref<number | null>(null);
    const expandedPOs = reactive<Record<number, boolean>>({});

    // Watch PO list changes to preserve or initialize expanded states
    watch(() => props.purchaseOrders, (newVal) => {
      newVal.forEach(po => {
        if (expandedPOs[po.id] === undefined) {
          expandedPOs[po.id] = false;
        }
      });
    }, { immediate: true, deep: true });

    const togglePo = (id: number) => {
      expandedPOs[id] = !expandedPOs[id];
    };

    const submitNewPo = async () => {
      if (!newPoNumber.value) return;
      try {
        const response = await api.post(`/missions/${props.missionId}/pos/`, {
          po_number: newPoNumber.value
        });
        if (response.data.status === 'success') {
          const newPo = response.data.po;
          newPoNumber.value = null;
          showAddPo.value = false;
          expandedPOs[newPo.id] = true; // Auto expand new PO
          emit('refresh');
        }
      } catch (error: any) {
        alert(error.response?.data?.message || "Failed to create PO.");
      }
    };

    const deletePo = async (id: number) => {
      if (!confirm("CRITICAL PROTOCOL: Deleting this Purchase Order will permanently erase all child cargo deliveries. Confirm?")) return;
      try {
        const response = await api.delete(`/pos/${id}/`);
        if (response.data.status === 'success') {
          emit('refresh');
        }
      } catch (error) {
        alert("Failed to delete PO.");
      }
    };

    const addDraftLoad = (poId: number) => {
      // Append a draft load locally to render an empty LoadForm
      // In a decoupled setup, we can let LoadForm save it directly to Django!
      const po = props.purchaseOrders.find(p => p.id === poId);
      if (po) {
        // If there's already an unsaved draft, don't add another one
        const hasDraft = po.loads.some((l: any) => !l.id);
        if (hasDraft) {
          alert("Please complete the current unsaved cargo record first.");
          return;
        }
        po.loads.push({
          id: null,
          fuel_type_id: null,
          store_id: null,
          price_at_store: null,
          gross_gal: null,
          net_gal: null,
          temp: 60.0,
          grav: 45.0,
          start_inches: null,
          start_gallons: null,
          end_inches: null,
          end_gallons: null
        });
      }
    };

    return {
      showAddPo,
      newPoNumber,
      expandedPOs,
      togglePo,
      submitNewPo,
      deletePo,
      addDraftLoad
    };
  }
});
</script>

<style scoped>
.bg-black-custom {
  background-color: #0b0d0f;
}
.po-card {
  border-radius: 0;
  background-color: #171a1d;
  transition: border-color 0.2s ease;
}
.po-header {
  user-select: none;
}
.cursor-pointer {
  cursor: pointer;
}
.btn-xs {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
}
</style>
