import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import PlaceholderModelWarning from '@/components/PlaceholderModelWarning';
import PredictionBadge from '@/components/PredictionBadge';
import { Alert, Button, Spinner, TextArea } from '@/components/ui';
import { ApiError, fetchReport } from '@/lib/api';
import {
  useAnalysis,
  useRerunInference,
  useReviewAnalysis,
} from '@/lib/analysisQueries';
import { PLACEHOLDER, formatDateTime } from '@/lib/format';
import { usePatient } from '@/lib/patientQueries';
import { useAuthenticatedImage } from '@/lib/useAuthenticatedImage';
import { STATUS_LABELS } from '@/types';
import type { Analysis, AnalysisImageKind } from '@/types';

function AnalysisImage({
  analysisId,
  kind,
  caption,
  enabled = true,
}: {
  analysisId: string;
  kind: AnalysisImageKind;
  caption: string;
  enabled?: boolean;
}) {
  const { url, isLoading, error } = useAuthenticatedImage(analysisId, kind, enabled);

  return (
    <figure className="space-y-2">
      <div className="flex aspect-square items-center justify-center overflow-hidden rounded-md border border-slate-200 bg-slate-900">
        {isLoading && <span className="text-xs text-slate-400">Chargement…</span>}
        {error && <span className="px-3 text-center text-xs text-slate-400">{error}</span>}
        {url && (
          <img src={url} alt={caption} className="size-full object-contain" />
        )}
      </div>
      <figcaption className="text-center text-xs text-slate-500">{caption}</figcaption>
    </figure>
  );
}

function ResultRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-1 gap-1 border-b border-slate-100 py-2.5 sm:grid-cols-3">
      <dt className="text-sm font-medium text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-900 sm:col-span-2">{value}</dd>
    </div>
  );
}

function DoctorReview({ analysis }: { analysis: Analysis }) {
  const review = useReviewAnalysis(analysis.id);
  const [comment, setComment] = useState(analysis.doctor_comment ?? '');
  const [validated, setValidated] = useState(analysis.doctor_validated);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setComment(analysis.doctor_comment ?? '');
    setValidated(analysis.doctor_validated);
  }, [analysis.doctor_comment, analysis.doctor_validated]);

  function save() {
    setSaved(false);
    // `mutate` et non `mutateAsync` : l'erreur est déjà rendue par
    // `review.isError`, et une promesse rejetée sans `catch` remonterait en
    // rejet non géré dans la console du navigateur.
    review.mutate(
      { doctor_comment: comment, doctor_validated: validated },
      { onSuccess: () => setSaved(true) },
    );
  }

  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Lecture médicale
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          C'est cette lecture qui fait foi cliniquement, et non la sortie du modèle.
        </p>
      </div>

      {review.isError && (
        <Alert variant="error">
          {review.error instanceof ApiError
            ? review.error.message
            : 'Enregistrement impossible.'}
        </Alert>
      )}
      {saved && !review.isPending && (
        <Alert variant="success">Lecture enregistrée.</Alert>
      )}

      <div className="flex flex-col gap-1">
        <label htmlFor="doctor_comment" className="text-sm font-medium text-slate-700">
          Commentaire
        </label>
        <TextArea
          id="doctor_comment"
          rows={5}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-800">
        <input
          type="checkbox"
          className="size-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          checked={validated}
          onChange={(event) => setValidated(event.target.checked)}
        />
        J'ai relu ce cliché et je valide ce compte rendu
      </label>

      <Button onClick={save} loading={review.isPending}>
        Enregistrer la lecture
      </Button>
    </section>
  );
}

function ReportActions({ analysis }: { analysis: Analysis }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setError(null);
    setDownloading(true);
    try {
      const blob = await fetchReport(analysis.id);
      // Le PDF est récupéré avec le jeton puis remis au navigateur : un lien
      // direct vers l'API recevrait un 401, faute d'en-tête d'autorisation.
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `breastai-rapport-${analysis.id.slice(0, 8)}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Téléchargement impossible.');
    } finally {
      setDownloading(false);
    }
  }

  const unavailable = analysis.status !== 'completed';

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        Compte rendu
      </h2>

      {error && <Alert variant="error">{error}</Alert>}

      <p className="text-sm text-slate-600">
        {unavailable
          ? "Le compte rendu n'est disponible que pour une analyse terminée."
          : 'Le compte rendu reprend le dossier, les images, le résultat et la lecture médicale.'}
      </p>

      <Button onClick={download} loading={downloading} disabled={unavailable}>
        Télécharger le PDF
      </Button>

      {analysis.report_generated_at && (
        <p className="text-xs text-slate-500">
          Dernière édition : {formatDateTime(analysis.report_generated_at)}
          {analysis.report_signature && (
            <>
              {' · empreinte '}
              <span className="font-mono">{analysis.report_signature.slice(0, 16)}…</span>
            </>
          )}
        </p>
      )}
    </section>
  );
}

export default function AnalysisDetailPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const { data: analysis, isPending, isError, error } = useAnalysis(analysisId);
  const { data: patient } = usePatient(analysis?.patient_id);
  const rerun = useRerunInference(analysisId ?? '');

  if (isPending) return <Spinner label="Chargement de l'analyse…" />;

  if (isError || !analysis) {
    return (
      <Alert variant="error">
        {error instanceof Error ? error.message : 'Analyse introuvable.'}
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <nav aria-label="Fil d'Ariane" className="text-sm text-slate-500">
        <Link to="/patients" className="underline">
          Patients
        </Link>
        <span aria-hidden="true"> / </span>
        <Link to={`/patients/${analysis.patient_id}`} className="underline">
          {patient?.full_name ?? 'Dossier'}
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="text-slate-700">Analyse</span>
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {analysis.original_filename}
          </h1>
          <p className="text-sm text-slate-500">
            Déposée le {formatDateTime(analysis.created_at)} ·{' '}
            {STATUS_LABELS[analysis.status]}
          </p>
        </div>
        <Button
          variant="secondary"
          loading={rerun.isPending}
          onClick={() => rerun.mutate()}
        >
          Relancer l'analyse
        </Button>
      </header>

      {/* Avant tout le reste : les chiffres qui suivent n'ont aucune valeur
          clinique tant que le modèle est un placeholder. */}
      {analysis.is_placeholder_model && analysis.model_warning && (
        <PlaceholderModelWarning message={analysis.model_warning} />
      )}

      {analysis.status === 'failed' && (
        <Alert variant="error">
          <p className="font-semibold">L'analyse a échoué</p>
          <p className="mt-1">{analysis.error_message ?? 'Cause inconnue.'}</p>
          <p className="mt-1">
            Le cliché reste archivé : l'analyse peut être relancée.
          </p>
        </Alert>
      )}

      <section className="rounded-lg border border-slate-200 bg-white px-5 py-2">
        <h2 className="sr-only">Résultat du modèle</h2>
        <dl>
          <ResultRow
            label="Classification"
            value={
              analysis.prediction
                ? `${analysis.prediction === 'malignant' ? 'Malin' : 'Bénin'}`
                : PLACEHOLDER
            }
          />
          <ResultRow
            label="Probabilité de malignité"
            value={
              analysis.probability != null
                ? `${(analysis.probability * 100).toFixed(1)} %`
                : PLACEHOLDER
            }
          />
          <ResultRow
            label="Score de confiance"
            value={
              analysis.confidence != null
                ? `${(analysis.confidence * 100).toFixed(1)} %`
                : PLACEHOLDER
            }
          />
          <ResultRow
            label="Temps d'inférence"
            value={
              analysis.inference_time_ms != null
                ? `${Math.round(analysis.inference_time_ms)} ms`
                : PLACEHOLDER
            }
          />
          <ResultRow label="Modèle" value={analysis.model_version ?? PLACEHOLDER} />
          <ResultRow
            label="Prétraitement"
            value={analysis.preprocessing_version ?? PLACEHOLDER}
          />
          <ResultRow label="Format" value={(analysis.image_format ?? '—').toUpperCase()} />
        </dl>
        <div className="py-3">
          <PredictionBadge
            prediction={analysis.prediction}
            probability={analysis.probability}
          />
        </div>
      </section>

      <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Imagerie
        </h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <AnalysisImage
            analysisId={analysis.id}
            kind="processed"
            caption="Image prétraitée, telle que vue par le modèle"
          />
          <AnalysisImage
            analysisId={analysis.id}
            kind="gradcam"
            caption="Superposition Grad-CAM"
            enabled={analysis.has_gradcam}
          />
        </div>

        {analysis.suspicious_region && (
          <p className="text-sm text-slate-700">
            Zone la plus activée : rectangle de {analysis.suspicious_region.width} ×{' '}
            {analysis.suspicious_region.height} pixels, à (
            {analysis.suspicious_region.x}, {analysis.suspicious_region.y}) dans
            l'image prétraitée.
          </p>
        )}

        {analysis.gradcam_disclaimer && (
          <Alert variant="warning">{analysis.gradcam_disclaimer}</Alert>
        )}
      </section>

      <DoctorReview analysis={analysis} />
      <ReportActions analysis={analysis} />
    </div>
  );
}
