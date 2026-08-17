/**
 * Composants de visualisation du tableau de bord.
 *
 * Choix qui structurent tout ce fichier :
 *
 * - **Bleu et orange pour bénin/malin**, jamais vert et rouge : ce dernier
 *   couple est indistinguable en deutéranopie et protanopie. Voir le commentaire
 *   des tokens dans `index.css`.
 * - **La couleur ne porte jamais l'information seule** : chaque série est
 *   accompagnée de son libellé, une légende est présente dès deux séries, et
 *   chaque graphique a son équivalent en tableau.
 * - **Pas de camembert pour une répartition à deux parts** : une barre empilée
 *   se lit sans comparer des angles.
 * - **Grille en filet plein**, jamais pointillée : le pointillé se lit comme un
 *   seuil ou une projection alors qu'il ne s'agit que d'un repère.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TooltipProps } from 'recharts';

import type { MonthlyCount } from '@/types';

const GRID = 'var(--color-chart-grid)';
const AXIS = 'var(--color-chart-axis)';
const MUTED = 'var(--color-chart-muted)';
const BENIGN = 'var(--color-benign)';
const MALIGNANT = 'var(--color-malignant)';

const MONTH_FORMATTER = new Intl.DateTimeFormat('fr-FR', { month: 'short', year: '2-digit' });

export function formatMonth(iso: string): string {
  const [year, month] = iso.split('-').map(Number);
  if (!year || !month) return iso;
  return MONTH_FORMATTER.format(new Date(year, month - 1, 1));
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('fr-FR').format(value);
}

// --------------------------------------------------------------------------- //
// Analyses par mois
// --------------------------------------------------------------------------- //

function MonthlyTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;

  const bucket = payload[0].payload as MonthlyCount;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-slate-800">{label}</p>
      <p className="text-slate-600">{formatNumber(bucket.total)} analyse(s)</p>
      <p className="text-slate-500">
        Bénin {formatNumber(bucket.benign)} · Malin {formatNumber(bucket.malignant)}
      </p>
    </div>
  );
}

export function MonthlyAnalysesChart({ data }: { data: MonthlyCount[] }) {
  const rows = data.map((bucket) => ({ ...bucket, label: formatMonth(bucket.month) }));
  const hasData = rows.some((row) => row.total > 0);

  return (
    <figure className="space-y-3">
      <figcaption>
        <h3 className="text-sm font-semibold text-slate-800">Analyses par mois</h3>
        <p className="text-xs text-slate-500">
          Analyses terminées sur les douze derniers mois. Un mois sans activité
          vaut zéro, il n'est pas omis.
        </p>
      </figcaption>

      {/* Hauteur fixée sur le graphique ET sa bande d'axe : sinon les libellés
          de mois débordent et la carte se met à défiler verticalement. */}
      <div className="h-64">
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID} strokeWidth={1} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: AXIS }}
                tick={{ fill: MUTED, fontSize: 11 }}
                interval="preserveStartEnd"
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={36}
                tick={{ fill: MUTED, fontSize: 11 }}
              />
              <Tooltip
                content={<MonthlyTooltip />}
                cursor={{ fill: 'rgba(11,11,11,0.04)' }}
              />
              {/* Série unique : une seule teinte, et pas de légende — le titre
                  dit déjà ce qui est tracé. Sommet arrondi, base carrée. */}
              <Bar
                dataKey="total"
                name="Analyses"
                fill={BENIGN}
                maxBarSize={24}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center rounded-md border border-dashed border-slate-300 text-sm text-slate-500">
            Aucune analyse terminée sur les douze derniers mois.
          </div>
        )}
      </div>

      <details className="text-sm">
        <summary className="cursor-pointer text-slate-600">Voir les données</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th scope="col" className="py-1.5 pr-4 font-semibold">Mois</th>
                <th scope="col" className="py-1.5 pr-4 font-semibold">Total</th>
                <th scope="col" className="py-1.5 pr-4 font-semibold">Bénin</th>
                <th scope="col" className="py-1.5 font-semibold">Malin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 tabular-nums">
              {rows.map((row) => (
                <tr key={row.month}>
                  <td className="py-1.5 pr-4 text-slate-700">{row.label}</td>
                  <td className="py-1.5 pr-4 text-slate-700">{formatNumber(row.total)}</td>
                  <td className="py-1.5 pr-4 text-slate-700">{formatNumber(row.benign)}</td>
                  <td className="py-1.5 text-slate-700">{formatNumber(row.malignant)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

// --------------------------------------------------------------------------- //
// Répartition bénin / malin
// --------------------------------------------------------------------------- //

/**
 * Barre empilée en HTML, et non en Recharts.
 *
 * Deux parts seulement : le camembert est exclu (comparer deux angles est plus
 * dur que comparer deux longueurs), et une barre empilée en CSS permet le
 * séparateur de 2 pixels dans la couleur de fond — le mécanisme prévu pour
 * séparer deux aplats sans dessiner de contour autour d'eux.
 */
export function PredictionSplit({
  benign,
  malignant,
}: {
  benign: number;
  malignant: number;
}) {
  const total = benign + malignant;
  const benignPercent = total ? (benign / total) * 100 : 0;
  const malignantPercent = total ? (malignant / total) * 100 : 0;

  return (
    <figure className="space-y-3">
      <figcaption>
        <h3 className="text-sm font-semibold text-slate-800">Répartition des résultats</h3>
        <p className="text-xs text-slate-500">
          Sur {formatNumber(total)} analyse(s) terminée(s).
        </p>
      </figcaption>

      {total === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
          Aucune analyse terminée.
        </div>
      ) : (
        <>
          <div
            className="flex h-6 w-full overflow-hidden rounded"
            role="img"
            aria-label={`Bénin ${benign} sur ${total}, malin ${malignant} sur ${total}`}
          >
            {benign > 0 && (
              <div
                style={{
                  width: `${benignPercent}%`,
                  backgroundColor: BENIGN,
                  // Séparateur de 2 px dans la couleur de surface.
                  marginRight: malignant > 0 ? 2 : 0,
                }}
              />
            )}
            {malignant > 0 && (
              <div style={{ width: `${malignantPercent}%`, backgroundColor: MALIGNANT }} />
            )}
          </div>

          {/* Légende présente dès deux séries, avec les valeurs en clair :
              l'identité ne repose jamais sur la seule couleur. */}
          <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <li className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="size-2.5 rounded-full"
                style={{ backgroundColor: BENIGN }}
              />
              <span className="text-slate-700">
                Bénin — {formatNumber(benign)} ({benignPercent.toFixed(1)} %)
              </span>
            </li>
            <li className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="size-2.5 rounded-full"
                style={{ backgroundColor: MALIGNANT }}
              />
              <span className="text-slate-700">
                Malin — {formatNumber(malignant)} ({malignantPercent.toFixed(1)} %)
              </span>
            </li>
          </ul>
        </>
      )}
    </figure>
  );
}

// --------------------------------------------------------------------------- //
// Tuiles
// --------------------------------------------------------------------------- //

/**
 * Tuile de chiffre clé.
 *
 * `tone` teinte la tuile quand le chiffre *est* un résultat : bleu pour les
 * bénins, orange pour les malins, aux mêmes teintes que les pastilles et la
 * barre de répartition. Les compteurs qui ne sont pas des résultats — patients,
 * analyses déposées — restent neutres. C'est ce qui fait que la couleur se lit
 * comme une information et non comme une décoration.
 *
 * L'ordre libellé → valeur → précision est structurant : le libellé annonce ce
 * qu'on lit avant de le lire, et `DashboardPage.test.tsx` s'appuie sur cet
 * ordre pour retrouver la valeur d'une tuile.
 */
type TileTone = 'neutral' | 'benign' | 'malignant';

/*
 * `muted` passe en slate-600 sur les fonds teintés : slate-500 y tombe à
 * 4,2:1, sous le seuil AA, alors qu'il tient (4,8:1) sur le blanc des tuiles
 * neutres.
 */
const TILE_TONES: Record<TileTone, { box: string; value: string; muted: string }> = {
  neutral: {
    box: 'border-slate-200 bg-white',
    value: 'text-slate-900',
    muted: 'text-slate-500',
  },
  benign: {
    box: 'border-transparent bg-[var(--color-benign-soft)]',
    value: 'text-[var(--color-benign-strong)]',
    muted: 'text-slate-600',
  },
  malignant: {
    box: 'border-transparent bg-[var(--color-malignant-soft)]',
    value: 'text-[var(--color-malignant-strong)]',
    muted: 'text-slate-600',
  },
};

export function StatTile({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: TileTone;
}) {
  const styles = TILE_TONES[tone];

  return (
    <div className={`rounded-lg border p-4 ${styles.box}`}>
      <p className={`text-xs font-medium uppercase tracking-wide ${styles.muted}`}>{label}</p>
      {/* `tabular-nums` : les tuiles sont alignées en grille, des chiffres de
          largeurs différentes décaleraient les valeurs d'une colonne à l'autre. */}
      <p className={`mt-1 text-[28px] font-semibold leading-none tabular-nums ${styles.value}`}>
        {value}
      </p>
      {hint && <p className={`mt-2 text-xs leading-snug ${styles.muted}`}>{hint}</p>}
    </div>
  );
}
