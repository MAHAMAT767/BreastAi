/** Primitives d'interface partagées. */

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

// --------------------------------------------------------------------------- //
// Retours d'état
// --------------------------------------------------------------------------- //

type AlertVariant = 'error' | 'success' | 'info' | 'warning';

const ALERT_STYLES: Record<AlertVariant, string> = {
  error: 'border-red-300 bg-red-50 text-red-900',
  success: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  info: 'border-slate-300 bg-slate-50 text-slate-800',
  warning: 'border-amber-300 bg-amber-50 text-amber-900',
};

export function Alert({
  variant = 'info',
  children,
}: {
  variant?: AlertVariant;
  children: ReactNode;
}) {
  return (
    <div
      role="alert"
      className={`rounded-lg border px-4 py-3 text-sm ${ALERT_STYLES[variant]}`}
    >
      {children}
    </div>
  );
}

export function Spinner({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-8 text-sm text-slate-500" role="status">
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-500"
      />
      {label}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 px-6 py-12 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Formulaires
// --------------------------------------------------------------------------- //

interface FieldProps {
  label: string;
  htmlFor: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: ReactNode;
}

export function Field({ label, htmlFor, required, hint, error, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm font-medium text-slate-700">
        {label}
        {required && (
          <span className="ml-1 text-red-600" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
      {error && (
        <p className="text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

const CONTROL_CLASSES =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 ' +
  'placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 ' +
  'focus:ring-brand-500/30 disabled:bg-slate-100 disabled:text-slate-500';

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL_CLASSES} ${props.className ?? ''}`} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${CONTROL_CLASSES} ${props.className ?? ''}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL_CLASSES} ${props.className ?? ''}`} />;
}

// --------------------------------------------------------------------------- //
// Boutons
// --------------------------------------------------------------------------- //

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 focus-visible:ring-brand-500',
  secondary:
    'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:ring-slate-400',
  danger: 'bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500',
  ghost: 'text-slate-600 hover:bg-slate-100 focus-visible:ring-slate-400',
};

/**
 * Donne à un lien l'apparence d'un bouton sans changer sa nature : un `<a>`
 * enveloppé dans un `<button>` perd l'ouverture en nouvel onglet et la copie
 * d'adresse.
 */
export function buttonClasses(variant: ButtonVariant = 'primary', extra = ''): string {
  return (
    'inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium ' +
    'transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 ' +
    `${BUTTON_STYLES[variant]} ${extra}`
  );
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
}

export function Button({
  variant = 'primary',
  loading = false,
  disabled,
  children,
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading}
      className={buttonClasses(
        variant,
        `disabled:cursor-not-allowed disabled:opacity-60 ${className ?? ''}`,
      )}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
}
