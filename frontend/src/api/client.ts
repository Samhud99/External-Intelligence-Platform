import type {
  Job,
  JobDetail,
  RunResult,
  CreateSessionResponse,
} from './types';

const BASE = '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  listJobs: () => request<Job[]>('/jobs'),

  getJob: (id: string) => request<JobDetail>(`/jobs/${id}`),

  createSession: (prompt: string) =>
    request<CreateSessionResponse>('/jobs/create', {
      method: 'POST',
      body: JSON.stringify({ request: prompt }),
    }),

  sendMessage: (sessionId: string, content: string) =>
    request<{ status: string }>(`/jobs/create/${sessionId}/message`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

  confirmSession: (sessionId: string) =>
    request<{ status: string }>(`/jobs/create/${sessionId}/confirm`, {
      method: 'POST',
    }),

  rejectSession: (sessionId: string) =>
    request<{ status: string }>(`/jobs/create/${sessionId}/reject`, {
      method: 'POST',
    }),

  triggerRun: (jobId: string) =>
    request<Record<string, unknown>>(`/jobs/${jobId}/run`, {
      method: 'POST',
    }),

  patchJob: (jobId: string, patch: { status?: string; schedule?: string }) =>
    request<Job>(`/jobs/${jobId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  deleteJob: (jobId: string) =>
    request<{ deleted: string }>(`/jobs/${jobId}`, {
      method: 'DELETE',
    }),

  listResults: (jobId: string) =>
    request<RunResult[]>(`/jobs/${jobId}/results`),

  getResult: (jobId: string, runId: string) =>
    request<RunResult>(`/jobs/${jobId}/results/${runId}`),
};
