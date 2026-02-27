import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Job } from '../api/types';
import JobCard from '../components/JobCard';

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      const data = await api.listJobs();
      setJobs(data);
      setError(null);
    } catch (err) {
      setError('Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleRunNow = async (id: string) => {
    try {
      await api.triggerRun(id);
      fetchJobs();
    } catch {
      setError('Failed to trigger run');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteJob(id);
      setJobs(jobs.filter((j) => j.id !== id));
    } catch {
      setError('Failed to delete job');
    }
  };

  const handleTogglePause = async (id: string, currentStatus: string) => {
    const newStatus = currentStatus === 'paused' ? 'active' : 'paused';
    try {
      await api.patchJob(id, { status: newStatus });
      fetchJobs();
    } catch {
      setError('Failed to update job');
    }
  };

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading jobs...</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Monitoring Jobs</h2>
        <Link
          to="/jobs/new"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          New Monitoring Job
        </Link>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No monitoring jobs yet.</p>
          <Link
            to="/jobs/new"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Create your first job
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onRunNow={handleRunNow}
              onDelete={handleDelete}
              onTogglePause={handleTogglePause}
            />
          ))}
        </div>
      )}
    </div>
  );
}
