export type Signal = { phase: 'EW' | 'NS'; displayPhase: 'EW' | 'NS' | 'CLEARANCE'; elapsed: number; owner: 'NORMAL' | 'CORRIDOR' }
export type NodeState = { id: string; x: number; y: number; label: string; queues: { EW: number; NS: number }; signal: Signal }
export type EdgeState = { id: string; source: string; target: string; freeFlowSeconds: number; direction: string; closed: boolean; costSeconds: number | null }
export type EventState = { step: number; kind: string; message: string; [key: string]: unknown }
export type Mission = { id: string; origin: string; destination: string; route: string[]; routeVersion: number; status: string; progress: number; travelSteps: number; reroutes: number; stops: number }
export type State = {
  schemaVersion: string; sourceMode: string; step: number; running: boolean; seed: number; scenario: string; controller: string;
  nodes: NodeState[]; edges: EdgeState[]; corridor: Record<string, string>; mission: Mission | null;
  metrics: { totalQueue: number; meanQueue: number; meanWaitProxy: number; throughput: number; fallbackInterventions: number };
  events: EventState[];
}
export type Perception = { sourceMode: string; effectiveStep: number; calibrated: boolean; notice: string; observations: Array<{intersectionId:string; vehicleCount:number; queueProxy:number; occupancy:number; confidence:number}> }
export type Comparison = { warning: string; results: Array<{ controller:string; meanQueue:number; meanWaitProxy:number; throughput:number }> }
