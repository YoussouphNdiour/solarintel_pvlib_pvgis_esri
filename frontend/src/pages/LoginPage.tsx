import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { useLogin } from '@/hooks/useAuth'

// ── Validation schema ─────────────────────────────────────────────────────────

const loginSchema = z.object({
  email: z.string().email('Adresse email invalide'),
  password: z.string().min(1, 'Le mot de passe est requis'),
})

type LoginFormValues = z.infer<typeof loginSchema>

// ── LoginPage ─────────────────────────────────────────────────────────────────

export default function LoginPage() {
  const loginMutation = useLogin()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = (values: LoginFormValues) => {
    loginMutation.mutate(values)
  }

  return (
    <div className="login-page flex min-h-screen">
      {/* Left panel — form */}
      <div className="flex flex-1 flex-col justify-center px-6 py-12 lg:w-1/2 lg:flex-none lg:px-20 xl:px-24">
        <div className="mx-auto w-full max-w-sm">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-solar-500">
              <span className="text-lg font-bold text-white">SI</span>
            </div>
            <span className="text-2xl font-bold text-gray-900">SolarIntel v2</span>
          </div>

          <h2 className="mt-8 text-2xl font-bold leading-9 text-gray-900">
            Connectez-vous à votre compte
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Plateforme de dimensionnement PV pour l'Afrique de l'Ouest
          </p>

          {/* Form */}
          <form
            className="mt-8 space-y-5"
            onSubmit={handleSubmit(onSubmit)}
            noValidate
          >
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700"
              >
                Adresse email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                {...register('email')}
                className={`mt-1 block w-full rounded-lg border px-3 py-2.5 text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-solar-500 ${
                  errors.email !== undefined
                    ? 'border-red-400 bg-red-50'
                    : 'border-gray-300 bg-white hover:border-gray-400'
                }`}
                aria-describedby={errors.email !== undefined ? 'email-error' : undefined}
                aria-invalid={errors.email !== undefined}
              />
              {errors.email !== undefined && (
                <p id="email-error" className="mt-1 text-xs text-red-600" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700"
              >
                Mot de passe
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register('password')}
                className={`mt-1 block w-full rounded-lg border px-3 py-2.5 text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-solar-500 ${
                  errors.password !== undefined
                    ? 'border-red-400 bg-red-50'
                    : 'border-gray-300 bg-white hover:border-gray-400'
                }`}
                aria-describedby={errors.password !== undefined ? 'password-error' : undefined}
                aria-invalid={errors.password !== undefined}
              />
              {errors.password !== undefined && (
                <p id="password-error" className="mt-1 text-xs text-red-600" role="alert">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* API error */}
            {loginMutation.isError && (
              <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
                Email ou mot de passe incorrect. Veuillez réessayer.
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting || loginMutation.isPending}
              className="flex w-full justify-center rounded-lg bg-solar-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-solar-600 focus:outline-none focus:ring-2 focus:ring-solar-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              aria-label="Se connecter"
            >
              {loginMutation.isPending ? 'Connexion...' : 'Se connecter'}
            </button>

            {/* Google OAuth */}
            <a
              href="/api/v2/auth/google"
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50"
              aria-label="Continuer avec Google"
            >
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z" />
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 16 19 12 24 12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 16.3 4 9.7 8.4 6.3 14.7z" />
                <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.1l-6.2-5.2C29.4 35.5 26.8 36 24 36c-5.2 0-9.7-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
                <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.4l6.2 5.2C41 34.6 44 29.8 44 24c0-1.3-.1-2.6-.4-3.9z" />
              </svg>
              Continuer avec Google
            </a>
          </form>

          {/* Register link */}
          <p className="mt-6 text-center text-sm text-gray-500">
            Pas encore de compte ?{' '}
            <Link
              to="/register"
              className="font-semibold text-solar-600 hover:text-solar-700"
            >
              Créer un compte
            </Link>
          </p>
        </div>
      </div>

      {/* Right panel — solar background */}
      <div
        className="hidden lg:block lg:flex-1 bg-gradient-to-br from-solar-400 via-solar-500 to-amber-600"
        aria-hidden="true"
      >
        <div className="flex h-full flex-col items-center justify-center gap-6 px-12 text-white">
          <div className="text-8xl" aria-hidden="true">☀️</div>
          <h2 className="text-center text-3xl font-bold">
            Dimensionnement PV intelligent
          </h2>
          <p className="text-center text-lg text-solar-100">
            Optimisez vos installations solaires au Sénégal et en Afrique de l'Ouest
            grâce à des données météo locales et des algorithmes avancés.
          </p>
          <div className="mt-4 grid grid-cols-3 gap-6 text-center">
            {[
              { value: '2 100+', label: 'Simulations' },
              { value: '98%', label: 'Précision' },
              { value: '15 pays', label: 'Couverts' },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl bg-white/20 px-4 py-3">
                <p className="text-2xl font-bold">{stat.value}</p>
                <p className="text-sm text-solar-100">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
