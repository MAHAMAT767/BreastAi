import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { Alert, Button } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useUploadAnalysis } from '@/lib/analysisQueries';
import { ACCEPTED_EXTENSIONS, MAX_UPLOAD_SIZE_MB } from '@/types';

/**
 * Contrôles locaux, identiques à ceux du serveur.
 *
 * Ils ne remplacent rien : le serveur revalide extension, taille, octets
 * magiques et décodage effectif. Ils évitent seulement de faire monter 50 Mo
 * sur une connexion lente pour recevoir un refus.
 */
function localValidationError(file: File): string | null {
  const name = file.name.toLowerCase();
  const accepted = ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension));

  if (!accepted) {
    return `Format non accepté. Attendus : ${ACCEPTED_EXTENSIONS.join(', ')}.`;
  }
  if (file.size === 0) {
    return 'Le fichier est vide.';
  }
  if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
    return `Fichier trop volumineux : maximum ${MAX_UPLOAD_SIZE_MB} Mo.`;
  }
  return null;
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} Ko`
    : `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

export default function UploadMammography({ patientId }: { patientId: string }) {
  const navigate = useNavigate();
  const upload = useUploadAnalysis(patientId);
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function select(candidate: File | undefined) {
    if (!candidate) return;

    const problem = localValidationError(candidate);
    setError(problem);
    setFile(problem ? null : candidate);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    select(event.dataTransfer.files[0]);
  }

  async function handleSubmit() {
    if (!file) return;
    setError(null);

    try {
      const analysis = await upload.mutateAsync(file);
      navigate(`/analyses/${analysis.id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Dépôt impossible.');
    }
  }

  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Déposer une mammographie
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Formats acceptés : DICOM (.dcm), PNG, JPG. Taille maximale{' '}
          {MAX_UPLOAD_SIZE_MB} Mo.
        </p>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`rounded-lg border-2 border-dashed px-6 py-8 text-center transition ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300'
        }`}
      >
        <p className="text-sm text-slate-600">
          Glissez le fichier ici, ou
        </p>
        <div className="mt-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => inputRef.current?.click()}
          >
            Choisir un fichier
          </Button>
        </div>
        <input
          ref={inputRef}
          type="file"
          // Le champ reste dans le flux accessible : `sr-only` et non `hidden`,
          // pour qu'il garde le focus au clavier et son étiquette.
          className="sr-only"
          aria-label="Fichier de mammographie"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            select(event.target.files?.[0])
          }
        />
      </div>

      {file && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-slate-50 px-4 py-3">
          <div className="text-sm">
            <p className="font-medium text-slate-800">{file.name}</p>
            <p className="text-slate-500">{formatSize(file.size)}</p>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleSubmit} loading={upload.isPending}>
              Lancer l'analyse
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setFile(null);
                setError(null);
              }}
              disabled={upload.isPending}
            >
              Retirer
            </Button>
          </div>
        </div>
      )}

      {upload.isPending && (
        <p className="text-sm text-slate-600" role="status">
          Prétraitement et analyse en cours — cela prend généralement une à deux
          secondes.
        </p>
      )}
    </section>
  );
}
