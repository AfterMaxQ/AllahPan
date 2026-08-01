<template>
  <div class="grid-container">
    <FileCard
      v-for="file in files"
      :key="file.id"
      :file="file"
      :is-selected="selectedIds.includes(file.id)"
      @contextmenu="(e) => $emit('item-contextmenu', e, file)"
      @toggle-select="$emit('item-toggle-select', file)"
      @open="$emit('item-open', file)"
    />
  </div>
</template>

<script setup>
import FileCard from './FileCard.vue'

defineProps({
  files: { type: Array, required: true },
  selectedIds: { type: Array, default: () => [] },
})
defineEmits(['item-contextmenu', 'item-toggle-select', 'item-open'])
</script>

<style scoped>
.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(176px, 1fr));
  align-items: stretch;
  gap: clamp(12px, 1.4vw, 18px);
}

@media (min-width: 1440px) {
  .grid-container {
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  }
}

@media (min-width: 769px) and (max-width: 1024px) {
  .grid-container {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
  }
}

@media (max-width: 768px) {
  .grid-container {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
}

@media (max-width: 300px) {
  .grid-container { grid-template-columns: 1fr; }
}
</style>
