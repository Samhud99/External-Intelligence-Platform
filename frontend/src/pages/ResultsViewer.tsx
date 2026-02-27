import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { RunResult } from '../api/types';

export default function ResultsViewer() {
  const { id, runId } = useParams<{ id: string; runId: string }>();
  const [result, setResult] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !runId) return;
    const fetchResult = async () => {
      try {
        const data = await api.getResult(id, runId);
        setResult(data);
      } catch {
        setError('Failed to load results');
      } finally {
        setLoading(false);
      }
    };
    fetchResult();
  }, [id, runId]);

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading...</div>;
  }

  if (error || !result) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">{error || 'Result not found'}</p>
        <Link to={`/jobs/${id}`} className="text-blue-600 hover:text-blue-700">
          Back to job
        </Link>
      </div>
    );
  }

  const columns = result.items.length > 0 ? Object.keys(result.items[0]) : [];

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <Link to={`/jobs/${id}`} className="text-sm text-blue-600 hover:text-blue-700 mb-2 inline-block">
            &larr; Back to job
          </Link>
          <h2 className="text-2xl font-bold text-gray-900">Run Results</h2>
        </div>
      </div>

      {/* Run Metadata */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Run ID</dt>
            <dd className="text-gray-900 font-mono text-xs">{result.run_id}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Ran At</dt>
            <dd className="text-gray-900">{new Date(result.ran_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Total Items</dt>
            <dd className="text-gray-900 font-medium">{result.items_total}</dd>
          </div>
          <div>
            <dt className="text-gray-500">New Items</dt>
            <dd className="text-green-600 font-medium">{result.items_new}</dd>
          </div>
        </dl>
      </div>

      {/* Items Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">
            Items ({result.items.length})
          </h3>
        </div>

        {result.items.length === 0 ? (
          <div className="p-6 text-gray-500 text-sm">No items extracted in this run.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col}
                      className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {result.items.map((item, i) => (
                  <tr key={i} className={item.is_new ? 'bg-green-50' : ''}>
                    {columns.map((col) => (
                      <td key={col} className="px-4 py-2 text-sm text-gray-700 max-w-xs truncate">
                        {col === 'is_new' ? (
                          item.is_new ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                              NEW
                            </span>
                          ) : null
                        ) : (
                          String(item[col] ?? '')
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
