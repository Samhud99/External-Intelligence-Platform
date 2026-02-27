import type { AgentEvent, NextStep } from '../api/types';
import { useState } from 'react';

interface FailureCardProps {
  event: AgentEvent;
  onAction: (step: NextStep) => void;
}

export default function FailureCard({ event, onAction }: FailureCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
          <span className="text-red-600 text-sm font-bold">!</span>
        </div>
        <div className="flex-1">
          <p className="text-red-800 font-medium">{event.user_message || event.message}</p>

          {event.next_steps && event.next_steps.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {event.next_steps.map((step, i) => (
                <button
                  key={i}
                  onClick={() => onAction(step)}
                  className="px-3 py-1.5 bg-white border border-red-200 rounded-lg text-sm text-red-700 hover:bg-red-100 font-medium"
                >
                  {step.label}
                </button>
              ))}
            </div>
          )}

          {event.technical_details && (
            <div className="mt-3">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="text-xs text-red-600 hover:text-red-700 underline"
              >
                {showDetails ? 'Hide technical details' : 'Show technical details'}
              </button>
              {showDetails && (
                <pre className="mt-2 p-3 bg-white rounded border text-xs text-gray-700 overflow-x-auto">
                  {JSON.stringify(event.technical_details, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
