import { Route, Routes } from 'react-router-dom';

import HomePage from '@/pages/HomePage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      {/* Phase 6 : /login, /patients, /analyses, /dashboard */}
      <Route
        path="*"
        element={
          <main className="mx-auto max-w-3xl px-6 py-16">
            <h1 className="text-2xl font-bold text-slate-800">Page introuvable</h1>
          </main>
        }
      />
    </Routes>
  );
}
