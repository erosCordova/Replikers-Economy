import { useEffect, useState } from "react";
import { api } from "../api";

type SchedulerStatus =
  | "not_connected"
  | "disabled"
  | "stopped"
  | "running";

type SchedulerSnapshot = {
  status: SchedulerStatus;
  connected: boolean;
  enabled: boolean;
  running: boolean;
  rounds_executed: number;
  rounds_failed: number;
  last_round_id: string | null;
  scope: string;
  external_ai_active: boolean;
  real_payments_active: boolean;
};

function validSnapshot(
  value: unknown,
): value is SchedulerSnapshot {
  if (
    typeof value !== "object" ||
    value === null
  ) {
    return false;
  }

  const item = value as Record<string, unknown>;

  const statuses: SchedulerStatus[] = [
    "not_connected",
    "disabled",
    "stopped",
    "running",
  ];

  return (
    typeof item.status === "string" &&
    statuses.includes(
      item.status as SchedulerStatus,
    ) &&
    typeof item.connected === "boolean" &&
    typeof item.enabled === "boolean" &&
    typeof item.running === "boolean" &&
    typeof item.rounds_executed === "number" &&
    Number.isInteger(item.rounds_executed) &&
    item.rounds_executed >= 0 &&
    typeof item.rounds_failed === "number" &&
    Number.isInteger(item.rounds_failed) &&
    item.rounds_failed >= 0 &&
    (
      item.last_round_id === null ||
      typeof item.last_round_id === "string"
    ) &&
    typeof item.scope === "string" &&
    typeof item.external_ai_active === "boolean" &&
    typeof item.real_payments_active === "boolean"
  );
}

const statusLabels: Record<
  SchedulerStatus,
  string
> = {
  not_connected: "No conectado",
  disabled: "Deshabilitado",
  stopped: "Detenido",
  running: "En ejecucion",
};

export default function WorldSchedulerStatus() {
  const [snapshot, setSnapshot] =
    useState<SchedulerSnapshot | null>(null);

  const [message, setMessage] = useState(
    "Consultando estado del controlador...",
  );

  useEffect(() => {
    const controller = new AbortController();

    let alive = true;
    let pending = false;

    async function refresh() {
      if (
        !alive ||
        pending ||
        document.visibilityState !== "visible"
      ) {
        return;
      }

      pending = true;

      try {
        const response = await api.get<unknown>(
          "/world/scheduler/mine",
          {
            signal: controller.signal,
          },
        );

        if (!alive) return;

        if (!validSnapshot(response.data)) {
          setSnapshot(null);
          setMessage(
            "El servidor devolvio un estado no reconocido.",
          );
          return;
        }

        setSnapshot(response.data);
        setMessage("");
      } catch {
        if (
          alive &&
          !controller.signal.aborted
        ) {
          setSnapshot(null);
          setMessage(
            "No se pudo consultar el supervisor.",
          );
        }
      } finally {
        pending = false;
      }
    }

    function onVisibilityChange() {
      if (document.visibilityState === "visible") {
        void refresh();
      }
    }

    void refresh();

    const interval = window.setInterval(
      () => void refresh(),
      20000,
    );

    document.addEventListener(
      "visibilitychange",
      onVisibilityChange,
    );

    return () => {
      alive = false;
      controller.abort();
      window.clearInterval(interval);

      document.removeEventListener(
        "visibilitychange",
        onVisibilityChange,
      );
    };
  }, []);

  const statusText = snapshot
    ? statusLabels[snapshot.status]
    : message;

  const active = snapshot?.running === true;

  const labelBackground = active
    ? "#dcfce7"
    : "#e5eaf2";

  const labelColor = active
    ? "#166534"
    : "#34445b";

  const connected = snapshot?.connected === true;

  return (
    <section
      aria-label="Supervisor autonomo del mundo"
      style={{
        marginBottom: 14,
        padding: 14,
        border: "1px solid #d5e2f0",
        borderRadius: 14,
        background: "#ffffff",
        color: "#25364d",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        <div>
          <strong
            style={{ fontSize: 15 }}
          >
            Supervisor autonomo
          </strong>

          <p
            style={{
              margin: "5px 0 0",
              fontSize: 12,
              color: "#62748b",
            }}
          >
            Estado real del backend conectado
          </p>
        </div>

        <span
          aria-live="polite"
          style={{
            padding: "7px 11px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 700,
            color: labelColor,
            background: labelBackground,
          }}
        >
          {statusText}
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(125px, 1fr))",
          gap: 10,
        }}
      >
        <div
          style={{
            borderRadius: 11,
            padding: 12,
            background: "#edf6ff",
          }}
        >
          <div
            style={{
              fontSize: 12,
              color: "#50657e",
            }}
          >
            Rondas completadas
          </div>

          <strong
            style={{
              display: "block",
              marginTop: 6,
              fontSize: 23,
            }}
          >
            {connected
              ? snapshot.rounds_executed
              : "—"}
          </strong>
        </div>

        <div
          style={{
            borderRadius: 11,
            padding: 12,
            background: "#fff3ee",
          }}
        >
          <div
            style={{
              fontSize: 12,
              color: "#725b54",
            }}
          >
            Rondas fallidas
          </div>

          <strong
            style={{
              display: "block",
              marginTop: 6,
              fontSize: 23,
            }}
          >
            {connected
              ? snapshot.rounds_failed
              : "—"}
          </strong>
        </div>
      </div>

      <div
        style={{
          marginTop: 12,
          fontSize: 12,
          lineHeight: 1.6,
          overflowWrap: "anywhere",
        }}
      >
        <strong>Ultima ronda:</strong>{" "}
        {connected
          ? snapshot.last_round_id ??
            "Todavia no hay rondas."
          : "Sin datos del controlador."}
      </div>

      <p
        style={{
          margin: "10px 0 0",
          color: "#687b91",
          fontSize: 11,
        }}
      >
        Actualizacion cada 20 segundos.
        El estado pertenece al proceso actual
        del servidor.
        Este panel no ejecuta agentes ni pagos.
      </p>

      {snapshot?.external_ai_active === true && (
        <p style={{ color: "#9a3412" }}>
          El servidor informa uso de IA externa.
        </p>
      )}

      {snapshot?.real_payments_active === true && (
        <p style={{ color: "#9a3412" }}>
          El servidor informa pagos reales activos.
        </p>
      )}
    </section>
  );
}
