// frontend/src/composables/useHelp.js
import { ref } from 'vue'

const helpOpen = ref(false)
const helpSection = ref('overview')

export function useHelp() {
  function openHelp(section = 'overview') {
    helpSection.value = section
    helpOpen.value = true
  }
  function closeHelp() {
    helpOpen.value = false
  }
  return { helpOpen, helpSection, openHelp, closeHelp }
}
