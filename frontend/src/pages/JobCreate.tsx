import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { connectSSE } from '../api/sse';
import type { AgentEvent, NextStep } from '../api/types';
import AgentFeed from '../components/AgentFeed';
import ExtractionPreview from '../components/ExtractionPreview';
import ChatInput from '../components/ChatInput';

type Phase = 'input' | 'running' | 'proposal' | 'done';

export default function JobCreate() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [phase, setPhase] = useState<Phase>('input');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [proposal, setProposal] = useState<AgentEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!prompt.trim()) return;
    setPhase('running');
    setEvents([]);
    setError(null);

    try {
      const { session_id } = await api.createSession(prompt);
      setSessionId(session_id);

      connectSSE(
        session_id,
        (event) => {
          setEvents((prev) => [...prev, event]);

          if (event.type === 'proposal') {
            setProposal(event);
            setPhase('proposal');
          } else if (event.type === 'done') {
            setPhase('done');
          } else if (event.type === 'error') {
            setError(event.message || 'An error occurred');
            setPhase('input');
          } else if (event.type === 'failure') {
            // Failure stays visible in feed — don't change phase
          }
        },
        () => {
          setError('Connection lost');
        },
      );
    } catch {
      setError('Failed to start session');
      setPhase('input');
    }
  }, [prompt]);

  const handleConfirm = useCallback(async () => {
    if (!sessionId) return;
    try {
      await api.confirmSession(sessionId);
    } catch {
      setError('Failed to confirm');
    }
  }, [sessionId]);

  const handleReject = useCallback(async () => {
    if (!sessionId) return;
    try {
      await api.rejectSession(sessionId);
      setPhase('input');
      setSessionId(null);
      setEvents([]);
      setProposal(null);
    } catch {
      setError('Failed to reject');
    }
  }, [sessionId]);

  const handleRefine = useCallback(
    async (message: string) => {
      if (!sessionId) return;
      try {
        await api.sendMessage(sessionId, message);
        setPhase('running');
        setProposal(null);
      } catch {
        setError('Failed to send message');
      }
    },
    [sessionId],
  );

  const handleEscalationApprove = useCallback(
    async (tier: string) => {
      if (!sessionId) return;
      try {
        await api.sendMessage(sessionId, `Approved. Please try using ${tier} to extract the data.`);
        setPhase('running');
      } catch {
        setError('Failed to approve escalation');
      }
    },
    [sessionId],
  );

  const handleEscalationReject = useCallback(async () => {
    if (!sessionId) return;
    try {
      await api.rejectSession(sessionId);
      setPhase('input');
      setSessionId(null);
      setEvents([]);
      setProposal(null);
    } catch {
      setError('Failed to reject');
    }
  }, [sessionId]);

  const handleFailureAction = useCallback(
    async (step: NextStep) => {
      if (!sessionId) return;
      if (step.type === 'retry') {
        handleSubmit();
      } else if (step.type === 'change_url') {
        setPhase('input');
        setEvents([]);
      } else if (step.type === 'escalate') {
        await api.sendMessage(sessionId, 'Please try the next extraction tier.');
        setPhase('running');
      } else {
        await api.sendMessage(sessionId, `User action: ${step.label}`);
        setPhase('running');
      }
    },
    [sessionId, handleSubmit],
  );

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Create Monitoring Job</h2>

      {/* Input phase */}
      {phase === 'input' && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What do you want to monitor?
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="e.g., Monitor the RACV blog for new articles about road safety..."
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={!prompt.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Discovery
          </button>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Agent activity feed */}
      {events.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium text-gray-500 mb-3">Agent Activity</h3>
          <AgentFeed
            events={events}
            onEscalationApprove={handleEscalationApprove}
            onEscalationReject={handleEscalationReject}
            onFailureAction={handleFailureAction}
          />
        </div>
      )}

      {/* Proposal phase */}
      {phase === 'proposal' && proposal && (
        <div className="mt-6 space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-lg font-semibold text-blue-900 mb-2">Proposed Configuration</h3>
            {proposal.message && (
              <p className="text-sm text-blue-800 mb-4">{proposal.message}</p>
            )}

            {proposal.sample_data && proposal.sample_data.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-blue-800 mb-2">Sample Data</h4>
                <ExtractionPreview
                  sampleData={proposal.sample_data}
                  selectors={proposal.config?.selectors as Record<string, string> | undefined}
                />
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleConfirm}
                className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
              >
                Confirm & Create Job
              </button>
              <button
                onClick={handleReject}
                className="px-4 py-2 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200"
              >
                Reject
              </button>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-500 mb-2">Or refine the configuration:</h4>
            <ChatInput onSend={handleRefine} placeholder="e.g., Only include articles from 2026..." />
          </div>
        </div>
      )}

      {/* Done phase */}
      {phase === 'done' && (
        <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <p className="text-green-800 font-medium mb-4">Job created successfully!</p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
          >
            Go to Dashboard
          </button>
        </div>
      )}
    </div>
  );
}
