import type { AgentEvent } from '../api/types';

interface AgentFeedProps {
  events: AgentEvent[];
}

export default function AgentFeed({ events }: AgentFeedProps) {
  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {events.map((event, i) => (
        <FeedItem key={i} event={event} />
      ))}
    </div>
  );
}

function FeedItem({ event }: { event: AgentEvent }) {
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
