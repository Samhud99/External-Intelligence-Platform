import type { AgentEvent } from './types';

export type SSECallback = (event: AgentEvent) => void;

export function connectSSE(
  sessionId: string,
  onEvent: SSECallback,
  onError?: (error: Event) => void,
  onDone?: () => void,
): () => void {
  const url = `/jobs/create/${sessionId}/stream`;
  const eventSource = new EventSource(url);

  const eventTypes = [
    'status',
    'page_fetched',
    'thinking',
    'extraction_test',
    'proposal',
    'done',
    'error',
    'escalation_proposal',
    'failure',
  ];

  for (const type of eventTypes) {
    eventSource.addEventListener(type, (e: MessageEvent) => {
      try {
        const data: AgentEvent = JSON.parse(e.data);
        onEvent(data);

        if (type === 'done' || type === 'error' || type === 'failure') {
          eventSource.close();
          onDone?.();
        }
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    });
  }

  eventSource.onerror = (e) => {
    onError?.(e);
    eventSource.close();
    onDone?.();
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
}
