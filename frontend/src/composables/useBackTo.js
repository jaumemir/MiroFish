import { useRouter } from 'vue-router'

export function useBackTo(defaultRouteName = 'Home') {
  const router = useRouter()

  function navigateBack() {
    const backTo = history.state?.backTo
    if (backTo) {
      router.push(backTo)
    } else {
      router.push({ name: defaultRouteName })
    }
  }

  function pushWithBackTo(route) {
    const backTo = history.state?.backTo
    return router.push({
      ...route,
      state: { ...(route.state || {}), backTo: backTo || undefined },
    })
  }

  return { navigateBack, pushWithBackTo }
}
