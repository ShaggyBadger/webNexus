<template>
  <div class="active-header card bg-dark-custom border-secondary p-4 mb-4">
    <div class="row align-items-center">
      <div class="col-12 col-md-6 text-start mb-3 mb-md-0">
        <div class="mono text-primary small fw-bold mb-1">
          <i class="fas fa-satellite-dish me-2 blink-tactical"></i> ● LOGGING ACTIVE MISSION
        </div>
        <h2 class="mono text-light h4 mb-0 fw-bold uppercase">MISSION: [ {{ formatTime(mission.shift_start) }} ]</h2>
        <span class="mono x-small text-muted-custom mt-1 d-block">[ OPERATOR: AUTHENTICATED ]</span>
      </div>

      <div class="col-12 col-md-6 text-md-end">
        <div class="d-inline-block text-start bg-black-custom p-3 border border-secondary" style="background: rgba(0,0,0,0.3);">
          <div class="mono text-primary x-small fw-bold">[ ELAPSED_ON_DUTY_TIME ]</div>
          <div class="mono display-6 text-light font-weight-bold" style="font-size: 1.8rem;">
            {{ elapsed }}
          </div>
          <span class="mono x-small text-muted-custom d-block mt-1">START_ODO: {{ mission.start_miles }} MI</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, onUnmounted } from 'vue';

export default defineComponent({
  name: 'ActiveHeader',
  props: {
    mission: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const elapsed = ref<string>('00:00:00');
    let timerInterval: any = null;

    const formatTime = (isoString: string) => {
      const d = new Date(isoString);
      const hours = String(d.getHours()).padStart(2, '0');
      const mins = String(d.getMinutes()).padStart(2, '0');
      return `${d.toLocaleDateString()} @ ${hours}${mins}L`;
    };

    const updateTimer = () => {
      const start = new Date(props.mission.shift_start).getTime();
      const diff = Date.now() - start;
      if (diff <= 0) {
        elapsed.value = '00:00:00';
        return;
      }
      const secs = Math.floor(diff / 1000) % 60;
      const mins = Math.floor(diff / 60000) % 60;
      const hours = Math.floor(diff / 3600000);
      
      const pad = (n: number) => String(n).padStart(2, '0');
      elapsed.value = `${pad(hours)}:${pad(mins)}:${pad(secs)}`;
    };

    onMounted(() => {
      updateTimer();
      timerInterval = setInterval(updateTimer, 1000);
    });

    onUnmounted(() => {
      if (timerInterval) clearInterval(timerInterval);
    });

    return {
      elapsed,
      formatTime
    };
  }
});
</script>

<style scoped>
.blink-tactical {
  animation: blinker 1.5s linear infinite;
}
@keyframes blinker {
  50% { opacity: 0.3; }
}
.bg-black-custom {
  background-color: #0b0d0f;
}
</style>
