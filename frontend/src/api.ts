export type RunInput = {
  seed: number; machines: number; job_count: number; case_count: number;
  holdout_count: number; candidate_limit: number;
};

export type Run = RunInput & {
  id: string; created_at: string; workload_digest: string; holdout_digest: string | null;
  winner_ordinal: number; winner_ratio: number; winner_holdout_ratio: number | null;
  valid_count: number; invalid_count: number;
};
export type Job = {
  id: string; created_at: string; started_at: string | null; finished_at: string | null;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  progress: number; parameters: RunInput; cancel_requested: boolean;
  error: string | null; run_id: string | null;
};
export type Candidate = {
  ordinal: number; name: string; ordering: string; order_parameter: number;
  placement: string; placement_seed: number; passes: number;
  status: 'valid' | 'invalid'; reason: string | null;
  average_ratio: number | null; worst_ratio: number | null; mean_makespan: number | null;
  preview_assignments: number[] | null; preview_makespan: number | null;
  train_case_ratios: number[] | null; holdout_case_ratios: number[] | null;
  holdout_average_ratio: number | null; holdout_worst_ratio: number | null;
};
export type CandidatePage = { total: number; items: Candidate[] };
export type Manifest = {
  format_version: string; parameters: RunInput; workload_digest: string;
  workloads: number[][]; holdout_digest: string | null; holdout_workloads: number[][];
  winner: { ordinal: number; name: string; average_ratio: number; holdout_average_ratio: number | null };
  reproduce_command: string; note: string;
};
export type SolveInput = { durations: number[]; machines: number; candidate_limit: number };
export type SolveResult = {
  winner_ordinal: number; winner_name: string; assignments: number[];
  machine_loads: number[]; makespan: number; baseline_makespan: number;
  lower_bound: number; valid_count: number; invalid_count: number;
};

let key = '';
export function setApiKey(value: string) { key = value.trim(); }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (key) headers.set('X-OMEGA-Key', key);
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = response.status === 401 ? 'Access denied. Enter the OMEGA API key.' : `HTTP ${response.status}`;
    try {
      const body: { detail?: string | { msg: string }[] } = await response.json();
      if (response.status !== 401 && typeof body.detail === 'string') message = body.detail;
      if (Array.isArray(body.detail)) message = body.detail.map((item) => item.msg).join('; ');
    } catch { /* Non-JSON responses still have an HTTP status. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

const post = <T,>(path: string, input?: unknown) => request<T>(path, {
  method: 'POST', headers: input === undefined ? undefined : { 'Content-Type': 'application/json' },
  body: input === undefined ? undefined : JSON.stringify(input),
});

export const api = {
  listRuns: () => request<Run[]>('/api/runs'),
  run: (id: string) => request<Run>(`/api/runs/${encodeURIComponent(id)}`),
  listJobs: () => request<Job[]>('/api/jobs'),
  queue: (data: RunInput) => post<Job>('/api/jobs', data),
  cancel: (id: string) => post<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`),
  solve: (data: SolveInput) => post<SolveResult>('/api/solve', data),
  manifest: (id: string) => request<Manifest>(`/api/runs/${encodeURIComponent(id)}/manifest`),
  candidates: (id: string, status: string, query: string, offset: number, sort: string) => {
    const params = new URLSearchParams({ status, query, offset: String(offset), limit: '25', sort });
    return request<CandidatePage>(`/api/runs/${encodeURIComponent(id)}/candidates?${params}`);
  },
};
