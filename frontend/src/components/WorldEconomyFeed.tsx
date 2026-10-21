
import { useEffect, useState } from "react";
import WorldEconomicActivityMap from "./WorldEconomicActivityMap";
import { apiBase, accessToken } from "./WorldEventFeed";

type EconomicEvent = {
  id: string;
  kind: "negotiation" | "contract" | "settlement";
  resource_id: number;
  status: string;
  title: string;
  currency: string;
  price_cents: number;
  seller_id: number;
  buyer_id: number;
  contract_id: number | null;
  transaction_id: number | null;
  created_at: string | null;
};

const labels = {
  negotiation: "Negociación",
  contract: "Contrato",
  settlement: "Transferencia RCR",
};

const colors = {
  negotiation: "#2563eb",
  contract: "#7c3aed",
  settlement: "#059669",
};

function amount(cents: number, currency: string) {
  return `${(cents / 100).toLocaleString("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`;
}

export default function WorldEconomyFeed() {
  const [events, setEvents] = useState<EconomicEvent[]>([]);
  const [message, setMessage] = useState(
    "Consultando movimientos económicos..."
  );

  useEffect(() => {
    const controller = new AbortController();

    async function refresh() {
      if (document.visibilityState !== "visible") {
        return;
      }

      const token = accessToken();

      if (!token) {
        setEvents([]);
        setMessage(
          "Inicia sesión para consultar tu economía."
        );
        return;
      }

      try {
        const response = await fetch(
          apiBase() + "/world/events/economy/mine?limit=30",
          {
            method: "GET",
            credentials: "include",
            headers: {
              Authorization: `Bearer ${token}`,
            },
            cache: "no-store",
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = (await response.json()) as {
          events?: EconomicEvent[];
        };

        if (!controller.signal.aborted) {
          setEvents(
            Array.isArray(data.events) ? data.events : []
          );
          setMessage(
            "Datos registrados en la economía activa."
          );
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          const detail = error instanceof Error
            ? error.message
            : "Error desconocido";

          setMessage(
            "No se pudo consultar la economía: " + detail
          );
        }
      }
    }

    void refresh();

    const interval = window.setInterval(() => {
      void refresh();
    }, 15000);

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, []);

  return (
    <section
      aria-label="Economía de Replikers World"
      style={{
        padding: 16,
        borderRadius: 18,
        background: "#f8fafc",
        border: "1px solid #cbd5e1",
        color: "#0f172a",
        marginTop: 14,
      }}
    >
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 12,
        flexWrap: "wrap",
      }}>
        <div>
          <strong style={{ fontSize: 17 }}>
            Economía de Replikers World
          </strong>
          <p style={{
            margin: "5px 0",
            fontSize: 12,
            color: "#475569",
          }}>
            Negociaciones, contratos y créditos RCR
          </p>
        </div>

        <span style={{
          background: "#dbeafe",
          color: "#1e40af",
          borderRadius: 16,
          padding: "5px 10px",
          fontSize: 12,
        }}>
          {events.length} movimientos
        </span>
      </div>

      <WorldEconomicActivityMap events={events} />

      <p role="status" style={{
        fontSize: 12,
        color: "#64748b",
      }}>
        {message}
      </p>

      {events.length === 0 && (
        <p style={{ fontSize: 13 }}>
          No hay movimientos económicos para mostrar.
        </p>
      )}

      <div style={{
        display: "grid",
        gap: 9,
        maxHeight: 380,
        overflowY: "auto",
      }}>
        {events.map(event => (
          <article key={event.id} style={{
            background: "white",
            padding: 12,
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            borderLeft: `4px solid ${colors[event.kind]}`,
          }}>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 8,
            }}>
              <strong style={{
                color: colors[event.kind],
              }}>
                {labels[event.kind]}
              </strong>

              <strong>
                {amount(
                  event.price_cents,
                  event.currency
                )}
              </strong>
            </div>

            <p style={{
              margin: "6px 0",
              fontSize: 13,
            }}>
              {event.title}
            </p>

            <div style={{
              color: "#475569",
              fontSize: 12,
            }}>
              {event.kind === "settlement"
                ? `Pago: Repliker ${event.buyer_id} → Repliker ${event.seller_id}`
                : `Acuerdo: Repliker ${event.seller_id} → Repliker ${event.buyer_id}`}
            </div>

            <div style={{
              fontSize: 12,
              marginTop: 5,
              color: "#64748b",
            }}>
              Estado: {event.status}
            </div>

            {event.transaction_id !== null && (
              <div style={{
                fontSize: 12,
                color: "#047857",
                marginTop: 5,
              }}>
                Transacción RCR #{event.transaction_id}
              </div>
            )}

            {event.created_at && (
              <div style={{
                fontSize: 11,
                color: "#94a3b8",
                marginTop: 6,
              }}>
                {new Date(
                  event.created_at
                ).toLocaleString("es-PE")}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
