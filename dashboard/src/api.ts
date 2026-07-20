/**
 * Thin API client. In demo mode (GitHub Pages build, VITE_DEMO_MODE=true —
 * no live backend) every call returns a canned fixture from demoData.ts
 * instead of hitting the network; otherwise behavior is identical to a
 * plain fetch() against the real API. A small artificial delay in demo
 * mode keeps the loading state from being an imperceptible flash, same as
 * a real request would produce.
 */
import {
  DEMO_ARIA_REPORT, DEMO_DRIFT_REPORT, DEMO_GAP_REPORT, DEMO_PIPELINE_REPORT, DEMO_PROVIDERS, DEMO_QAIP_REPORT,
  DEMO_SYNTHESIS_RESULT, DEMO_TEMPLATES, DEMO_VERIFICATION_REPORT, DEMO_ZENTRAVIX_REPORT,
} from './demoData'
import type {
  ARIAVerificationReport, ContractTemplate, DriftAnalysis, GapAnalysisReport, MultiAgentReport, ProvidersInfo,
  QAIPVerificationReport, SynthesizedContractResult, TestResultsSummary, VerificationReport, ZentravixVerificationReport,
} from './types'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8010'
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

const demoDelay = <T,>(value: T): Promise<T> => new Promise(resolve => setTimeout(() => resolve(value), 400))

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(errBody.detail || `${resp.status} ${resp.statusText}`)
  }
  return resp.json() as Promise<T>
}

export async function fetchProviders(): Promise<ProvidersInfo> {
  if (DEMO_MODE) return demoDelay(DEMO_PROVIDERS)
  const resp = await fetch(`${API_URL}/providers`)
  return resp.json()
}

export async function fetchTemplates(): Promise<ContractTemplate[]> {
  if (DEMO_MODE) return demoDelay(DEMO_TEMPLATES)
  const resp = await fetch(`${API_URL}/templates`)
  return resp.json()
}

export interface ContractPayload {
  name: string
  system: string
  topic?: string
  threshold: number
  always: string[]
  never: string[]
  under_pressure: string[]
}

export async function verifyContract(payload: ContractPayload): Promise<VerificationReport> {
  if (DEMO_MODE) return demoDelay(DEMO_VERIFICATION_REPORT)
  return postJson<VerificationReport>('/verify', payload)
}

export async function analyzeGaps(payload: ContractPayload): Promise<GapAnalysisReport> {
  if (DEMO_MODE) return demoDelay(DEMO_GAP_REPORT)
  return postJson<GapAnalysisReport>('/analyze-gaps', payload)
}

export interface PipelineAgentPayload {
  name: string
  system: string
  never: string[]
}

export async function verifyPipeline(agents: PipelineAgentPayload[]): Promise<MultiAgentReport> {
  if (DEMO_MODE) return demoDelay(DEMO_PIPELINE_REPORT)
  return postJson<MultiAgentReport>('/verify-pipeline', {
    pipeline_name: 'dashboard_pipeline', cases_per_link: 5, agents,
  })
}

export async function checkDrift(contractName: string): Promise<DriftAnalysis> {
  if (DEMO_MODE) return demoDelay(DEMO_DRIFT_REPORT)
  const resp = await fetch(`${API_URL}/drift/${encodeURIComponent(contractName)}?min_runs=3`)
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(body.detail || `${resp.status} ${resp.statusText}`)
  }
  return resp.json()
}

export interface SynthesisExamplePayload {
  input_text: string
  response_text: string
  label: 'compliant' | 'violation'
  note: string
}

export async function synthesizeContract(
  name: string, examples: SynthesisExamplePayload[],
): Promise<SynthesizedContractResult> {
  if (DEMO_MODE) return demoDelay(DEMO_SYNTHESIS_RESULT)
  return postJson<SynthesizedContractResult>('/synthesize-contract', { name, examples })
}

/**
 * QAIP and ZENTRAVIX have no simulation mode of their own — their
 * adapters always call a real endpoint — so in demo mode (GitHub Pages,
 * no live QAIP/ZENTRAVIX instance to reach) these return an illustrative
 * canned fixture instead, clearly not a claim about any real deployment.
 */
export interface AipqTrackingOptions {
  aipqUrl?: string
  aipqPromptId?: number
  aipqApiKey?: string
}

export async function verifyQaip(serviceUrl: string, aipq?: AipqTrackingOptions): Promise<QAIPVerificationReport> {
  if (DEMO_MODE) return demoDelay(DEMO_QAIP_REPORT)
  return postJson<QAIPVerificationReport>('/verify-qaip', {
    service_url: serviceUrl, aipq_url: aipq?.aipqUrl || null,
    aipq_prompt_id: aipq?.aipqPromptId || null, aipq_api_key: aipq?.aipqApiKey || null,
  })
}

export async function verifyZentravix(serviceUrl: string, aipq?: AipqTrackingOptions): Promise<ZentravixVerificationReport> {
  if (DEMO_MODE) return demoDelay(DEMO_ZENTRAVIX_REPORT)
  return postJson<ZentravixVerificationReport>('/verify-zentravix', {
    service_url: serviceUrl, aipq_url: aipq?.aipqUrl || null,
    aipq_prompt_id: aipq?.aipqPromptId || null, aipq_api_key: aipq?.aipqApiKey || null,
  })
}

/**
 * ARIA has no simulation mode either — its adapter always calls the real,
 * session-based endpoint (POST /api/sessions then POST /api/sessions/{id}/chat).
 * In demo mode this returns an illustrative canned fixture, same as QAIP/ZENTRAVIX.
 */
export async function verifyAria(serviceUrl: string, aipq?: AipqTrackingOptions): Promise<ARIAVerificationReport> {
  if (DEMO_MODE) return demoDelay(DEMO_ARIA_REPORT)
  return postJson<ARIAVerificationReport>('/verify-aria', {
    service_url: serviceUrl, aipq_url: aipq?.aipqUrl || null,
    aipq_prompt_id: aipq?.aipqPromptId || null, aipq_api_key: aipq?.aipqApiKey || null,
  })
}

/**
 * Test results are a static JSON file the CI workflow regenerates and
 * deploys alongside the dashboard build on every push to main — not part
 * of the FastAPI backend, so this always fetches from the same origin the
 * dashboard itself was served from (respects Vite's `base`), in both demo
 * and real mode.
 */
export async function fetchTestResults(): Promise<TestResultsSummary> {
  const resp = await fetch(`${import.meta.env.BASE_URL}test-results.json`)
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText} — test-results.json not found`)
  }
  return resp.json()
}
