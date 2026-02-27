interface ExtractionPreviewProps {
  sampleData: Record<string, unknown>[];
  selectors?: Record<string, string>;
}

export default function ExtractionPreview({ sampleData, selectors }: ExtractionPreviewProps) {
  if (sampleData.length === 0) return null;

  const columns = Object.keys(sampleData[0]);

  return (
    <div className="border rounded-lg overflow-hidden">
      {selectors && (
        <div className="bg-gray-50 p-3 border-b">
          <p className="text-xs font-medium text-gray-500 mb-1">Extraction Selectors</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(selectors).map(([key, value]) => (
              <span key={key} className="text-xs bg-white px-2 py-1 rounded border">
                <span className="font-medium">{key}:</span> {value}
              </span>
            ))}
          </div>
        </div>
      )}
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
          <tbody className="bg-white divide-y divide-gray-200">
            {sampleData.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col} className="px-4 py-2 text-sm text-gray-700 max-w-xs truncate">
                    {String(row[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
