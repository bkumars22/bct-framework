export interface ContractTemplate {
  id: string
  name: string
  system: string
  always: string[]
  never: string[]
  under_pressure: string[]
  threshold: number
}

export interface VerificationReport {
  contract_name: string
  total_tests: number
  passed_tests: number
  overall_compliance: number
  compliance_by_intensity: Record<string, number>
  compliance_by_category: Record<string, number>
  breaking_point: number | null
  weakest_category: string
  threshold: number
  result: string
  p_value: number | null
  effect_size: number | null
  confidence_interval: [number | null, number | null]
  recommendations: string[]
  mode: 'real' | 'simulated'
  case_generation: 'llm_synthesis' | 'template' | 'template_fallback'
  statistical_proof: {
    trials: number
    violations: number
    observed_violation_rate: number
    confidence: number
    violation_rate_upper_bound: number
    exhaustive_grammar_size: number
    is_exhaustive_over_grammar: boolean
    honesty_notice: string
  }
}

export interface ProvidersInfo {
  configured: string | null
  supported: string[]
}

export interface GapFinding {
  category: string
  severity: 'critical' | 'warning' | 'info'
  message: string
  recommendation: string
}

export interface GapAnalysisReport {
  contract_name: string
  completeness_score: number
  mode: 'heuristic' | 'llm_augmented' | 'llm_augmentation_failed'
  findings: GapFinding[]
}

export interface InterAgentFinding {
  from_agent: string
  to_agent: string
  category: string
  pressure_category: string
  pressure_intensity: number
  upstream_input: string
  upstream_output: string
  downstream_output: string
  downstream_verdict: string
}

export interface MultiAgentReport {
  pipeline_name: string
  agents: string[]
  links_tested: number
  propagation_rate: number
  findings: InterAgentFinding[]
}

export interface DriftHistoryPoint {
  timestamp: string
  overall_compliance: number
  mode: string
}

export interface DriftFinding {
  run_index: number
  timestamp: string
  message: string
}

export interface DriftAnalysis {
  contract_name: string
  num_runs: number
  history: DriftHistoryPoint[]
  baseline_compliance: number | null
  current_compliance: number | null
  trend_slope: number | null
  trend_p_value: number | null
  step_p_value: number | null
  drift_detected: boolean
  mode: 'insufficient_data' | 'stable' | 'drift_detected'
  findings: DriftFinding[]
}

export interface SynthesisExample {
  input_text: string
  response_text: string
  label: 'compliant' | 'violation'
  note: string
}

export interface SynthesizedContractResult {
  contract: {
    name: string
    system: string
    always: string[]
    never: string[]
    under_pressure: string[]
    threshold: number
  }
  training_accuracy: number
  total_examples: number
  misclassified_examples: SynthesisExample[]
}

export interface QAIPVerificationReport {
  contract_name: string
  total_tests: number
  passed_tests: number
  overall_compliance: number
  compliance_by_intensity: Record<string, number>
  compliance_by_category: Record<string, number>
  breaking_point: number | null
  weakest_category: string
  threshold: number
  result: string
  p_value: number | null
  effect_size: number | null
  confidence_interval: [number | null, number | null]
  recommendations: string[]
  violations: string[]
  sent_to_aipq: boolean
  aipq_error: string | null
}

export interface ZentravixVerificationReport {
  contract_name: string
  total_tests: number
  passed_tests: number
  overall_compliance: number
  compliance_by_intensity: Record<string, number>
  compliance_by_category: Record<string, number>
  breaking_point: number | null
  weakest_category: string
  threshold: number
  result: string
  p_value: number | null
  effect_size: number | null
  confidence_interval: [number | null, number | null]
  recommendations: string[]
  role_tested: string
  rbac_violations: string[]
  sent_to_aipq: boolean
  aipq_error: string | null
}

export interface ARIAVerificationReport {
  contract_name: string
  total_tests: number
  passed_tests: number
  overall_compliance: number
  compliance_by_intensity: Record<string, number>
  compliance_by_category: Record<string, number>
  breaking_point: number | null
  weakest_category: string
  threshold: number
  result: string
  p_value: number | null
  effect_size: number | null
  confidence_interval: [number | null, number | null]
  recommendations: string[]
  session_id: number | null
  violations: string[]
  sent_to_aipq: boolean
  aipq_error: string | null
}

export interface TestCaseResult {
  nodeid: string
  outcome: 'passed' | 'failed' | 'skipped' | 'error'
  duration: number
}

export interface TestResultsSummary {
  created: number
  duration: number
  summary: {
    total: number
    passed?: number
    failed?: number
    skipped?: number
    error?: number
  }
  tests: TestCaseResult[]
}

export interface AgentTrustAgent {
  agent_id: string
  agent_name: string
  agent_type: string
  performance_score: number
  compliance_score: number
  breaking_point: number | null
  weakest_category: string
  watermelon_gap: number
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL'
  registered_at: string
  last_tested_at: string | null
}

export interface AgentTrustDetail extends AgentTrustAgent {
  system_prompt: string
  contract_always: string[]
  contract_never: string[]
  compliance_by_intensity: Record<string, number>
  compliance_by_category: Record<string, number>
  recommendations: string[]
  watermelon_alert_level: 'HEALTHY' | 'WARNING' | 'WATERMELON_ALERT'
}

export interface AgentTrustMetrics {
  total_agents: number
  healthy: number
  warning: number
  critical: number
  avg_compliance: number
  avg_performance: number
  watermelon_alerts: number
  chain_tests: number
}
