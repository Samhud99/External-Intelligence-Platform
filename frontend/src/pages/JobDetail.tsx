import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Job, ExtractionConfig, RunResult } from '../api/types';
import StatusBadge from '../components/StatusBadge';

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [config, setConfig] = useState<ExtractionConfig | null>(null);
  const [results, setResults] = useState<RunResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const fetchData = async () => {
      try {
        const [jobData, resultsData] = await Promise.all([
          api.getJob(id),
          api.listResults(id),
        ]);
        setJob(jobData.job);
        setConfig(jobData.config);
        setResults(resultsData);
      } catch {
        setError('Failed to load job details');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleRunNow = async () => {
    if (!id) return;
    try {
      await api.triggerRun(id);
      const resultsData = await api.listResults(id);
      setResults(resultsData);
    } catch {
      setError('Failed to trigger run');
    }
  };

  const handleTogglePause = async () => {
    if (!id || !job) return;
    const newStatus = job.status === 'paused' ? 'active' : 'paused';
    try {
      const updated = await api.patchJob(id, { status: newStatus });
      setJob(updated);
    } catch {
      setError('Failed to update job');
    }
  };

  const handleDelete = async () => {
    if (!id) return;
    try {
      await api.deleteJob(id);
      navigate('/');
    } catch {
      setError('Failed to delete job');
    }
  };

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading...</div>;
  }

  if (!job) {
    return <div className="text-center py-12 text-red-500">Job not found</div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-start mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{job.name}</h2>
          <p className="text-sm text-gray-500 mt-1">{job.target_url}</p>
        </div>
        <StatusBadge status={job.status} />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* Job Metadata */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Job Details</h3>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Schedule</dt>
            <dd className="text-gray-900 font-medium">{job.schedule || 'None'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Created</dt>
            <dd className="text-gray-900 font-medium">{new Date(job.created_at).toLocaleString()}</dd>
          </div>
          {config && (
            <>
              <div>
                <dt className="text-gray-500">Strategy</dt>
                <dd className="text-gray-900 font-medium">{config.strategy}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Selectors</dt>
                <dd className="text-gray-900 font-mono text-xs">
                  {Object.entries(config.selectors).map(([k, v]) => (
                    <div key={k}>{k}: {v}</div>
                  ))}
                </dd>
              </div>
            </>
          )}
        </dl>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mb-8">
        <button
          onClick={handleTogglePause}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200"
        >
          {job.status === 'paused' ? 'Resume' : 'Pause'}
        </button>
        <button
          onClick={handleRunNow}
          className="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200"
        >
          Run Now
        </button>
        <button
          onClick={handleDelete}
          className="px-4 py-2 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200"
        >
          Delete Job
        </button>
      </div>

      {/* Run History */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Run History</h3>
        {results.length === 0 ? (
          <p className="text-gray-500 text-sm">No runs yet.</p>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Items Found</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">New Items</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {results.map((run) => (
                <tr key={run.run_id}>
                  <td className="px-4 py-2 text-sm text-gray-700">
                    {new Date(run.ran_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-700">{run.items_total}</td>
                  <td className="px-4 py-2 text-sm text-gray-700">{run.items_new}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={run.success ? 'completed' : 'error'} />
                  </td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/jobs/${id}/results/${run.run_id}`}
                      className="text-blue-600 hover:text-blue-700 text-sm"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
