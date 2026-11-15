export interface Signals {
  blocker: boolean
  data_access: boolean
  scope_change: boolean
  sentiment: number
  pct_done: number | null
}

export interface Decision {
  escalate: boolean
  score: number
  reasons: string[]
  kind: string
}

export interface Note {
  week: number
  text: string
  signals: Signals
  decision: Decision | null
  by?: string
}

export interface GateResult {
  passed: boolean
  recall: number
  grounded: number
  questions: number
  findings: string[]
  misses: string[]
  config?: Record<string, unknown>
}

export interface EngagementSummary {
  id: string
  customer: string
  sector: string
  topology: string
  contract: string
  phase: string
  done: boolean
  dueWeek: number
  weeksLeft: number
  remainingHours: number
  plannedHours: number
  escalatedWeek: number | null
  risk: number
  riskReasons: string[]
  gate: boolean | null
}

export interface EngagementDetail extends EngagementSummary {
  phases: { phase: string; scopedHours: number; dueWeek: number; loggedHours: number; reportedDone: number | null }[]
  notes: Note[]
  team: { fdeId: string; hours: number; phase: string }[]
  requiredSkills: string[]
  workItems: string[]
  gateResult: GateResult | null
  awaitingReview: boolean
}

export interface Person {
  id: string
  name: string
  profile: string
  skills: string[]
  capacityHours: number
  plannedHours: number
  load: number
  hotStreak: number
  work: { engagementId: string; phase: string; hours: number }[]
}

export interface Team {
  week: number
  target: number
  hotLoad: number
  people: Person[]
  warnings: string[]
}

export interface Review {
  engagementId: string
  topology: string
  config: Record<string, unknown>
  documents: number
  goldenQuestions: number
  result: GateResult | null
}

export interface DesignScore {
  label: string
  milestonesOnPlan: number
  surpriseSlips: number
  customerEscalations: number
  utilization: number
  burnoutWeeks: number
  marginShare: number
  productionIncidents: number
  engagementsDeclined: number
}

export interface Report {
  world: { name: string; engagements: number; people: number; weeks: number }
  designs: Record<string, DesignScore>
}
