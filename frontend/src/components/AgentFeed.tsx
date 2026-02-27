import { useState } from 'react';
import type { AgentEvent, NextStep } from '../api/types';

interface AgentFeedProps {
  events: AgentEvent[];
  onEscalationApprove?: (tier: string) => void;
  onEscalationReject?: () => void;
  onFailureAction?: (step: NextStep) => void;
}

export default function AgentFeed({ events, onEscalationApprove, onEscalationReject, onFailureAction }: AgentFeedProps) {
  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {events.map((event, i) => (
        <FeedItem
          key={i}
          event={event}
          onEscalationApprove={onEscalationApprove}
          onEscalationReject={onEscalationReject}
          onFailureAction={onFailureAction}
        />
      ))}
    </div>
  );
}

function FeedItem({
  event,
  onEscalationApprove,
  onEscalationReject,
  onFailureAction,
}: {
  event: AgentEvent;
  onEscalationApprove?: (tier: string) => void;
  onEscalationReject?: () => void;
  onFailureAction?: (step: NextStep) => void;
}) {
  const [showDetails, setShowDetails] = useState(false);

  switch (event.type) {
    case 'status':
      return (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
          {event.message}
        </div>
      );
    case 'page_fetched':
      return (
        <div className="text-sm text-green-700 bg-green-50 p-2 rounded">
          Fetched: {event.url} ({event.content_length?.toLocaleString()} chars)
        </div>
      );
    case 'thinking':
      return (
        <div className="text-sm text-purple-700 bg-purple-50 p-2 rounded italic">
          {event.message}
        </div>
      );
    case 'extraction_test':
      return (
        <div className="text-sm bg-yellow-50 p-2 rounded">
          <span className="font-medium text-yellow-800">
            Extraction test: {event.count} items found
          </span>
        </div>
      );
    case 'escalation_proposal':
      return (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <p className="text-sm text-amber-800 font-medium mb-2">
            {event.message}
          </p>
          <p className="text-xs text-amber-600 mb-3">
            Current: {event.current_tier} → Proposed: {event.proposed_tier}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => onEscalationApprove?.(event.proposed_tier || 'playwright')}
              className="px-3 py-1.5 bg-amber-600 text-white rounded text-sm font-medium hover:bg-amber-700"
            >
              Approve {event.proposed_tier}
            </button>
            <button
              onClick={() => onEscalationReject?.()}
              className="px-3 py-1.5 bg-white border border-amber-300 text-amber-700 rounded text-sm hover:bg-amber-50"
            >
              Skip
            </button>
          </div>
        </div>
      );
    case 'failure':
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 font-medium">{event.user_message || event.message}</p>
          {event.next_steps && event.next_steps.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {event.next_steps.map((step, i) => (
                <button
                  key={i}
                  onClick={() => onFailureAction?.(step)}
                  className="px-3 py-1.5 bg-white border border-red-200 rounded text-sm text-red-700 hover:bg-red-100"
                >
                  {step.label}
                </button>
              ))}
            </div>
          )}
          {event.technical_details && (
            <div className="mt-2">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="text-xs text-red-600 underline"
              >
                {showDetails ? 'Hide details' : 'Technical details'}
              </button>
              {showDetails && (
                <pre className="mt-1 p-2 bg-white rounded border text-xs overflow-x-auto">
                  {JSON.stringify(event.technical_details, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      );
    case 'error':
      return (
        <div className="text-sm text-red-700 bg-red-50 p-2 rounded">
          Error: {event.message}
        </div>
      );
    default:
      return null;
  }
}
