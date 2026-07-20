import { Card } from './components'

interface ProjectInfo {
  name: string
  whatBctTests: string
  status: 'wired' | 'receiver' | 'not_connected'
  sectionId?: string
}

const PROJECTS: ProjectInfo[] = [
  {
    name: 'QAIP',
    whatBctTests: 'Defect-explanation accuracy under adversarial pressure — malformed/ambiguous/foreign-language/'
      + 'duplicate/oversized failure messages, plus authority and urgency pressure to force a specific answer.',
    status: 'wired',
    sectionId: 'qaip-section',
  },
  {
    name: 'ZENTRAVIX',
    whatBctTests: 'Role-based access control (RBAC) boundaries — authority claims, urgency escalation, and '
      + 'technical injection all trying to make a lower-privileged role receive higher-privileged data.',
    status: 'wired',
    sectionId: 'zentravix-section',
  },
  {
    name: 'AIPQ',
    whatBctTests: 'Receives BCT verification results via POST /prompts/{id}/bct-result for prompt-version quality '
      + 'tracking (fill in an AIPQ prompt ID + API key on the QAIP/ZENTRAVIX panels) — verified working against a '
      + 'real AIPQ deployment. Not itself tested by BCT; it only receives results, doesn\'t generate them.',
    status: 'receiver',
  },
  {
    name: 'ARIA',
    whatBctTests: 'Socratic-tutor contract under adversarial pressure — DIRECT/AUTHORITY/ROLEPLAY/TECHNICAL '
      + 'pressure to force a direct answer, MULTILINGUAL pressure (Hindi/Tamil), and EMOTIONAL (frustration) '
      + 'pressure. Session-based (POST /api/sessions, then POST /api/sessions/{id}/chat) — bct/integrations/aria.py '
      + 'creates one real session and threads every adversarial case through it as a genuine growing conversation, '
      + 'the same way ARIA\'s own frontend would.',
    status: 'wired',
    sectionId: 'aria-section',
  },
  {
    name: 'AIMO',
    whatBctTests: 'No equivalent endpoint exists yet — its API is pipeline/incident CRUD and monitoring, not a '
      + '"send a question, get an LLM-generated answer" endpoint BCT could adversarially test. Needs a new '
      + 'endpoint on AIMO\'s side (e.g. an incident-explanation route) before an adapter can be built here.',
    status: 'not_connected',
  },
]

export default function Projects({ onGoToSection }: { onGoToSection: (sectionId: string) => void }) {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-3xl font-bold mb-1">Connected Projects</h1>
        <p className="text-slate-400 text-sm">
          Real systems BCT tests against their own live API endpoint, not a generic contract form.
        </p>
      </div>

      {PROJECTS.map(p => (
        <Card key={p.name} title={p.name}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <span className={`text-xs font-semibold px-2 py-1 rounded ${
                p.status === 'wired' ? 'bg-emerald-900/40 text-emerald-400'
                  : p.status === 'receiver' ? 'bg-sky-900/40 text-sky-400'
                    : 'bg-slate-700 text-slate-400'
              }`}>
                {p.status === 'wired' ? 'WIRED' : p.status === 'receiver' ? 'RECEIVES RESULTS' : 'NOT CONNECTED'}
              </span>
              <p className="text-slate-300 text-sm mt-2">{p.whatBctTests}</p>
            </div>
            {p.status === 'wired' && p.sectionId && (
              <button
                onClick={() => onGoToSection(p.sectionId!)}
                className="shrink-0 px-3 py-2 rounded-md bg-sky-600 hover:bg-sky-500 text-sm font-medium whitespace-nowrap"
              >
                Test it →
              </button>
            )}
          </div>
        </Card>
      ))}
    </div>
  )
}
