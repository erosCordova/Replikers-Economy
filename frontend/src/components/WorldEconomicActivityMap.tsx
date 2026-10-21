
import { useEffect, useRef, useState } from "react";

type EconomicEvent = {
  id: string;
  kind: "negotiation" | "contract" | "settlement";
  seller_id: number;
  buyer_id: number;
  status: string;
  price_cents: number;
  currency: string;
};

type Props = {
  events: EconomicEvent[];
};

const zones = [
  {
    kind: "negotiation",
    title: "Mercado",
    x: 22,
    color: "#2563eb",
    background: "#dbeafe",
  },
  {
    kind: "contract",
    title: "Contratos",
    x: 274,
    color: "#7c3aed",
    background: "#ede9fe",
  },
  {
    kind: "settlement",
    title: "Banco RCR",
    x: 526,
    color: "#059669",
    background: "#d1fae5",
  },
] as const;

export default function WorldEconomicActivityMap({
  events,
}: Props) {
  const previous = useRef<Set<string> | null>(null);
  const [recentIds, setRecentIds] = useState<string[]>([]);

  useEffect(() => {
    if (events.length === 0) {
      previous.current = null;
      setRecentIds([]);
      return;
    }

    const next = new Set(events.map(event => event.id));

    if (previous.current === null) {
      previous.current = next;
      setRecentIds([]);
      return;
    }

    const newEvents = events
      .filter(event => !previous.current?.has(event.id))
      .map(event => event.id);

    previous.current = next;
    setRecentIds(newEvents);
  }, [events]);

  useEffect(() => {
    if (recentIds.length === 0) return;

    const timer = window.setTimeout(() => {
      setRecentIds([]);
    }, 5000);

    return () => window.clearTimeout(timer);
  }, [recentIds]);


  // Solo los eventos posteriores a la primera carga
  // producen animaciones. El historial no se reproduce.
  const movingEvents = events
    .filter((event) => recentIds.includes(event.id))
    .slice(0, 3);

  const transfers = events.filter(
    event => event.kind === "settlement"
  );

  const transferred = transfers.reduce(
    (sum, event) => sum + event.price_cents,
    0
  );

  return (
    <section
      aria-label="Mapa de actividad económica registrada"
      style={{
        marginTop: 14,
        marginBottom: 14,
        padding: 14,
        borderRadius: 16,
        background: "#eff6ff",
        border: "1px solid #bfdbfe",
      }}
    >
      <style>{`
        @keyframes rwEconomicPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: .25; }
        }
        .rw-economic-pulse {
          animation: rwEconomicPulse 0.65s ease-in-out 5;
        }
        @media (prefers-reduced-motion: reduce) {
          .rw-economic-pulse {
            animation: none;
          }
        }
      `}</style>

      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 10,
        flexWrap: "wrap",
      }}>
        <strong style={{ color: "#0f172a", fontSize: 14 }}>
          Actividad económica en la ciudad
        </strong>

        <span
          aria-live="polite"
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: recentIds.length ? "#047857" : "#475569",
          }}
        >
          {recentIds.length
            ? `${recentIds.length} movimientos nuevos`
            : "Historial registrado"}
        </span>
      </div>


      <style>{`
        @media (prefers-reduced-motion: reduce) {
          .rw-economic-travel {
            display: none;
          }
        }
      `}</style>
      <svg
        viewBox="0 0 740 255"
        role="img"
        aria-label="Mercado, contratos y banco RCR con los Replikers participantes"
        style={{ width: "100%", height: "auto" }}
      >
        <path
          d="M 207 76 L 270 76 M 459 76 L 522 76"
          stroke="#64748b"
          strokeWidth="3"
          strokeDasharray="7 6"
          fill="none"
        />

        {zones.map(zone => {
          const records = events.filter(
            event => event.kind === zone.kind
          ).slice(0, 2);

          return (
            <g key={zone.kind}>
              <path
                d={`M ${zone.x} 76 l 94 -45 l 94 45 l -94 45 Z`}
                fill={zone.background}
                stroke={zone.color}
                strokeWidth="2"
              />

              <text
                x={zone.x + 94}
                y={79}
                textAnchor="middle"
                fontSize="17"
                fontWeight="700"
                fill={zone.color}
              >
                {zone.title}
              </text>

              {records.map((event, index) => {
                const from = zone.kind === "settlement"
                  ? event.buyer_id
                  : event.seller_id;

                const to = zone.kind === "settlement"
                  ? event.seller_id
                  : event.buyer_id;

                const y = 137 + index * 34;
                const fresh = recentIds.includes(event.id);

                return (
                  <g key={event.id}>
                    <rect
                      x={zone.x + 4}
                      y={y}
                      width="181"
                      height="28"
                      rx="14"
                      fill="#ffffff"
                      stroke={zone.color}
                      strokeWidth={fresh ? 2.5 : 1}
                    />

                    <text
                      x={zone.x + 94}
                      y={y + 19}
                      textAnchor="middle"
                      fill="#1e293b"
                      fontSize="13"
                      fontWeight="600"
                    >
                      {`R${from} → R${to}`}
                    </text>

                    {fresh && (
                      <circle
                        cx={zone.x + 176}
                        cy={y + 14}
                        r="5"
                        fill={zone.color}
                        className="rw-economic-pulse"
                      />
                    )}
                  </g>
                );
              })}

              {records.length === 0 && (
                <text
                  x={zone.x + 94}
                  y="157"
                  textAnchor="middle"
                  fontSize="12"
                  fill="#64748b"
                >
                  Sin actividad registrada
                </text>
              )}
            </g>
          );
        })}

        {movingEvents.map((event, index) => {
          const route =
            event.kind === "negotiation"
              ? "M 116 228 C 190 195 290 195 368 228"
              : event.kind === "contract"
                ? "M 368 228 C 440 195 540 195 620 228"
                : "M 620 228 C 450 250 280 250 116 228";

          const color =
            event.kind === "negotiation"
              ? "#2563eb"
              : event.kind === "contract"
                ? "#7c3aed"
                : "#059669";

          const actor =
            event.kind === "settlement"
              ? event.buyer_id
              : event.seller_id;

          const recipient =
            event.kind === "settlement"
              ? event.seller_id
              : event.buyer_id;

          return (
            <g
              key={`moving-${event.id}`}
              className="rw-economic-travel"
              aria-label={`Movimiento de Repliker ${actor} hacia Repliker ${recipient}`}
            >
              <path
                d={route}
                fill="none"
                stroke={color}
                strokeWidth="2"
                strokeDasharray="5 5"
                opacity="0.8"
              />

              <g>
                <circle
                  r="16"
                  fill="#ffffff"
                  stroke={color}
                  strokeWidth="3"
                />

                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize="11"
                  fontWeight="700"
                  fill={color}
                >
                  {`R${actor}`}
                </text>

                <animateMotion
                  path={route}
                  dur={`${3 + index * 0.4}s`}
                  repeatCount="1"
                  fill="freeze"
                />
              </g>
            </g>
          );
        })}

      </svg>

      <div style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 10,
        justifyContent: "space-between",
        fontSize: 12,
        color: "#334155",
      }}>
        <span>
          Negociaciones:{" "}
          <strong>
            {events.filter(e => e.kind === "negotiation").length}
          </strong>
        </span>

        <span>
          Contratos:{" "}
          <strong>
            {events.filter(e => e.kind === "contract").length}
          </strong>
        </span>

        <span>
          Transferencias:{" "}
          <strong>{transfers.length}</strong>
        </span>

        <span>
          RCR transferidos:{" "}
          <strong>
            {(transferred / 100).toLocaleString("es-PE", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </strong>
        </span>
      </div>

      <p style={{
        fontSize: 11,
        margin: "10px 0 0",
        color: "#64748b",
      }}>
        Los totales corresponden a los movimientos visibles
        en la consulta, no al saldo total de la economía.
        La actividad se actualiza con los datos de la API.
      </p>
    </section>
  );
}
