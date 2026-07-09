import { ref, onMounted, onUnmounted } from 'vue'

const mobileQuery = window.matchMedia('(max-width: 768px)')
const tabletQuery = window.matchMedia('(min-width: 769px) and (max-width: 1024px)')

export function useResponsive() {
  const isMobile = ref(mobileQuery.matches)
  const isTablet = ref(tabletQuery.matches)

  const onMobileChange = (e) => { isMobile.value = e.matches }
  const onTabletChange = (e) => { isTablet.value = e.matches }

  onMounted(() => {
    mobileQuery.addEventListener('change', onMobileChange)
    tabletQuery.addEventListener('change', onTabletChange)
  })

  onUnmounted(() => {
    mobileQuery.removeEventListener('change', onMobileChange)
    tabletQuery.removeEventListener('change', onTabletChange)
  })

  return { isMobile, isTablet }
}
