<script setup lang="ts">
import { ref, onMounted } from 'vue';
import api from './api';

interface Mission {
  id: number;
  date: string;
  miles_started: number;
  miles_ended: number;
  truck_fuel_gallons: string;
  notes: string;
}

const missions = ref<Mission[]>([]);
const loading = ref(true);
const error = ref('');

const fetchMissions = async () => {
  try {
    loading.value = true;
    const response = await api.get('/missions/');
    missions.value = response.data;
  } catch (err: any) {
    error.value = 'Failed to load missions. Ensure you are logged into webNexus.';
    console.error(err);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchMissions);
</script>

<template>
  <div class="mission-log-container">
    <header class="tactical-header">
      <h1>[ MISSION_LOG_v1.0 ]</h1>
      <p class="status-badge">OPERATIONAL</p>
    </header>

    <main class="dashboard">
      <section v-if="loading" class="loading-state">
        <p>RETRIVING DATA...</p>
      </section>

      <section v-else-if="error" class="error-state">
        <p>{{ error }}</p>
      </section>

      <section v-else class="mission-list">
        <h2>DAILY_ENTRIES</h2>
        <div v-if="missions.length === 0" class="empty-state">
          <p>NO MISSIONS LOGGED. READY FOR NEW ENTRY.</p>
        </div>
        <table v-else class="tactical-table">
          <thead>
            <tr>
              <th>DATE</th>
              <th>MILES</th>
              <th>FUEL_GAL</th>
              <th>NOTES</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="mission in missions" :key="mission.id">
              <td>{{ mission.date }}</td>
              <td>{{ mission.miles_ended - mission.miles_started }}</td>
              <td>{{ mission.truck_fuel_gallons }}</td>
              <td>{{ mission.notes }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
</template>

<style>
/* Tactical Base Camp Aesthetic */
:root {
  --tactical-bg: #1a1a1a;
  --tactical-amber: #ffb86c;
  --tactical-gray: #44475a;
  --tactical-white: #f8f8f2;
}

body {
  background-color: var(--tactical-bg);
  color: var(--tactical-white);
  font-family: 'JetBrains Mono', monospace;
  margin: 0;
  padding: 20px;
}

.mission-log-container {
  max-width: 900px;
  margin: 0 auto;
  border: 1px solid var(--tactical-gray);
  padding: 20px;
  background-color: #282a36;
}

.tactical-header {
  border-bottom: 2px solid var(--tactical-amber);
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tactical-header h1 {
  margin: 0;
  color: var(--tactical-amber);
  font-size: 1.5rem;
}

.status-badge {
  background-color: var(--tactical-amber);
  color: #000;
  padding: 2px 8px;
  font-weight: bold;
  font-size: 0.8rem;
}

.tactical-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}

.tactical-table th, .tactical-table td {
  border: 1px solid var(--tactical-gray);
  padding: 10px;
  text-align: left;
}

.tactical-table th {
  background-color: var(--tactical-gray);
  color: var(--tactical-amber);
}

.tactical-table tr:hover {
  background-color: #383a59;
}

.loading-state, .error-state, .empty-state {
  text-align: center;
  padding: 40px;
  color: var(--tactical-amber);
  border: 1px dashed var(--tactical-amber);
}
</style>
