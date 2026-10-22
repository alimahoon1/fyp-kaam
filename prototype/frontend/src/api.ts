async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || 'Request failed')
  }
  return response.json()
}

export const api = {
  state: <T>() => request<T>('/api/state'),
  perception: <T>() => request<T>('/api/perception'),
  compare: <T>() => request<T>('/api/compare?scenario=rush_hour&steps=120'),
  step: <T>(steps = 1) => request<T>('/api/simulation/step', { method: 'POST', body: JSON.stringify({ steps }) }),
  reset: <T>(scenario: string, controller: string) => request<T>('/api/simulation/reset', { method: 'POST', body: JSON.stringify({ seed: 104, scenario, controller }) }),
  controller: <T>(controller: string) => request<T>('/api/controller', { method: 'POST', body: JSON.stringify({ controller }) }),
  dispatch: <T>(origin: string, destination: string) => request<T>('/api/emergency/dispatch', { method: 'POST', body: JSON.stringify({ origin, destination }) }),
  closure: <T>(edgeId: string, closed: boolean) => request<T>('/api/incidents/closure', { method: 'POST', body: JSON.stringify({ edgeId, closed }) }),
}
