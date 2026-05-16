<template>
  <div class="project-detail">
    <p>ProjectDetailView — projectId: {{ projectId }}</p>
  </div>
</template>

<script setup>
defineProps({ projectId: String })
</script>
