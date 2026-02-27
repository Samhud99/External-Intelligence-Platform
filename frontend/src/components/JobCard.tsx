import { Link } from 'react-router-dom';
import type { Job } from '../api/types';
import StatusBadge from './StatusBadge';

interface JobCardProps {
  job: Job;
  onRunNow: (id: string) => void;
  onDelete: (id: string) => void;
  onTogglePause: (id: string, currentStatus: string) => void;
}

export default function JobCard({ job, onRunNow, onDelete, onTogglePause }: JobCardProps) {
  return (
    <div className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-4">
        <Link to={`/jobs/${job.id}`} className="text-lg font-semibold text-gray-900 hover:text-blue-600">
          {job.name}
        </Link>
        <StatusBadge status={job.status} />
      </div>

      <p className="text-sm text-gray-500 mb-2 truncate">{job.target_url}</p>
      <p className="text-sm text-gray-400 mb-4">Schedule: {job.schedule || 'None'}</p>

      <div className="flex gap-2">
        <button
          onClick={() => onTogglePause(job.id, job.status)}
          className="text-xs px-3 py-1 rounded bg-gray-100 text-gray-700 hover:bg-gray-200"
        >
          {job.status === 'paused' ? 'Resume' : 'Pause'}
        </button>
        <button
          onClick={() => onRunNow(job.id)}
          className="text-xs px-3 py-1 rounded bg-blue-100 text-blue-700 hover:bg-blue-200"
        >
          Run Now
        </button>
        <button
          onClick={() => onDelete(job.id)}
          className="text-xs px-3 py-1 rounded bg-red-100 text-red-700 hover:bg-red-200"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
