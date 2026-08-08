import { Link, Route, Routes } from 'react-router-dom';

import AppLayout from '@/components/AppLayout';
import ProtectedRoute from '@/components/ProtectedRoute';
import ForgotPasswordPage from '@/pages/ForgotPasswordPage';
import HomePage from '@/pages/HomePage';
import LoginPage from '@/pages/LoginPage';
import PatientDetailPage from '@/pages/PatientDetailPage';
import PatientFormPage from '@/pages/PatientFormPage';
import PatientsPage from '@/pages/PatientsPage';
import ResetPasswordPage from '@/pages/ResetPasswordPage';
import { CLINICAL_ROLES } from '@/types';

function NotFoundPage() {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold text-slate-800">Page introuvable</h1>
      <Link to="/" className="text-sm text-brand-700 underline">
        Retour à l'accueil
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Routes publiques : hors du layout applicatif, qui suppose une session. */}
      <Route path="/connexion" element={<LoginPage />} />
      <Route path="/mot-de-passe-oublie" element={<ForgotPasswordPage />} />
      <Route path="/reinitialiser-mot-de-passe" element={<ResetPasswordPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<HomePage />} />

        {/* Les dossiers nominatifs sont réservés aux rôles cliniques, comme
            côté API : le rôle chercheur y reçoit un 403. */}
        <Route
          path="/patients"
          element={
            <ProtectedRoute roles={CLINICAL_ROLES}>
              <PatientsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/patients/nouveau"
          element={
            <ProtectedRoute roles={CLINICAL_ROLES}>
              <PatientFormPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/patients/:patientId"
          element={
            <ProtectedRoute roles={CLINICAL_ROLES}>
              <PatientDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/patients/:patientId/modifier"
          element={
            <ProtectedRoute roles={CLINICAL_ROLES}>
              <PatientFormPage />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
