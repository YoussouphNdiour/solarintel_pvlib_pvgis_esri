import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { useRegister } from '@/hooks/useAuth'
import type { UserRole } from '@/types/api'

// ── Validation schema ─────────────────────────────────────────────────────────

const registerSchema = z
  .object({
    email: z.string().email('Adresse email invalide'),
    password: z
      .string()
      .min(8, 'Le mot de passe doit contenir au moins 8 caractères'),
    confirmPassword: z.string().min(1, 'Confirmez votre mot de passe'),
    fullName: z.string().optional(),
    company: z.string().optional(),
    role: z.enum(['admin', 'commercial', 'technicien', 'client'] as const).optional(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Les mots de passe ne correspondent pas',
    path: ['confirmPassword'],
  })

type RegisterFormValues = z.infer<typeof registerSchema>

// ── Field component ───────────────────────────────────────────────────────────

interface FieldProps {
  id: string
  label: string
  error?: string | undefined
  children: React.ReactNode
}

function Field({ id, label, error, children }: FieldProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <div className="mt-1">{children}</div>
      {error !== undefined && (
        <p id={`${id}-error`} className="mt-1 text-xs text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

const inputClass = (hasError: boolean) =>
  `block w-full rounded-lg border px-3 py-2.5 text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-solar-500 ${
    hasError
      ? 'border-red-400 bg-red-50'
      : 'border-gray-300 bg-white hover:border-gray-400'
  }`

// ── RegisterPage ──────────────────────────────────────────────────────────────

export default function RegisterPage() {
  const registerMutation = useRegister()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: 'client' },
  })

  const onSubmit = (values: RegisterFormValues) => {
    const { confirmPassword: _unused, ...payload } = values
    void _unused
    registerMutation.mutate({
      email: payload.email,
      password: payload.password,
      ...(payload.fullName !== undefined && payload.fullName.length > 0 && { fullName: payload.fullName }),
      ...(payload.company !== undefined && payload.company.length > 0 && { company: payload.company }),
      ...(payload.role !== undefined && { role: payload.role as UserRole }),
    })
  }

  return (
    <div className="register-page flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-solar-500">
            <span className="text-lg font-bold text-white">SI</span>
          </div>
          <span className="text-2xl font-bold text-gray-900">SolarIntel v2</span>
        </div>

        <div className="rounded-2xl bg-white px-8 py-10 shadow-sm ring-1 ring-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Créer un compte</h2>
          <p className="mt-1 text-sm text-gray-500">
            Rejoignez la plateforme de dimensionnement PV
          </p>

          <form
            className="mt-6 space-y-4"
            onSubmit={handleSubmit(onSubmit)}
            noValidate
          >
            {/* Email */}
            <Field id="reg-email" label="Adresse email *" error={errors.email?.message}>
              <input
                id="reg-email"
                type="email"
                autoComplete="email"
                {...register('email')}
                className={inputClass(errors.email !== undefined)}
                aria-invalid={errors.email !== undefined}
                aria-describedby={errors.email !== undefined ? 'reg-email-error' : undefined}
              />
            </Field>

            {/* Full name */}
            <Field id="reg-fullname" label="Nom complet" error={errors.fullName?.message}>
              <input
                id="reg-fullname"
                type="text"
                autoComplete="name"
                {...register('fullName')}
                className={inputClass(errors.fullName !== undefined)}
                placeholder="Moussa Diallo"
              />
            </Field>

            {/* Company */}
            <Field id="reg-company" label="Entreprise" error={errors.company?.message}>
              <input
                id="reg-company"
                type="text"
                {...register('company')}
                className={inputClass(errors.company !== undefined)}
                placeholder="SolarCo Sénégal"
              />
            </Field>

            {/* Role */}
            <Field id="reg-role" label="Rôle" error={errors.role?.message}>
              <select
                id="reg-role"
                {...register('role')}
                className={inputClass(errors.role !== undefined)}
                aria-label="Sélectionner un rôle"
              >
                <option value="client">Client</option>
                <option value="technicien">Technicien</option>
                <option value="commercial">Commercial</option>
                <option value="admin">Administrateur</option>
              </select>
            </Field>

            {/* Password */}
            <Field id="reg-password" label="Mot de passe *" error={errors.password?.message}>
              <input
                id="reg-password"
                type="password"
                autoComplete="new-password"
                {...register('password')}
                className={inputClass(errors.password !== undefined)}
                aria-invalid={errors.password !== undefined}
                aria-describedby={errors.password !== undefined ? 'reg-password-error' : undefined}
              />
            </Field>

            {/* Confirm password */}
            <Field id="reg-confirm" label="Confirmer le mot de passe *" error={errors.confirmPassword?.message}>
              <input
                id="reg-confirm"
                type="password"
                autoComplete="new-password"
                {...register('confirmPassword')}
                className={inputClass(errors.confirmPassword !== undefined)}
                aria-invalid={errors.confirmPassword !== undefined}
                aria-describedby={errors.confirmPassword !== undefined ? 'reg-confirm-error' : undefined}
              />
            </Field>

            {/* API error */}
            {registerMutation.isError && (
              <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
                Erreur lors de la création du compte. Cet email est peut-être déjà utilisé.
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting || registerMutation.isPending}
              className="mt-2 flex w-full justify-center rounded-lg bg-solar-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-solar-600 focus:outline-none focus:ring-2 focus:ring-solar-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              aria-label="Créer mon compte"
            >
              {registerMutation.isPending ? 'Création...' : 'Créer mon compte'}
            </button>
          </form>
        </div>

        {/* Login link */}
        <p className="mt-6 text-center text-sm text-gray-500">
          Déjà un compte ?{' '}
          <Link
            to="/login"
            className="font-semibold text-solar-600 hover:text-solar-700"
          >
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  )
}
