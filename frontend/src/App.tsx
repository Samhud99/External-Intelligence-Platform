import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import JobCreate from './pages/JobCreate';
import JobDetail from './pages/JobDetail';
import ResultsViewer from './pages/ResultsViewer';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/jobs/new" element={<JobCreate />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/jobs/:id/results/:runId" element={<ResultsViewer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
