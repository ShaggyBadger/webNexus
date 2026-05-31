<template>
  <div class="shift-parameters mb-5">
    <div class="mono text-muted-custom small mb-3 text-center">[ OPERATIONAL_LOG_PARAMETERS ]</div>
    <div class="table-responsive mx-auto" style="max-width: 600px;">
      <table class="table table-bordered border-secondary bg-black-custom mono x-small text-light mb-0">
        <thead>
          <tr class="bg-dark-custom text-primary text-uppercase">
            <th scope="col" class="py-2 px-3">PARAMETER</th>
            <th scope="col" class="py-2 px-3 text-end">INPUT_VALUE</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="py-2 px-3 align-middle text-muted-custom">SHIFT START TIME</td>
            <td class="py-0 px-0">
              <input 
                type="datetime-local" 
                :value="modelValue"
                @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
                @blur="$emit('auto-save')"
                class="tactical-input-table w-100 mono text-light text-end border-0"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'ShiftParameters',
  props: {
    modelValue: {
      type: String,
      required: true
    }
  },
  emits: ['update:modelValue', 'auto-save']
});
</script>
