/**
 * @vitest-environment node
 *
 * Dépôt réel d'une mammographie contre l'API.
 *
 * Ce fichier tourne en environnement **node**, et non jsdom, contrairement au
 * reste des tests. Raison : le `FormData` et le `File` de jsdom ne sont pas
 * ceux qu'attend le `fetch` d'undici utilisé par Node. Un envoi multipart
 * construit avec les objets jsdom ne quitte jamais le processus — la requête
 * reste en suspens jusqu'au délai d'expiration, sans jamais atteindre le
 * serveur. En environnement node, `File`, `FormData` et `fetch` proviennent
 * tous de Node et s'accordent.
 *
 * Ce n'est un problème que pour les tests : dans un navigateur, les trois sont
 * natifs et compatibles. Le parcours d'interface correspondant est couvert par
 * `AnalysisDetailPage.test.tsx`, avec un serveur simulé.
 *
 * Prérequis : backend démarré, base migrée, compte administrateur créé.
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { API_URL } from '@/lib/api';
import * as api from '@/lib/api';
import { clearTokens } from '@/lib/tokens';

const EMAIL = process.env.VITE_TEST_EMAIL ?? 'admin@breastai.local';
const PASSWORD = process.env.VITE_TEST_PASSWORD ?? 'BreastAI-Dev-2026!';

async function apiIsReachable(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(3000) });
    return response.ok;
  } catch {
    return false;
  }
}

const reachable = await apiIsReachable();

// En intégration continue, une suite qui s'ignore est un vert mensonger :
// `VITE_REQUIRE_API=1` transforme l'absence de backend en échec.
if (process.env.VITE_REQUIRE_API === '1' && !reachable) {
  throw new Error(
    `VITE_REQUIRE_API=1 mais l'API est injoignable sur ${API_URL}. ` +
      'Les tests de dépôt ne peuvent pas être ignorés dans ce contexte.',
  );
}

/**
 * PNG 40×48 en niveaux de gris, valide et décodable par OpenCV.
 *
 * Un fond noir avec une zone dense plus claire au centre : assez de structure
 * pour que le débruitage, le CLAHE et le Grad-CAM aient quelque chose à traiter,
 * assez peu d'entropie pour tenir en 108 octets une fois compressé — d'où
 * l'intégration en dur plutôt qu'un fichier binaire versionné.
 */
const PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAACgAAAAwCAAAAABGEGdHAAAAM0lEQVQ4y2NgGAUj' +
  'BTDCGCdwKLCA0kzEmjgUFLKgcs2R2CeHnGdGFZIS1ydHhq9HwcgBAHFmAv1y9GrP' +
  'AAAAAElFTkSuQmCC';

function makePng(name = 'mammographie-integration.png'): File {
  const bytes = Uint8Array.from(Buffer.from(PNG_BASE64, 'base64'));
  return new File([bytes], name, { type: 'image/png' });
}

const createdPatientIds: string[] = [];

function uniqueCode(): string {
  return `TCD-UP-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
}

async function newPatient() {
  const patient = await api.createPatient({
    code: uniqueCode(),
    first_name: 'Analyse',
    last_name: 'Upload',
    birth_date: null,
    sex: 'F',
    phone: null,
    email: null,
    address: null,
    medical_history: null,
    notes: null,
  });
  createdPatientIds.push(patient.id);
  return patient;
}

describe.skipIf(!reachable)("Dépôt réel d'une mammographie", () => {
  beforeAll(async () => {
    clearTokens();
    await api.login(EMAIL, PASSWORD);
  });

  afterAll(async () => {
    for (const id of createdPatientIds.splice(0)) {
      try {
        await api.deletePatient(id);
      } catch {
        // Déjà supprimé.
      }
    }
    clearTokens();
  });

  it('dépose un PNG et obtient une prédiction complète', async () => {
    const patient = await newPatient();

    const analysis = await api.uploadAnalysis(patient.id, makePng());

    expect(analysis.status).toBe('completed');
    expect(['benign', 'malignant']).toContain(analysis.prediction);
    expect(analysis.probability).toBeGreaterThanOrEqual(0);
    expect(analysis.probability).toBeLessThanOrEqual(1);
    expect(analysis.confidence).toBeGreaterThan(0);
    expect(analysis.inference_time_ms).toBeGreaterThan(0);
    expect(analysis.image_format).toBe('png');
    expect(analysis.preprocessing_version).toBeTruthy();
  }, 60_000);

  it('produit une carte Grad-CAM et localise une zone', async () => {
    const patient = await newPatient();

    const analysis = await api.uploadAnalysis(patient.id, makePng());

    expect(analysis.has_gradcam).toBe(true);
    expect(analysis.gradcam_disclaimer).toContain("non l'emplacement d'une lésion");
    expect(analysis.suspicious_region).not.toBeNull();
  }, 60_000);

  it('marque le résultat comme provenant du modèle de démonstration', async () => {
    const patient = await newPatient();

    const analysis = await api.uploadAnalysis(patient.id, makePng());

    expect(analysis.is_placeholder_model).toBe(true);
    expect(analysis.model_version).toMatch(/^placeholder-/);
    expect(analysis.model_warning).toContain('AUCUNE VALEUR CLINIQUE');
  }, 60_000);

  it('sert les images prétraitée et Grad-CAM', async () => {
    const patient = await newPatient();
    const analysis = await api.uploadAnalysis(patient.id, makePng());

    const processed = await api.fetchAnalysisImage(analysis.id, 'processed');
    const gradcam = await api.fetchAnalysisImage(analysis.id, 'gradcam');
    const original = await api.fetchAnalysisImage(analysis.id, 'original');

    expect(processed.size).toBeGreaterThan(0);
    expect(processed.type).toBe('image/png');
    expect(gradcam.size).toBeGreaterThan(0);
    expect(original.size).toBeGreaterThan(0);
  }, 60_000);

  it("refuse un fichier qui n'est pas une image", async () => {
    const patient = await newPatient();
    const file = new File(['%PDF-1.4 pas une image'], 'rapport.pdf', {
      type: 'application/pdf',
    });

    await expect(api.uploadAnalysis(patient.id, file)).rejects.toMatchObject({ status: 400 });
  }, 60_000);

  it('refuse un PNG dont le contenu est illisible', async () => {
    const patient = await newPatient();
    // Signature PNG correcte, contenu corrompu : la validation ne s'arrête pas
    // aux octets magiques.
    const corrupted = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, ...new Uint8Array(64)]);
    const file = new File([corrupted], 'casse.png', { type: 'image/png' });

    await expect(api.uploadAnalysis(patient.id, file)).rejects.toMatchObject({ status: 422 });
  }, 60_000);

  it('rejoue l’inférence de façon déterministe', async () => {
    const patient = await newPatient();
    const first = await api.uploadAnalysis(patient.id, makePng());

    const second = await api.rerunInference(first.id);

    expect(second.prediction).toBe(first.prediction);
    expect(second.probability).toBeCloseTo(first.probability ?? 0, 5);
  }, 90_000);

  it('enregistre la lecture médicale, produit le PDF et le vérifie', async () => {
    const patient = await newPatient();
    const analysis = await api.uploadAnalysis(patient.id, makePng());

    const reviewed = await api.reviewAnalysis(analysis.id, {
      doctor_comment: 'Contrôle recommandé à 12 mois.',
      doctor_validated: true,
    });
    expect(reviewed.doctor_validated).toBe(true);

    const pdf = await api.fetchReport(analysis.id);
    expect(pdf.type).toBe('application/pdf');
    expect(pdf.size).toBeGreaterThan(1000);

    const verification = await api.verifyReport(analysis.id);
    expect(verification.signature_valid).toBe(true);
  }, 90_000);

  it('alimente le tableau de bord', async () => {
    const before = await api.fetchDashboardStats();

    const patient = await newPatient();
    await api.uploadAnalysis(patient.id, makePng());

    const after = await api.fetchDashboardStats();

    expect(after.total_analyses).toBe(before.total_analyses + 1);
    expect(after.completed_analyses).toBe(before.completed_analyses + 1);
    expect(after.monthly).toHaveLength(12);
    // Aucun taux d'exactitude n'est publiable sans diagnostic de référence.
    expect(after.accuracy_available).toBe(false);
    expect(after.accuracy_note).toContain('pas la justesse du modèle');
  }, 60_000);
});

describe.skipIf(reachable)("Dépôt réel d'une mammographie", () => {
  it('est ignoré : API injoignable', () => {
    expect(reachable).toBe(false);
  });
});
