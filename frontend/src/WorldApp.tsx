
/* REPLIKERS_WORLD_MAIN_APP_V2 */

import axios from "axios";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  api,
  logoutSession,
  restoreSession,
} from "./api";

import { setAccessToken } from "./auth/sesion";

import MundoReplikersWorld from "./components/MundoReplikersWorld";

import "./WorldApp.css";

type WorldUser = {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active?: boolean;
};

export default function WorldApp() {
  const [user, setUser] = useState<WorldUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [authMode, setAuthMode] = useState<
    "login" | "register"
  >("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");

  const [worldVisible, setWorldVisible] = useState(true);

  useEffect(() => {
    let active = true;

    async function initialize() {
      try {
        const existing = await restoreSession<WorldUser>();

        if (active) {
          setUser(existing || null);
        }
      } catch {
        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void initialize();

    return () => {
      active = false;
    };
  }, []);

  async function authenticate(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setBusy(true);
    setError("");

    try {
      const endpoint =
        authMode === "login"
          ? "/auth/login"
          : "/auth/register";

      const payload =
        authMode === "login"
          ? { email, password }
          : { email, password, full_name: fullName };

      const response = await api.post(endpoint, payload);

      const token = response.data?.access_token;
      const account = response.data?.user;

      if (!token || !account) {
        throw new Error("Autenticacion incompleta");
      }

      setAccessToken(token);
      setUser(account);
      setWorldVisible(true);

      setPassword("");
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        const detail: unknown = err.response?.data?.detail;
        const retryAfter = err.response?.headers?.["retry-after"];

        const message =
          typeof detail === "string"
            ? detail
            : "El servidor no proporciono detalles.";

        if (status === 429) {
          setError(
            `Error HTTP 429: ${message}` +
            (retryAfter ? ` Espera ${retryAfter} segundos.` : "")
          );
        } else if (status) {
          setError(`Error HTTP ${status}: ${message}`);
        } else {
          setError(
            "No hay conexion con el backend. " +
            "Comprueba que FastAPI siga activo."
          );
        }
      } else {
        setError(
          "No se pudo procesar la respuesta del servidor."
        );
      }
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    try {
      await logoutSession();
      setUser(null);
      setWorldVisible(true);
    } catch {
      setError("No se pudo cerrar la sesion.");
    }
  }

  if (loading) {
    return (
      <main className="rww-loading">
        <div className="rww-loader" />
        <h1>Replikers World</h1>
        <p>Preparando tu mundo de agentes...</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="rww-auth">
        <section className="rww-auth-card">
          <div className="rww-logo">RW</div>

          <div className="rww-eyebrow">
            ECONOMIA DE AGENTES INTELIGENTES
          </div>

          <h1>Replikers World</h1>

          <p className="rww-description">
            Explora un mundo virtual donde los Replikers
            administran su capital, interactuan, negocian
            y desarrollan estrategias economicas.
          </p>

          <form
            className="rww-form"
            onSubmit={authenticate}
          >
            {authMode === "register" && (
              <>
                <label htmlFor="rww-name">
                  Nombre completo
                </label>

                <input
                  id="rww-name"
                  value={fullName}
                  onChange={(e) =>
                    setFullName(e.target.value)
                  }
                  required
                />
              </>
            )}

            <label htmlFor="rww-email">
              Correo electronico
            </label>

            <input
              id="rww-email"
              type="email"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
              autoComplete="username"
              required
            />

            <label htmlFor="rww-password">
              Contrasena
            </label>

            <input
              id="rww-password"
              type="password"
              value={password}
              onChange={(e) =>
                setPassword(e.target.value)
              }
              autoComplete={
                authMode === "login"
                  ? "current-password"
                  : "new-password"
              }
              required
            />

            {error && (
              <p className="rww-error" role="alert">
                {error}
              </p>
            )}

            <button
              className="rww-primary"
              disabled={busy}
              type="submit"
            >
              {busy
                ? "Procesando..."
                : authMode === "login"
                  ? "Entrar al mundo"
                  : "Crear cuenta"}
            </button>
          </form>

          <button
            className="rww-link"
            type="button"
            onClick={() => {
              setError("");
              setAuthMode(
                authMode === "login"
                  ? "register"
                  : "login"
              );
            }}
          >
            {authMode === "login"
              ? "Crear una cuenta nueva"
              : "Ya tengo una cuenta"}
          </button>

          <div className="rww-note">
            Economia RCR simulada. Sin dinero real.
          </div>
        </section>
      </main>
    );
  }

  return (
    <div className="rww-app">
      <header className="rww-header">
        <div className="rww-brand">
          <span className="rww-mini-logo">RW</span>
          <div>
            <strong>Replikers World</strong>
            <small>
              Economia autonoma de agentes
            </small>
          </div>
        </div>

        <div className="rww-account">
          <span>
            {user.full_name || user.email}
          </span>

          <button
            type="button"
            onClick={() => void signOut()}
          >
            Cerrar sesion
          </button>
        </div>
      </header>

      {worldVisible ? (
        <main className="rww-world">
          <MundoReplikersWorld
            onClose={() => setWorldVisible(false)}
          />
        </main>
      ) : (
        <main className="rww-hub">
          <div className="rww-hub-content">
            <span className="rww-hub-icon">RW</span>

            <h1>Replikers World</h1>

            <p>
              Tu mundo economico sigue disponible.
              Entra para visualizar los Replikers,
              sus billeteras RCR y los eventos.
            </p>

            <button
              type="button"
              className="rww-primary"
              onClick={() => setWorldVisible(true)}
            >
              Volver a la ciudad
            </button>
          </div>
        </main>
      )}
    </div>
  );
}
