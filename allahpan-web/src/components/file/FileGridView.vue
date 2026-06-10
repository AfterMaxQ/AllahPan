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
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}
</style>
