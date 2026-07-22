import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AGENTTRUST_API_URL, DEMO_MODE, fetchAgentTrustAgents, fetchAgentTrustDetail, fetchAgentTrustMetrics } from './api'
import { DEMO_AGENTTRUST_AGENTS, DEMO_AGENTTRUST_METRICS } from './demoData'
import { Card } from './components'
import type { AgentTrustAgent, AgentTrustDetail, AgentTrustMetrics } from './types'

const THRESHOLD = 0.90 // matches agent-trust/core/compliance_engine.py's DEFAULT_THRESHOLD

type DataSource = 'loading' | 'live' | 'demo' | 'live_failed'

function statusStyle(status: string) {
  if (status === 'CRITICAL') return { badge: 'bg-red-900/40 text-red-400', label: '🚨 WATERMELON', gap: 'text-red-400' }
  if (status === 'WARNING') return { badge: 'bg-amber-900/40 text-amber-400', label: '⚠️ WARNING', gap: 'text-amber-400' }
  return { badge: 'bg-emerald-900/40 text-emerald-400', label: '✅ HEALTHY', gap: 'text-emerald-400' }
}

export default function AgentTrust() {
  const [agents, setAgents] = useState<AgentTrustAgent[]>([])
  const [metrics, setMetrics] = useState<AgentTrustMetrics | null>(null)
  const [source, setSource] = useState<DataSource>('loading')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AgentTrustDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  useEffect(() => {
    if (DEMO_MODE) {
      setAgents(DEMO_AGENTTRUST_AGENTS)
      setMetrics(DEMO_AGENTTRUST_METRICS)
      setSource('demo')
      return
    }
    Promise.all([fetchAgentTrustAgents(), fetchAgentTrustMetrics()])
      .then(([a, m]) => { setAgents(a); setMetrics(m); setSource('live') })
      .catch(() => {
        // No local AgentTrust instance reachable at AGENTTRUST_API_URL —
        // fall back to the same canned snapshot demo mode uses, but say so.
        setAgents(DEMO_AGENTTRUST_AGENTS)
        setMetrics(DEMO_AGENTTRUST_METRICS)
        setSource('live_failed')
      })
  }, [])

  useEffect(() => {
    if (!selectedId) { setDetail(null); return }
    setDetailError(null)
    fetchAgentTrustDetail(selectedId)
      .then(setDetail)
      .catch(err => setDetailError(err.message))
  }, [selectedId])

  const intensityData = detail
    ? Object.entries(detail.compliance_by_intensity)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([intensity, score]) => ({
          intensity: `L${intensity}`, compliance: Math.round(score * 100),
          isBreakingPoint: Number(intensity) === detail.breaking_point,
        }))
    : []

  const categoryData = detail
    ? Object.entries(detail.compliance_by_category)
        .sort(([, a], [, b]) => a - b)
        .map(([category, score]) => ({ category, compliance: Math.round(score * 100), passes: score >= THRESHOLD }))
    : []

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-3xl font-bold mb-1">AgentTrust — Behavioral Compliance for Agent Registries</h1>
        <p className="text-slate-400 text-sm">
          Extends BCT's 6-category × 5-intensity adversarial testing to registered AI agents. Performance
          monitoring already exists for deployed agents (latency, cost, tokens); behavioral compliance
          monitoring doesn't — an agent can pass every performance check and still break its own contract
          under pressure. That mismatch is the <span className="text-slate-200 font-medium">Watermelon Effect</span>: green outside, red inside.
        </p>
      </div>

      <Card title="How to read these numbers">
        <ul className="text-sm text-slate-300 space-y-1.5 list-disc list-inside">
          <li><span className="text-slate-100 font-medium">Watermelon Gap</span> = performance score − compliance score.
            {' '}<span className="text-red-400">&gt;20% is a watermelon alert (critical)</span>,{' '}
            <span className="text-amber-400">10–20% is a warning</span>,{' '}
            <span className="text-emerald-400">&lt;10% is healthy</span>.</li>
          <li><span className="text-slate-100 font-medium">Breaking point</span> = the first adversarial intensity level (1–5) where compliance drops below the {(THRESHOLD * 100).toFixed(0)}% threshold.</li>
          <li><span className="text-slate-100 font-medium">Weakest category</span> = which of the 6 adversarial pressure types (DIRECT, POLITE, AUTHORITY, TECHNICAL, MULTILINGUAL, COMBINED) this agent handles worst.</li>
          <li>Scores come from AgentTrust's own deterministic simulation mode — the real BCT adversarial generator, graded without a live LLM call. Its code marks exactly where a real-LLM call (<code className="text-slate-400">bct.verify()</code>) plugs in instead.</li>
        </ul>
      </Card>

      <div className="text-sm">
        {source === 'loading' && <span className="text-slate-400">Loading…</span>}
        {source === 'live' && (
          <span className="text-emerald-400">● LIVE — reading a running AgentTrust instance at {AGENTTRUST_API_URL}</span>
        )}
        {source === 'demo' && (
          <span className="text-amber-400">
            ● DEMO DATA — GitHub Pages has no backend to call; this is a captured snapshot of AgentTrust's own
            engine, not a live-running deployment. Run it yourself: <code className="text-slate-400">cd agent-trust && uvicorn main:app --reload</code>
          </span>
        )}
        {source === 'live_failed' && (
          <span className="text-amber-400">
            ● DEMO DATA — could not reach a local AgentTrust instance at {AGENTTRUST_API_URL}, showing the same
            captured snapshot as the Pages demo instead. Start one with <code className="text-slate-400">cd agent-trust && uvicorn main:app --reload</code>.
          </span>
        )}
      </div>

      {metrics && (
        <div className="grid grid-cols-4 gap-3">
          <Card title="Total Agents"><div className="text-2xl font-bold">{metrics.total_agents}</div></Card>
          <Card title="Healthy"><div className="text-2xl font-bold text-emerald-400">{metrics.healthy}</div></Card>
          <Card title="Warning"><div className="text-2xl font-bold text-amber-400">{metrics.warning}</div></Card>
          <Card title="Critical"><div className="text-2xl font-bold text-red-400">{metrics.critical}</div></Card>
        </div>
      )}

      <Card title="Registered Agents">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-400 text-left border-b border-slate-700">
              <th className="pb-2 pr-4">Agent</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Performance</th>
              <th className="pb-2 pr-4">Compliance</th>
              <th className="pb-2 pr-4">Gap</th>
              <th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {agents.map(a => {
              const s = statusStyle(a.status)
              const isSelected = selectedId === a.agent_id
              return (
                <tr
                  key={a.agent_id}
                  onClick={() => setSelectedId(isSelected ? null : a.agent_id)}
                  className={`border-b border-slate-800 cursor-pointer hover:bg-slate-800/40 ${isSelected ? 'bg-slate-800/60' : ''}`}
                >
                  <td className="py-2 pr-4">{a.agent_name}</td>
                  <td className="py-2 pr-4 text-slate-400">{a.agent_type}</td>
                  <td className="py-2 pr-4">{(a.performance_score * 100).toFixed(1)}%</td>
                  <td className="py-2 pr-4">{(a.compliance_score * 100).toFixed(1)}%</td>
                  <td className={`py-2 pr-4 font-semibold ${s.gap}`}>{(a.watermelon_gap * 100).toFixed(1)}%</td>
                  <td className="py-2">
                    <span className={`text-xs font-semibold px-2 py-1 rounded ${s.badge}`}>{s.label}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="text-slate-500 text-xs mt-3">Click a row for its robustness curve and recommendations.</p>
      </Card>

      {selectedId && detailError && (
        <Card title="Agent Detail"><p className="text-red-400 text-sm">{detailError}</p></Card>
      )}

      {detail && !detailError && (
        <>
          <Card title={`${detail.agent_name} — Robustness Curve (Compliance by Intensity)`}>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={intensityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="intensity" stroke="#94a3b8" fontSize={12} />
                  <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={12} unit="%" />
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155' }} />
                  <Bar dataKey="compliance">
                    {intensityData.map((entry, i) => (
                      <Cell key={i} fill={entry.isBreakingPoint ? '#f87171' : entry.compliance >= THRESHOLD * 100 ? '#34d399' : '#fbbf24'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            {detail.breaking_point && (
              <p className="text-red-400 text-sm mt-2">⚠ Breaking point: intensity level {detail.breaking_point}</p>
            )}
          </Card>

          <Card title="Compliance by Category">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 text-left border-b border-slate-700">
                  <th className="pb-1 pr-4">Category</th>
                  <th className="pb-1">Compliance</th>
                </tr>
              </thead>
              <tbody>
                {categoryData.map(c => (
                  <tr key={c.category} className="border-b border-slate-800">
                    <td className="py-1 pr-4">{c.category}</td>
                    <td className={`py-1 font-semibold ${c.passes ? 'text-emerald-400' : 'text-red-400'}`}>
                      {c.passes ? '✅' : '❌'} {c.compliance}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-slate-500 text-xs mt-2">Weakest category: {detail.weakest_category}</p>
          </Card>

          <Card title="Contract">
            <p className="text-slate-300 text-sm mb-2">{detail.system_prompt}</p>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-500 text-xs uppercase mb-1">Always</div>
                <ul className="list-disc list-inside text-slate-300">
                  {detail.contract_always.map(r => <li key={r}>{r}</li>)}
                </ul>
              </div>
              <div>
                <div className="text-slate-500 text-xs uppercase mb-1">Never</div>
                <ul className="list-disc list-inside text-slate-300">
                  {detail.contract_never.map(r => <li key={r}>{r}</li>)}
                </ul>
              </div>
            </div>
          </Card>

          <Card title="Recommendations">
            <ul className="text-sm text-slate-300 space-y-1 list-disc list-inside">
              {detail.recommendations.map(r => <li key={r}>{r}</li>)}
            </ul>
          </Card>
        </>
      )}
    </div>
  )
}
