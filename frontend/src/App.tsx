import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import {
  api, setApiKey, type Candidate, type CandidatePage, type Job, type Manifest,
  type Run, type RunInput, type SolveResult,
} from './api';

type Page = 'home' | 'experiments' | 'playground';
type IconName = 'home' | 'layers' | 'sliders' | 'arrow' | 'check' | 'close' | 'download' |
  'play' | 'stop' | 'external' | 'shield' | 'chart' |
  'menu' | 'clock' | 'copy' | 'info' | 'chevron' | 'database' | 'search' | 'activity';

const DEFAULT_INPUT: RunInput = {
  seed: 42, machines: 4, job_count: 24, case_count: 8, holdout_count: 4, candidate_limit: 500,
};
const SMALL_INPUT: RunInput = {
  seed: 42, machines: 3, job_count: 10, case_count: 3, holdout_count: 2, candidate_limit: 60,
};
const DEEP_INPUT: RunInput = {
  seed: 42, machines: 6, job_count: 40, case_count: 12, holdout_count: 8, candidate_limit: 1500,
};
const EMPTY_CANDIDATES: CandidatePage = { total: 0, items: [] };

const humanDate = (value: string) => new Date(value).toLocaleString(undefined, {
  month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
});
const signedGain = (score: number | null) => score === null ? 'Not measured' : `${((1 - score) * 100) >= 0 ? '+' : ''}${((1 - score) * 100).toFixed(2)}%`;
const scoreLabel = (score: number | null) => score === null ? '—' : score.toFixed(3);
const statusLabel = (value: string) => ({
  queued: 'Waiting', running: 'Running', succeeded: 'Completed', failed: 'Failed',
  cancelled: 'Cancelled', valid: 'Valid', invalid: 'Rejected',
}[value] ?? value);
const activeJob = (job: Job) => job.status === 'queued' || job.status === 'running';
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';

const paths: Record<IconName, ReactNode> = {
  home: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
  sliders: <><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="17" r="2"/></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  close: <path d="M5 5l14 14M19 5 5 19"/>,
  download: <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>,
  play: <path d="m8 5 11 7-11 7V5Z"/>,
  stop: <rect x="5" y="5" width="14" height="14" rx="2"/>,
  external: <path d="M13 4h7v7m0-7L10 14M20 14v6H4V4h6"/>,
  shield: <><path d="M12 2 4 6v6c0 5 3 8 8 10 5-2 8-5 8-10V6l-8-4Z"/><path d="m9 12 2 2 4-4"/></>,
  chart: <><path d="M3 3v18h18M6 16l5-5 3 3 5-7"/></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  database: <><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4 4"/></>,
  activity: <path d="M2 12h4l3-7 6 14 3-7h4"/>,
};
function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function Tag({ status }: { status: string }) {
  return <span className={`status status-${status}`}><span className="status-dot" />{statusLabel(status)}</span>;
}
function SectionHeading({ eyebrow, title, note, action }: {
  eyebrow?: string; title: string; note?: string; action?: ReactNode;
}) {
  return <div className="section-heading"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}
    <h2>{title}</h2>{note && <p className="section-note">{note}</p>}</div>{action && <div className="section-action">{action}</div>}</div>;
}
function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-symbol"><Icon name="layers" size={26}/></div>
    <strong>{title}</strong><p>{text}</p>{action}</div>;
}
function StatCard({ label, value, hint, accent }: {
  label: string; value: string; hint: string; accent?: boolean;
}) {
  return <div className={`metric-card${accent ? ' metric-accent' : ''}`}><p>{label}</p><strong>{value}</strong><small>{hint}</small></div>;
}
function WorkloadBars({ loads }: { loads: number[] }) {
  const max = Math.max(...loads, 1);
  return <div className="machine-list" aria-label="Machine load distribution">{loads.map((load, index) => <div className="machine-row" key={index}>
    <span className="machine-label">Machine {index + 1}</span>
    <div className="machine-track" role="meter" aria-label={`Machine ${index + 1} load`} aria-valuemin={0} aria-valuemax={max} aria-valuenow={load}>
      <span style={{ width: `${load / max * 100}%` }} /></div><strong>{load}</strong></div>)}</div>;
}

function ScheduleTimeline({ durations, assignments, machines, makespan }: {
  durations: number[]; assignments: number[]; machines: number; makespan: number;
}) {
  const rows = Array.from({ length: machines }, (_, machine) => durations
    .map((duration, index) => ({ duration, index }))
    .filter(job => assignments[job.index] === machine));
  return <div className="timeline-block">
    <div className="card-subheading"><h4>Where the jobs went</h4><span>Each block is one job · hover for details</span></div>
    <div className="timeline-grid" aria-label="Job assignments by machine">{rows.map((jobs, machine) => <div className="timeline-row" key={machine}>
      <span className="timeline-label">M{machine + 1}</span>
      <div className="timeline-track" aria-label={`Machine ${machine + 1}: ${jobs.map(job => `job ${job.index + 1} takes ${job.duration}`).join(', ') || 'no jobs'}`}>
        {jobs.map(job => <span key={job.index} className="timeline-job"
          style={{ width: `${job.duration / Math.max(makespan, 1) * 100}%` }}
          title={`Job ${job.index + 1} · ${job.duration} time units`}>
          {job.duration / Math.max(makespan, 1) >= .1 ? job.index + 1 : ''}
        </span>)}
      </div>
    </div>)}</div>
    <p className="muted-small">Block labels are job numbers from your input. Block width shows how long each job runs.</p>
  </div>;
}

function CaseChart({ values, name }: { values: number[] | null; name: string }) {
  if (!values?.length) return <p className="subtle-placeholder">No {name.toLowerCase()} cases available.</p>;
  const top = Math.max(1.08, ...values) + 0.02;
  const bottom = Math.max(0, Math.min(0.90, ...values) - 0.02);
  const scale = (value: number) => 130 - ((value - bottom) / (top - bottom)) * 107;
  const pts = values.map((value, index) => `${36 + (index / Math.max(values.length - 1, 1)) * 506},${scale(value)}`).join(' ');
  return <div className={`case-plot${name === 'Holdout' ? ' case-plot-holdout' : ''}`}>
    <div className="chart-heading"><span>{name} cases</span><small>Lower is better · LPT = 1.000</small></div>
    <svg viewBox="0 0 580 174" role="img" aria-label={`${name} makespan ratios: ${values.map(value => value.toFixed(3)).join(', ')}`}>
      <line x1="36" y1={scale(1)} x2="542" y2={scale(1)} className="baseline-line" strokeDasharray="5 5" />
      <line x1="36" y1="140" x2="542" y2="140" className="axis-line" />
      <text x="36" y={Math.max(12, scale(1) - 7)} className="axis-caption">LPT baseline</text>
      <polyline points={pts} className="chart-line" />
      {values.map((value, index) => <circle key={index} cx={36 + (index / Math.max(values.length - 1, 1)) * 506}
        cy={scale(value)} r="4" className="chart-point" />)}
      <text x="36" y="160" className="axis-caption">Case 1</text>
      <text x="542" y="160" className="axis-caption" textAnchor="end">Case {values.length}</text>
    </svg>
  </div>;
}

function CandidateInspector({ candidate, manifest, machineCount }: {
  candidate: Candidate; manifest: Manifest | null; machineCount: number;
}) {
  const firstCase = manifest?.workloads[0] ?? [];
  const schedule = candidate.preview_assignments;
  const loads = schedule?.length === firstCase.length ? Array.from({ length: machineCount }, (_, machine) =>
    firstCase.reduce((sum, duration, index) => sum + (schedule[index] === machine ? duration : 0), 0)) : null;
  return <div className="inspector">
    <div className="inspector-title"><div><p className="eyebrow">Recipe {candidate.ordinal}</p><h3>{candidate.name}</h3></div><Tag status={candidate.status}/></div>
    {candidate.reason && <div className="notice notice-danger"><Icon name="info"/>The verifier rejected this schedule: {candidate.reason}</div>}
    {candidate.status === 'valid' && <>
      <div className="detail-metrics"><div><small>Training ratio</small><strong>{scoreLabel(candidate.average_ratio)}</strong></div>
        <div><small>Holdout ratio</small><strong>{scoreLabel(candidate.holdout_average_ratio)}</strong></div>
        <div><small>Worst training case</small><strong>{scoreLabel(candidate.worst_ratio)}</strong></div></div>
      <CaseChart values={candidate.train_case_ratios} name="Training" />
      <CaseChart values={candidate.holdout_case_ratios} name="Holdout" />
      {loads && <div className="schedule-preview"><div className="card-subheading"><h4>First workload</h4>
        <span>Finishes in {candidate.preview_makespan} time units</span></div>
        <WorkloadBars loads={loads}/><p className="muted-small">Job to machine assignments (starting from 0): {schedule?.join(', ')}</p></div>}
    </>}
  </div>;
}

function Playground() {
  const [input, setInput] = useState('9, 8, 7, 6, 5, 4, 3');
  const [machines, setMachines] = useState(3);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [solvedJobs, setSolvedJobs] = useState<number[]>([]);
  const [solvedMachines, setSolvedMachines] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const examples = [
    { name: 'Balanced jobs', value: '9, 8, 7, 6, 5, 4, 3' },
    { name: 'One big job', value: '40, 2, 3, 4, 5, 2, 7, 1' },
    { name: 'Mixed durations', value: '18, 6, 12, 5, 25, 9, 3, 14, 8, 7' },
  ];
  async function solve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parts = input.split(/[\s,]+/).filter(Boolean);
    const durations = parts.map(Number);
    if (durations.length < 2 || durations.length > 60 || durations.some(number => !Number.isSafeInteger(number) || number < 1 || number > 1_000_000)) {
      setError('Enter 2 to 60 positive whole numbers, separated by commas or spaces.'); return;
    }
    if (!Number.isInteger(machines) || machines < 2 || machines > 12) { setError('Choose between 2 and 12 machines.'); return; }
    setBusy(true); setResult(null); setError('');
    try { const solved = await api.solve({ durations, machines, candidate_limit: 100 }); setSolvedJobs(durations); setSolvedMachines(machines); setResult(solved); }
    catch (cause) { setError(errorText(cause)); }
    finally { setBusy(false); }
  }
  const difference = result ? ((1 - result.makespan / result.baseline_makespan) * 100) : null;
  const workloadPreview = useMemo(() => {
    const values = input.split(/[\s,]+/).filter(Boolean).map(Number);
    if (!values.length || values.some(value => !Number.isSafeInteger(value) || value < 1)) return null;
    return { count: values.length, total: values.reduce((sum, value) => sum + value, 0), biggest: Math.max(...values) };
  }, [input]);
  return <div className="page-content">
    <div className="page-intro"><p className="eyebrow">Try it yourself</p><h1>Scheduling playground</h1>
      <p>Enter a few jobs and see how OMEGA splits the work across machines. No experiment is saved.</p></div>
    <div className="split-grid">
      <section className="panel panel-pad"><SectionHeading title="Your workload" note="Each number is how long one job takes." />
        <form onSubmit={solve} className="input-form">
          <label className="form-field" htmlFor="durations">Job durations <span>2–60 whole numbers</span></label>
          <textarea id="durations" rows={5} value={input} required onChange={e => { setInput(e.target.value); setResult(null); }} spellCheck={false} />
          {workloadPreview && <div className="workload-preview" aria-live="polite"><span><strong>{workloadPreview.count}</strong> jobs</span><span><strong>{workloadPreview.total.toLocaleString()}</strong> total time</span><span><strong>{workloadPreview.biggest.toLocaleString()}</strong> longest job</span></div>}
          <div className="preset-area"><p>Try an example</p><div className="preset-list">{examples.map(example => <button
            key={example.name} type="button" className="preset-chip" aria-pressed={input === example.value} onClick={() => { setInput(example.value); setResult(null); setError(''); }}>{example.name}</button>)}</div></div>
          <label className="form-field" htmlFor="machine-count">Machines <span>2–12</span></label>
          <input id="machine-count" type="number" required min={2} max={12} value={machines} onChange={e => { setMachines(Number(e.target.value)); setResult(null); }} />
          <button className="btn btn-primary btn-full" type="submit" disabled={busy}><Icon name="play" size={16}/>{busy ? 'Finding a schedule…' : 'Find a schedule'}</button>
        </form>{error && <div className="notice notice-danger" role="alert">{error}</div>}
      </section>
      <section className="panel panel-pad"><SectionHeading title="The result" note="Your schedule, checked against the jobs you entered." />
        {!result ? <EmptyState title="Give it a try" text="Choose an example or enter your own jobs, then click Find a schedule." /> : <div className="result-stack">
          <div className="detail-metrics"><div><small>OMEGA makespan</small><strong>{result.makespan}</strong></div>
            <div><small>LPT makespan</small><strong>{result.baseline_makespan}</strong></div>
            <div><small>Difference</small><strong className="accent-text">{difference?.toFixed(1)}%</strong></div></div>
          <p className="result-recipe"><strong>Best strategy</strong><span>{result.winner_name}</span></p>
          <WorkloadBars loads={result.machine_loads}/>
          <ScheduleTimeline durations={solvedJobs} assignments={result.assignments} machines={solvedMachines} makespan={result.makespan}/>
          <p className="muted-small">{result.valid_count} valid recipes. {result.invalid_count} intentionally invalid test recipe rejected.</p>
          <details className="disclosure"><summary>See the exact assignment</summary><p>Machine numbers start at 0. Each value is the machine assigned to that job, in the same order as the input.</p><code>{result.assignments.join(', ')}</code></details>
        </div>}
      </section>
    </div>
    <section className="callout"><Icon name="info"/><div><strong>What is makespan?</strong>
      <p>Imagine every machine starts at the same time. Makespan is when the last machine finishes. A smaller makespan is better; it does not mean the scheduling program itself ran faster.</p></div></section>
  </div>;
}

function ExperimentForm({ draft, setDraft, start, submitting }: {
  draft: RunInput; setDraft: (value: RunInput) => void; start: (event: FormEvent<HTMLFormElement>) => void; submitting: boolean;
}) {
  const fields: { key: keyof RunInput; label: string; min: number; max: number; help: string }[] = [
    { key: 'seed', label: 'Random seed', min: 0, max: 2_147_483_647, help: 'Repeat the same random workloads' },
    { key: 'machines', label: 'Machines', min: 2, max: 12, help: 'Workers sharing the jobs' },
    { key: 'job_count', label: 'Jobs per case', min: 4, max: 60, help: 'Jobs in each workload' },
    { key: 'case_count', label: 'Training cases', min: 2, max: 12, help: 'Cases used to choose the winner' },
    { key: 'holdout_count', label: 'Holdout cases', min: 0, max: 12, help: 'Unseen cases used to check the winner' },
    { key: 'candidate_limit', label: 'Recipes to try', min: 2, max: 2000, help: 'Upper limit for the search' },
  ];
  return <section id="new-experiment" className="panel panel-pad"><SectionHeading title="New experiment" note="Start with a preset or adjust the settings." />
    <div className="preset-area"><p>Quick settings</p><div className="preset-list"><button className="preset-chip" type="button" aria-pressed={JSON.stringify(draft) === JSON.stringify(SMALL_INPUT)} onClick={() => setDraft({ ...SMALL_INPUT })}>Quick test</button>
      <button className="preset-chip" type="button" aria-pressed={JSON.stringify(draft) === JSON.stringify(DEFAULT_INPUT)} onClick={() => setDraft({ ...DEFAULT_INPUT })}>Standard</button>
      <button className="preset-chip" type="button" aria-pressed={JSON.stringify(draft) === JSON.stringify(DEEP_INPUT)} onClick={() => setDraft({ ...DEEP_INPUT })}>Deeper search</button></div></div>
    <form className="input-form" onSubmit={start}><div className="form-grid">{fields.map(field => <div key={field.key}><label className="form-field" htmlFor={`run-${field.key}`}>{field.label}
      <span>{field.help}</span></label><input id={`run-${field.key}`} required type="number" min={field.min} max={field.max}
        value={draft[field.key]} onChange={e => setDraft({ ...draft, [field.key]: Number(e.target.value) })}/></div>)}</div>
      <button type="submit" className="btn btn-primary btn-full" disabled={submitting}><Icon name="play" size={16}/>{submitting ? 'Adding to queue…' : 'Start search'}</button>
      <p className="muted-small form-footnote">Your search runs in the background. Results are saved automatically.</p></form>
  </section>;
}

export default function App() {
  const [view, setView] = useState<Page>('home');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [draft, setDraft] = useState<RunInput>({ ...DEFAULT_INPUT });
  const [runs, setRuns] = useState<Run[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [candidates, setCandidates] = useState<CandidatePage>(EMPTY_CANDIDATES);
  const [selectedOrdinal, setSelectedOrdinal] = useState<number | null>(null);
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('train');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [apiKeyText, setApiKeyText] = useState('');
  const [keyRevision, setKeyRevision] = useState(0);
  const [copied, setCopied] = useState(false);
  const [accessKeySaved, setAccessKeySaved] = useState(false);

  const active = useMemo(() => runs.find(run => run.id === activeId) ?? null, [activeId, runs]);
  const selected = useMemo(() => candidates.items.find(candidate => candidate.ordinal === selectedOrdinal)
    ?? candidates.items[0] ?? null, [candidates, selectedOrdinal]);
  const pending = jobs.filter(activeJob);

  // Honor the device appearance automatically. There is no decorative theme toggle.
  useEffect(() => {
    const preference = window.matchMedia('(prefers-color-scheme: dark)');
    const applyAppearance = () => {
      document.documentElement.dataset.theme = preference.matches ? 'dark' : 'light';
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', preference.matches ? '#0d1428' : '#f4f7ff');
    };
    applyAppearance();
    preference.addEventListener('change', applyAppearance);
    return () => preference.removeEventListener('change', applyAppearance);
  }, []);

  const reload = useCallback(async () => {
    try {
      const [loadedRuns, loadedJobs] = await Promise.all([api.listRuns(), api.listJobs()]);
      setRuns(loadedRuns); setJobs(loadedJobs);
      setActiveId(previous => previous && loadedRuns.some(run => run.id === previous) ? previous : loadedRuns[0]?.id ?? null);
      setError('');
    } catch (cause) { setError(errorText(cause)); }
    finally { setInitialLoading(false); }
  }, []);
  // Check active work frequently, but avoid unnecessary polling when the queue is idle.
  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => { if (!document.hidden) void reload(); }, pending.length > 0 ? 5000 : 15000);
    const refreshOnReturn = () => { if (!document.hidden) void reload(); };
    document.addEventListener('visibilitychange', refreshOnReturn);
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', refreshOnReturn); };
  }, [reload, pending.length > 0]);
  useEffect(() => {
    if (!activeId) { setManifest(null); return; }
    let cancelled = false;
    setManifest(null);
    api.manifest(activeId).then(value => { if (!cancelled) setManifest(value); })
      .catch(cause => { if (!cancelled) setError(errorText(cause)); });
    return () => { cancelled = true; };
  }, [activeId, keyRevision]);
  useEffect(() => {
    if (!activeId) { setCandidates(EMPTY_CANDIDATES); return; }
    let cancelled = false;
    setSelectedOrdinal(null);
    api.candidates(activeId, filter, query, offset, sort).then(value => { if (!cancelled) setCandidates(value); })
      .catch(cause => { if (!cancelled) setError(errorText(cause)); });
    return () => { cancelled = true; };
  }, [activeId, filter, query, offset, sort, keyRevision]);

  function navigate(next: Page) { setView(next); setMobileOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  function chooseRun(id: string) { setActiveId(id); setFilter('all'); setQuery(''); setSort('train'); setOffset(0); navigate('experiments'); }
  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSubmitting(true); setError('');
    try { await api.queue(draft); navigate('experiments'); await reload(); }
    catch (cause) { setError(errorText(cause)); }
    finally { setSubmitting(false); }
  }
  async function cancel(id: string) {
    try { await api.cancel(id); await reload(); } catch (cause) { setError(errorText(cause)); }
  }
  function downloadManifest() {
    if (!manifest || !active) return;
    const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `omega-${active.id}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function copyCommand() {
    if (!manifest) return;
    try { await navigator.clipboard.writeText(manifest.reproduce_command); setCopied(true); window.setTimeout(() => setCopied(false), 2500); }
    catch { setError('Copy was blocked. Select the command and copy it manually.'); }
  }
  function applyKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setApiKey(apiKeyText); setAccessKeySaved(Boolean(apiKeyText.trim()));
    setKeyRevision(previous => previous + 1); setError(''); void reload();
  }
  function clearKey() {
    setApiKey(''); setApiKeyText(''); setAccessKeySaved(false);
    setKeyRevision(previous => previous + 1); void reload();
  }
  function retryConnection() {
    setKeyRevision(previous => previous + 1);
    void reload();
  }
  const labels: Record<Page, string> = { home: 'Overview', experiments: 'Experiments', playground: 'Playground' };
  const navEntries: { id: Page; icon: IconName; label: string }[] = [
    { id: 'home', icon: 'home', label: 'Overview' }, { id: 'experiments', icon: 'layers', label: 'Experiments' },
    { id: 'playground', icon: 'sliders', label: 'Playground' },
  ];
  const navigation = <nav aria-label="Main navigation" className="nav-list">{navEntries.map(entry => <button
    type="button" key={entry.id} onClick={() => navigate(entry.id)} className={`nav-link${view === entry.id ? ' is-current' : ''}`}
    aria-current={view === entry.id ? 'page' : undefined}><Icon name={entry.icon}/><span>{entry.label}</span>
    {entry.id === 'experiments' && pending.length > 0 && <span className="nav-counter">{pending.length}</span>}</button>)}</nav>;

  return <div className="app-shell">
    <a className="skip-link" href="#content">Skip to main content</a>
    {mobileOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside className={`sidebar${mobileOpen ? ' sidebar-open' : ''}`}>
      <button className="brand" type="button" onClick={() => navigate('home')} aria-label="OMEGA home">
        <span className="brand-mark">O</span><span className="brand-word"><strong>OMEGA</strong><small>Scheduling lab</small></span>
      </button>
      <span className="nav-caption">WORKSPACE</span>{navigation}
      <div className="sidebar-footer">
        <section className="sidebar-guide" aria-label="Quick start">
          <div className="guide-heading"><span className="guide-icon"><Icon name="play" size={16}/></span>
            <span className="guide-kicker">NEW HERE?</span></div>
          <strong>See a schedule in action.</strong>
          <p>A sample workload is already filled in. Open the playground and try changing the machine count.</p>
          <button type="button" className="guide-button" onClick={() => navigate('playground')}>
            <span>Try the playground</span><Icon name="arrow" size={16}/>
          </button>
        </section>
        <details className="sidebar-access"><summary><Icon name="shield" size={16}/> API access
          <span className="access-state">{accessKeySaved ? 'Key added' : 'Optional'}</span></summary>
          <form onSubmit={applyKey}><label htmlFor="api-key-input">API key</label>
            <p>Only needed when your server requires a key. Kept in memory, not saved on your device.</p>
            <input id="api-key-input" type="password" autoComplete="off" value={apiKeyText} placeholder="Enter your API key"
              onChange={e => setApiKeyText(e.target.value)} />
            <div className="key-buttons"><button type="submit" className="btn btn-primary btn-small">Apply key</button>
              <button type="button" className="btn btn-small" onClick={clearKey}>Clear</button></div>
          </form></details>
      </div>
    </aside>
    <div className="main-column"><header className="topbar">
      <div className="topbar-left"><button className="icon-btn mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Icon name="menu"/></button>
        <span className="crumb">Workspace</span><Icon name="chevron" size={14}/><strong>{labels[view]}</strong></div>
      <div className="topbar-right">
        {pending.length > 0 && <button type="button" className="topbar-activity" onClick={() => navigate('experiments')}>
          <span className="activity-pulse" aria-hidden="true" />
          <span>{pending.length} {pending.length === 1 ? 'search active' : 'searches active'}</span>
        </button>}
        <a href="/docs" className="topbar-api" target="_blank" rel="noopener noreferrer"
          aria-label="Open API documentation in a new tab" title="Open the interactive API reference">
          <Icon name="external" size={17}/><span>API docs</span>
        </a>
      </div>
    </header>
      <main className="main-content" id="content">
        {error && <div className="notice notice-danger global-error" role="alert"><Icon name="info"/>
          <span>{error}</span><button type="button" className="error-retry" onClick={retryConnection}>Try again</button>
          <button type="button" aria-label="Dismiss message" onClick={() => setError('')}><Icon name="close" size={17}/></button></div>}
        {view === 'home' && <div className="page-content">
          <section className="welcome"><div className="welcome-copy"><div className="eyebrow"><span className="eyebrow-mark"/> SCHEDULING LAB / 01</div>
            <h1>Better schedules.<br/><em>Made easier to explore.</em></h1>
            <p>Put scheduling ideas to the test. Explore different strategies, compare the results, and see where every job ends up.</p>
            <div className="welcome-buttons"><button type="button" className="btn btn-primary" onClick={() => navigate('experiments')}>Start an experiment <Icon name="arrow" size={17}/></button>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('playground')}>Try an example</button></div>
            <div className="welcome-note"><Icon name="check" size={16}/>Every saved schedule is independently verified.</div></div>
            <div className="welcome-visual" aria-label="Illustration of four machine workloads; values are examples, not actual experiment results">
              <div className="visual-top"><span>EXAMPLE WORKLOAD</span><strong>Balanced schedule</strong></div>
              <div className="visual-lines">{[73, 84, 78, 80].map((value, index) => <div className="visual-machine" key={index}><span>M{index + 1}</span>
                <div className="visual-track"><span style={{ width: `${value}%` }}/></div><small>{value}%</small></div>)}</div>
              <div className="visual-bottom"><span className="visual-key"/>Example only · your results appear below</div>
            </div>
          </section>
          <SectionHeading eyebrow="CURRENT ACTIVITY" title="Your lab at a glance" note="A quick look at what you’ve tried so far." />
          <div className="metrics-grid"><StatCard label="Recent experiments" value={initialLoading ? "—" : runs.length.toLocaleString()} hint="Latest saved runs"/>
            <StatCard label="Verified strategies" value={initialLoading ? "—" : runs.reduce((sum, run) => sum + run.valid_count, 0).toLocaleString()} hint="From these recent runs"/>
            <StatCard label="Best training improvement" value={runs.length ? signedGain(Math.min(...runs.map(run => run.winner_ratio))) : '—'} hint="Compared with LPT" accent/>
            <StatCard label="Jobs in progress" value={initialLoading ? "—" : String(pending.length)} hint="Waiting or running"/></div>
          <div className="overview-columns"><section className="panel panel-pad"><SectionHeading title="Recent experiments" note="Pick a run to see the full results."
            action={<button type="button" className="text-link" onClick={() => navigate('experiments')}>View all <Icon name="arrow" size={15}/></button>} />
            {initialLoading ? <p className="subtle-placeholder" role="status">Loading recent experiments…</p> : runs.length === 0 ? <EmptyState title="Your first experiment starts here" text="Start a search and your results will appear here."
              action={<button className="btn btn-secondary" onClick={() => navigate('experiments')}>Create an experiment</button>} /> :
              <div className="recent-list">{runs.slice(0, 5).map(run => <button type="button" className="recent-row" key={run.id} onClick={() => chooseRun(run.id)}>
                <span className="recent-number">{String(run.seed).padStart(2, '0').slice(-2)}</span><span className="recent-content"><strong>{run.machines} machines · {run.job_count} jobs</strong>
                  <small>{humanDate(run.created_at)} · {run.candidate_limit} recipes</small></span><span className="recent-gain">{signedGain(run.winner_ratio)}</span><Icon name="chevron" size={16}/></button>)}</div>}
          </section>
          <section className="panel panel-pad how-panel"><SectionHeading title="How it works" note="The short version." />
            <ol className="how-list"><li><span>1</span><div><strong>Try different methods</strong><p>Combine ways of ordering jobs, assigning machines, and improving schedules.</p></div></li>
              <li><span>2</span><div><strong>Check every schedule</strong><p>Python verifies the assignments independently from the Rust search engine.</p></div></li>
              <li><span>3</span><div><strong>Compare fairly</strong><p>Choose a winner on training cases, then test it on workloads it hasn't seen.</p></div></li></ol>
            <div className="how-footer"><Icon name="info" size={18}/><span>OMEGA searches known heuristic combinations. It doesn't invent arbitrary new algorithms or guarantee an optimal answer.</span></div>
          </section></div>
        </div>}
        {view === 'playground' && <Playground/>}
        {view === 'experiments' && <div className="page-content">
          <div className="page-intro"><p className="eyebrow">Test new ideas</p><h1>Experiments</h1>
            <p>Set up a scheduling search, watch it run, and look closely at the results.</p></div>
          <div className="experiment-top-grid"><ExperimentForm draft={draft} setDraft={setDraft} start={start} submitting={submitting}/>
            <div className="experiment-side"><section className="panel panel-pad"><SectionHeading title="Search queue" note="Active searches update every five seconds." />
              {initialLoading ? <p className="subtle-placeholder" role="status">Loading the search queue…</p> : jobs.length === 0 ? <EmptyState title="Ready when you are" text="Start an experiment and watch its progress here." /> :
                <div className="job-list">{jobs.slice(0, 6).map(job => <div key={job.id} className="job-item"><div className="job-head">
                  <div><strong>Search {job.id.slice(0, 8)}</strong><small>{job.parameters.candidate_limit} recipes · {humanDate(job.created_at)}</small></div>
                  <Tag status={job.status}/></div><div className="progress-bar" role="progressbar" aria-label={`Search ${job.id.slice(0, 8)} progress`}
                    aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress}><span style={{ width: `${job.progress}%` }} /></div>
                  <div className="job-actions"><small>{job.status === 'running' ? `${job.progress}% complete` : job.error || statusLabel(job.status)}</small>
                    {activeJob(job) && !job.cancel_requested && <button type="button" className="text-link text-danger" onClick={() => void cancel(job.id)}>Cancel</button>}
                    {job.cancel_requested && <small>Cancellation requested</small>}
                    {job.run_id && <button type="button" className="text-link" onClick={() => chooseRun(job.run_id!)}>View results <Icon name="arrow" size={14}/></button>}</div>
                </div>)}</div>}
              </section>
              <section className="panel panel-pad"><SectionHeading title="Saved runs" note="The 10 most recent experiments." />
                {runs.length === 0 ? <p className="subtle-placeholder">Saved experiments will show up here.</p> : <div className="saved-runs">{runs.map(run => <button type="button" key={run.id}
                  className={`saved-run${run.id === activeId ? ' saved-selected' : ''}`} onClick={() => chooseRun(run.id)}>
                  <span><strong>Seed {run.seed} · {run.candidate_limit} recipes</strong><small>{run.machines} machines · {humanDate(run.created_at)}</small></span>
                  <strong className="saved-gain">{signedGain(run.winner_ratio)}</strong></button>)}</div>}
              </section>
            </div>
          </div>
          {active && <section className="results-area" aria-label="Selected experiment results"><SectionHeading eyebrow="Selected run"
            title={`Experiment ${active.id.slice(0, 8)}`} note={`${active.machines} machines · ${active.job_count} jobs · ${active.case_count} training cases · ${active.holdout_count} holdout cases`}
            action={<button type="button" className="btn btn-secondary" disabled={!manifest} onClick={downloadManifest}><Icon name="download" size={16}/> Download data</button>}/>
            <div className="metrics-grid metrics-three"><StatCard label="Strategies tested" value={String(active.valid_count + active.invalid_count)} hint={`${active.invalid_count} rejected (including a test case)`}/>
              <StatCard label="Training gain" value={signedGain(active.winner_ratio)} hint="Used to select the winner" accent/>
              <StatCard label="Holdout gain" value={signedGain(active.winner_holdout_ratio)} hint="New workloads, not used in selection"/></div>
            <section className="panel panel-pad candidates-panel"><SectionHeading title="Candidate results" note="Select a recipe to see the scores and machine loads."
              action={<span className="count-label">{candidates.total} matching</span>}/>
              <div className="filter-bar"><label className="search-field"><Icon name="search" size={17}/><input type="search" value={query}
                aria-label="Search recipe names" placeholder="Search recipes…" maxLength={80} onChange={e => { setQuery(e.target.value); setOffset(0); }}/></label>
                <label className="select-wrap"><span>Status</span><select aria-label="Filter by status" value={filter} onChange={e => { setFilter(e.target.value); setOffset(0); }}>
                  <option value="all">All</option><option value="valid">Valid</option><option value="invalid">Rejected</option></select></label>
                <label className="select-wrap"><span>Sort</span><select aria-label="Sort candidate results" value={sort} onChange={e => { setSort(e.target.value); setOffset(0); }}>
                  <option value="train">Training score</option><option value="holdout">Holdout score</option></select></label></div>
              <div className="table-outer"><table className="results-table"><thead><tr><th scope="col">Recipe</th><th scope="col">Status</th><th scope="col">Training</th><th scope="col">Holdout</th></tr></thead>
                <tbody>{candidates.items.map(candidate => <tr key={candidate.ordinal} className={selected?.ordinal === candidate.ordinal ? 'row-selected' : ''}>
                  <td><button type="button" className="recipe-select" onClick={() => setSelectedOrdinal(candidate.ordinal)}
                    aria-pressed={selected?.ordinal === candidate.ordinal}><span className="recipe-ordinal">#{candidate.ordinal}</span>{candidate.name}</button></td>
                  <td><Tag status={candidate.status}/></td><td className="numeric-cell">{scoreLabel(candidate.average_ratio)}</td>
                  <td className="numeric-cell">{scoreLabel(candidate.holdout_average_ratio)}</td></tr>)}
                  {candidates.items.length === 0 && <tr><td colSpan={4}><p className="subtle-placeholder">No recipes match your filters. Try a different name or status.</p></td></tr>}</tbody></table></div>
              <div className="pagination"><span>{candidates.total === 0 ? 'No results' : `${offset + 1}–${offset + candidates.items.length} of ${candidates.total}`}</span>
                <div><button type="button" className="btn btn-small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</button>
                  <button type="button" className="btn btn-small" disabled={offset + 25 >= candidates.total} onClick={() => setOffset(offset + 25)}>Next</button></div></div>
            </section>
            {selected && <section className="panel panel-pad"><SectionHeading title="Strategy details" note="Why it was accepted and how it performed."/>
              <CandidateInspector candidate={selected} manifest={manifest} machineCount={active.machines}/></section>}
            <section className="panel panel-pad"><SectionHeading title="Run it again" note="A fixed seed and the same code reproduce the same workload and scores." />
              <div className="command-wrapper"><code>{manifest?.reproduce_command ?? 'Loading command…'}</code><button type="button" disabled={!manifest}
                className="btn btn-small" onClick={() => void copyCommand()}><Icon name={copied ? 'check' : 'copy'} size={15}/>{copied ? 'Copied' : 'Copy'}</button></div>
              {manifest && <p className="hash-text">Workload fingerprint: <code>{manifest.workload_digest}</code></p>}</section>
            <p className="results-disclaimer"><Icon name="info" size={16}/> A ratio below 1.000 means a shorter average schedule than LPT on these workloads. It does not measure algorithm runtime.</p>
          </section>}
        </div>}
      </main>
      <footer className="site-footer"><span>OMEGA · Experiment. Compare. Improve.</span><span>Python + Rust + React + PostgreSQL</span></footer>
    </div>
    <nav className="mobile-tabs" aria-label="Mobile navigation">{navEntries.map(entry => <button type="button" key={entry.id}
      className={view === entry.id ? 'tab-selected' : ''} aria-current={view === entry.id ? 'page' : undefined}
      onClick={() => navigate(entry.id)}><Icon name={entry.icon} size={20}/><span>{entry.label}</span></button>)}</nav>
  </div>;
}
