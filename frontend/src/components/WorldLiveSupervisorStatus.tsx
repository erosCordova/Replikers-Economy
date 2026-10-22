import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

type SupervisorSnapshot = {
  status: string;
  running: boolean;
  stop_requested: boolean;
  executions_completed: number;
  executions_failed: number;
  last_error_type: string | null;
  owner_id: number;
  max_rounds: number;
  scope: string;
  http_enabled: boolean;
  pilot_used: boolean;
  real_payments_active: boolean;
};

const endpoint = "/world/scheduler/live/control/mine";

function validSnapshot(value: unknown): value is SupervisorSnapshot {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const item = value as Record<string, unknown>;

  return (
    typeof item.status === "string" &&
    typeof item.running === "boolean" &&
    typeof item.stop_requested === "boolean" &&
    typeof item.http_enabled === "boolean" &&
    typeof item.pilot_used === "boolean" &&
    typeof item.real_payments_active === "boolean" &&
    typeof item.owner_id === "number" &&
    typeof item.max_rounds === "number" &&
    typeof item.executions_completed === "number" &&
    typeof item.executions_failed === "number" &&
    typeof item.scope === "string" &&
    (
      item.last_error_type === null ||
      typeof item.last_error_type === "string"
    )
  );
}

function describeError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const detail: unknown = error.response?.data?.detail;

    const requestUrl = api.getUri(
      error.config ?? { url: endpoint },
    );

    const message =
      typeof detail === "string"
        ? detail
        : error.message;

    return (
      `HTTP ${status ?? "sin respuesta"} | ` +
      `URL: ${requestUrl} | ` +
      `Detalle: ${message}`
    );
  }

  return error instanceof Error
    ? `Error: ${error.message}`
    : "Error desconocido al consultar el supervisor.";
}

function getStatusLabel(snapshot: SupervisorSnapshot | null) {
  if (!snapshot) return "Sin conexión";
  if (snapshot.running && snapshot.stop_requested) {
    return "Deteniendo...";
  }
  if (snapshot.running) return "Ejecutándose";
  if (snapshot.status === "failed") return "Error detectado";
  if (snapshot.pilot_used) return "Prueba utilizada";
  if (snapshot.status === "completed") return "Rondas completadas";
  if (snapshot.status === "stopped") return "Detenido";
  if (!snapshot.http_enabled) return "Inicio bloqueado";
  return "Preparado";
}

export default function WorldLiveSupervisorStatus() {
  const [snapshot, setSnapshot] =
    useState<SupervisorSnapshot | null>(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] =
    useState<"start" | "stop" | null>(null);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await api.get<unknown>(
        endpoint,
        { signal },
      );

      if (signal?.aborted) return;

      if (!validSnapshot(response.data)) {
        throw new Error("Respuesta de estado no reconocida");
      }

      setSnapshot(response.data);
      setError("");
    } catch (err) {
      if (signal?.aborted) return;

      setError(describeError(err));
      setSnapshot(null);
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let pending = false;

    async function poll() {
      if (
        pending ||
        controller.signal.aborted ||
        document.visibilityState !== "visible"
      ) return;

      pending = true;

      try {
        await refresh(controller.signal);
      } finally {
        pending = false;
      }
    }

    void poll();

    const interval = window.setInterval(
      () => void poll(),
      10000,
    );

    function onVisibilityChange() {
      if (document.visibilityState === "visible") {
        void poll();
      }
    }

    document.addEventListener(
      "visibilitychange",
      onVisibilityChange,
    );

    return () => {
      controller.abort();
      window.clearInterval(interval);
      document.removeEventListener(
        "visibilitychange",
        onVisibilityChange,
      );
    };
  }, [refresh]);

  async function operate(action: "start" | "stop") {
    if (busy) return;

    if (action === "start") {
      if (
        !snapshot?.http_enabled ||
        snapshot.running ||
        snapshot.real_payments_active
      ) {
        return;
      }

      const approved = window.confirm(
        "¿Iniciar las rondas autónomas simuladas de Replikers World?\n\n" +
        "Esta acción puede utilizar Gemini y registrar nuevas " +
        "negociaciones ficticias.\n\n" +
        "No se realizarán pagos reales."
      );

      if (!approved) return;
    } else {
      if (!snapshot?.running || snapshot.stop_requested) {
        return;
      }
    }

    setBusy(action);
    setMessage("");
    setError("");

    try {
      const response = await api.post(
        endpoint + "/" + action,
      );

      const data: unknown = response.data;

      if (
        typeof data === "object" &&
        data !== null &&
        validSnapshot(data)
      ) {
        setSnapshot(data);
      }

      setMessage(
        action === "start"
          ? "Se solicitó el inicio del supervisor."
          : "Se solicitó la parada del supervisor."
      );
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(null);
      await refresh();
    }
  }

  const running = snapshot?.running === true;

  const canStart =
    snapshot?.http_enabled === true &&
    snapshot.real_payments_active === false &&
    snapshot.pilot_used === false &&
    !running &&
    busy === null;

  const canStop =
    running &&
    snapshot?.stop_requested !== true &&
    busy === null;

  const status = getStatusLabel(snapshot);

  const cardStyle: React.CSSProperties = {
    padding: 12,
    borderRadius: 11,
    background: "#eff6ff",
  };

  return (
    <section
      aria-label="Control autónomo de Replikers World"
      style={{
        padding: 16,
        marginBottom: 14,
        border: "1px solid #cbdaf0",
        borderRadius: 14,
        background: "#ffffff",
        color: "#24354e",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <strong style={{ fontSize: 16 }}>
            Supervisor autónomo Gemini
          </strong>
          <p style={{
            margin: "4px 0 0",
            fontSize: 12,
            color: "#64748b",
          }}>
            Control de rondas en la economía ficticia RCR
          </p>
        </div>

        <span
          aria-live="polite"
          style={{
            padding: "7px 12px",
            borderRadius: 20,
            fontSize: 12,
            fontWeight: 700,
            background: running ? "#dcfce7" : "#e8eef6",
            color: running ? "#166534" : "#475569",
          }}
        >
          {loading ? "Consultando..." : status}
        </span>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(115px, 1fr))",
          gap: 10,
          marginTop: 14,
        }}
      >
        <div style={cardStyle}>
          <small>Rondas máximas</small>
          <div style={{ fontSize: 23, fontWeight: 700 }}>
            {snapshot?.max_rounds ?? "—"}
          </div>
        </div>

        <div style={{
          ...cardStyle,
          background: "#f0fdf4",
        }}>
          <small>Ejecuciones completadas</small>
          <div style={{ fontSize: 23, fontWeight: 700 }}>
            {snapshot?.executions_completed ?? "—"}
          </div>
        </div>

        <div style={{
          ...cardStyle,
          background: "#fff7ed",
        }}>
          <small>Ejecuciones fallidas</small>
          <div style={{ fontSize: 23, fontWeight: 700 }}>
            {snapshot?.executions_failed ?? "—"}
          </div>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          marginTop: 15,
        }}
      >
        <button
          type="button"
          disabled={!canStart}
          onClick={() => void operate("start")}
          style={{
            padding: "10px 17px",
            border: 0,
            borderRadius: 10,
            fontWeight: 700,
            color: "#ffffff",
            background: canStart ? "#16a34a" : "#9ca3af",
            cursor: canStart ? "pointer" : "not-allowed",
          }}
        >
          {busy === "start" ? "Iniciando..." : "▶ Iniciar"}
        </button>

        <button
          type="button"
          disabled={!canStop}
          onClick={() => void operate("stop")}
          style={{
            padding: "10px 17px",
            border: 0,
            borderRadius: 10,
            fontWeight: 700,
            color: "#ffffff",
            background: canStop ? "#dc2626" : "#9ca3af",
            cursor: canStop ? "pointer" : "not-allowed",
          }}
        >
          {busy === "stop" ? "Deteniendo..." : "■ Detener"}
        </button>

        <button
          type="button"
          disabled={busy !== null}
          onClick={() => void refresh()}
          style={{
            padding: "10px 14px",
            border: "1px solid #cbd5e1",
            borderRadius: 10,
            background: "#ffffff",
            color: "#334155",
            cursor: "pointer",
          }}
        >
          Actualizar estado
        </button>
      </div>

      {snapshot?.pilot_used && !snapshot.running && (
        <p
          style={{
            fontSize: 12,
            color: "#92400e",
            margin: "12px 0 0",
          }}
        >
          La prueba de una ronda ya fue utilizada.
          No puedes iniciar otra desde este proceso.
        </p>
      )}

      {snapshot && !snapshot.http_enabled && (
        <p
          style={{
            fontSize: 12,
            color: "#64748b",
            margin: "12px 0 0",
          }}
        >
          El inicio está bloqueado por el backend.
          Requiere autorización explícita y un entorno
          local de desarrollo.
        </p>
      )}

      {snapshot?.stop_requested && running && (
        <p style={{ fontSize: 12, color: "#92400e" }}>
          Parada solicitada. La ronda actual puede
          tardar en finalizar si Gemini está procesando.
        </p>
      )}

      {snapshot?.last_error_type && (
        <p role="alert" style={{ fontSize: 12, color: "#b91c1c" }}>
          Último error: {snapshot.last_error_type}
        </p>
      )}

      {message && (
        <p role="status" style={{ fontSize: 12, color: "#166534" }}>
          {message}
        </p>
      )}

      {error && (
        <p role="alert" style={{ fontSize: 12, color: "#b91c1c" }}>
          {error}
        </p>
      )}

      <p
        style={{
          fontSize: 11,
          color: "#64748b",
          lineHeight: 1.5,
          margin: "12px 0 0",
        }}
      >
        Estado actualizado cada 10 segundos.
        El supervisor pertenece al proceso actual del backend.
        No realiza pagos reales.
      </p>
    </section>
  );
}
