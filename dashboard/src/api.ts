/**
 * Thin API client. In demo mode (GitHub Pages build, VITE_DEMO_MODE=true —
 * no live backend) every call returns a canned fixture from demoData.ts
 * instead of hitting the network; otherwise behavior is identical to a
 * plain fetch() against the real API. A small artificial delay in demo
 * mode keeps the loading state from being an imperceptible flash, same as
 * a real request would produce.
 */
import {
  DEMO_DRIFT_REPORT, DEMO_GAP_REPORT, DEMO_PIPELINE_REPORT, DEMO_PROVIDERS,
  DEMO_SYNTHESIS_RESULT, DEMO_VERIFICATION_REPORT,
} from './demoData'
import type {
  DriftAnalysis, GapAnalysisReport, MultiAgentReport, ProvidersInfo,
  SynthesizedContractResult, TestResultsSummary, VerificationReport,
} from './types'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8010'
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

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
