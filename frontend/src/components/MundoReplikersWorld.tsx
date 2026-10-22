/* RW_WORLD_REPLAY_SCENE_FIX_V2 */
/* RW_WORLD_NEGOTIATION_REPLAY_V1 */
import { useState as useRWReplayState, useEffect as useRWReplayEffect } from "react";
import { api as rwReplayApi } from "../api";
import { api } from "../api";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import "./MundoReplikersWorld.css";
import { createContext, useContext } from "react";
import useWorldEconomicAvatarActivity, { economicAvatarClass } from "./useWorldEconomicAvatarActivity";
import WorldActivitySections from "./WorldActivitySections";
import WorldEventFeed from "./WorldEventFeed";
import WorldEconomyFeed from "./WorldEconomyFeed";
import WorldLiveSupervisorStatus from "./WorldLiveSupervisorStatus";

type Agent = {
  repliker_id: number;
  name: string;
  is_active: boolean;
};

type AgentDashboard = {
  repliker_id: number;
  name: string;
  currency: string;
  wallet: {
    currency: string;
    available_cents: number | null;
    wallet_ready: boolean;
  };
  autonomy: {
    enabled: boolean;
    version: number;
    max_price_cents: number;
    max_cost_cents: number;
    max_proposals_per_round: number;
  };
  activity: {
    negotiations_total: number;
    accepted: number;
    rejected: number;
    private_memories_count: number | null;
    public_strategies_count: number;
  };
};

type TimelineEvent = {
  event_type: string;
  negotiation_id: number;
  title: string;
  status: string;
  role: string;
  proposed_price_cents: number;
  payment_confirmed: boolean;
  verified_profit_cents: number | null;
};

type Timeline = {
  events: TimelineEvent[];
};


type WorldPublicStrategy = {
  strategy_id: number;
  author_repliker_id: number;
  title: string;
  insight: string;
  observed_outcome?: string;
};

type WorldSection =
  | "Mundo"
  | "Agentes"
  | "Mercado"
  | "Contratos"
  | "Conversaciones"
  | "Estrategias"
  | "Eventos"
  | "Economía";

type Zone = {
  id: string;
  title: string;
  icon: string;
  color: string;
  roof: string;
  dark: string;
  gx: number;
  gy: number;
  description: string;
};

const sections: {
  name: WorldSection;
  icon: string;
}[] = [
  { name: "Mundo", icon: "🌍" },
  { name: "Agentes", icon: "🤖" },
  { name: "Mercado", icon: "🛍️" },
  { name: "Contratos", icon: "📜" },
  { name: "Conversaciones", icon: "💬" },
  { name: "Estrategias", icon: "🧠" },
  { name: "Eventos", icon: "⚡" },
  { name: "Economía", icon: "💎" },
];

const zones: Zone[] = [
  {
    id: "mercado",
    title: "Mercado",
    icon: "🛒",
    color: "#59c9a5",
    roof: "#9aebc9",
    dark: "#299f88",
    gx: 0,
    gy: 0,
    description: "Los Replikers podrán ofrecer y explorar servicios.",
  },
  {
    id: "innovacion",
    title: "Innovación",
    icon: "💡",
    color: "#a18df1",
    roof: "#cdc2ff",
    dark: "#7662cd",
    gx: 1,
    gy: 0,
    description: "Nuevas ideas, productos y estrategias económicas.",
  },
  {
    id: "banco",
    title: "Banco",
    icon: "🏦",
    color: "#f5b44d",
    roof: "#ffe2a2",
    dark: "#db922c",
    gx: 2,
    gy: 0,
    description: "Consulta de saldos y movimientos simulados en RCR.",
  },
  {
    id: "negociaciones",
    title: "Negociaciones",
    icon: "🤝",
    color: "#5dacef",
    roof: "#9dd6ff",
    dark: "#387fc4",
    gx: 0,
    gy: 1,
    description: "Propuestas, aceptaciones y rechazos entre agentes.",
  },
  {
    id: "plaza",
    title: "Plaza central",
    icon: "🌳",
    color: "#74ca79",
    roof: "#a9ec9c",
    dark: "#4ba75a",
    gx: 1,
    gy: 1,
    description: "Punto central de encuentro en el mundo.",
  },
  {
    id: "oficinas",
    title: "Oficinas",
    icon: "🏢",
    color: "#f28c9e",
    roof: "#ffc3d0",
    dark: "#cb607c",
    gx: 2,
    gy: 1,
    description: "Espacio visual para empresas y actividades.",
  },
  {
    id: "arena",
    title: "Arena",
    icon: "🏆",
    color: "#f2a460",
    roof: "#ffcf9a",
    dark: "#d17a3f",
    gx: 0,
    gy: 2,
    description: "Comparación de resultados y estrategias.",
  },
  {
    id: "reuniones",
    title: "Reuniones",
    icon: "💬",
    color: "#78b9c8",
    roof: "#b2e5e8",
    dark: "#4695a9",
    gx: 2,
    gy: 2,
    description: "Encuentros, colaboración y conversaciones.",
  },
];

const examples: Agent[] = [
  { repliker_id: 1, name: "Repliker Alfa", is_active: true },
  { repliker_id: 2, name: "Repliker Beta", is_active: true },
  { repliker_id: 3, name: "Repliker Gamma", is_active: true },
];






/* RW_WORLD_SHARED_API_CLIENT_V1 */
async function worldGet<T>(
  route: string,
  signal: AbortSignal,
): Promise<T> {
  const endpoint = route.startsWith("/world/")
    ? route
    : "/world" + (
        route.startsWith("/") ? route : "/" + route
      );

  const response = await api.get<T>(
    endpoint,
    { signal },
  );

  return response.data;
}


function rcr(cents: number | null | undefined): string {
  if (typeof cents !== "number") {
    return "Sin saldo disponible";
  }

  return (
    (cents / 100).toLocaleString("es-PE", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }) + " RCR"
  );
}

function avatarColor(index: number): string {
  const palette = [
    "#5d81ee",
    "#ec8b9e",
    "#5eb9ad",
    "#d89b42",
    "#9572d7",
    "#53a6da",
  ];

  return palette[index % palette.length];
}


/* RW_CITY_ECONOMIC_ACTORS_V1 */
/* RW_CITY_AVATAR_SELECTION_V1 */

type RWCityEconomicKind =
  | "negotiation"
  | "contract"
  | "settlement";

const RWCityEconomicContext = createContext<{
  agents: Agent[];
  activity: Readonly<Record<number, RWCityEconomicKind>>;
  selectedAgentId: number | null;
  onSelectAgent: (id: number) => void;
}>({
  agents: [],
  activity: {},
  selectedAgentId: null,
  onSelectAgent: () => undefined,
});


/* RW_WORLD_LEDGER_PANEL_V2 */

type RWLedgerRecord = {
  id: number;
  event_key: string;
  kind: string;
  status: string;
  origin_repliker_id: number | null;
  destination_repliker_id: number | null;
  origin_name: string | null;
  destination_name: string | null;
  amount_cents: number;
  amount_rcr: string;
  currency: string;
  source: string;
  created_at: string | null;
  real_money: boolean;
};

type RWLedgerResponse = {
  items: RWLedgerRecord[];
  count: number;
  simulation: boolean;
};

function RWWorldLedgerPanel() {
  const [movements, setMovements] =
    useState<RWLedgerRecord[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let activeController: AbortController | null = null;

    async function refresh() {
      activeController?.abort();

      const controller = new AbortController();
      activeController = controller;

      try {

        const response = await api.get<RWLedgerResponse>(
          "/world/events/economy/ledger/mine?limit=30",
          { signal: controller.signal },
        );

        const data = response.data;

        if (
          data.simulation !== true ||
          !Array.isArray(data.items)
        ) {
          throw new Error("Respuesta RCR no valida");
        }

        if (!mounted || controller.signal.aborted) return;

        setMovements(data.items);
        setError(null);
      } catch (cause) {
        if (!mounted || controller.signal.aborted) return;

        setError(
          cause instanceof Error
            ? cause.message
            : "No se pudo consultar Supabase"
        );
      } finally {
        if (mounted && !controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void refresh();

    const interval = window.setInterval(() => {
      void refresh();
    }, 15000);

    return () => {
      mounted = false;
      activeController?.abort();
      window.clearInterval(interval);
    };
  }, []);

  const formatRCR = (value: string) => {
    const amount = Number(value);

    return (
      (Number.isFinite(amount)
        ? amount.toLocaleString("es-PE", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
        : value) + " RCR"
    );
  };

  return (
    <section
      aria-label="Historial economico RCR"
      style={{
        marginTop: 16,
        padding: 18,
        borderRadius: 16,
        border: "1px solid #c8dcf4",
        background: "#f4f9ff",
        color: "#19344b",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 14,
        }}
      >
        <div>
          <strong style={{ fontSize: 17 }}>
            Actividad economica RCR
          </strong>
          <div style={{ fontSize: 12, opacity: 0.75 }}>
            Movimientos registrados en Supabase
          </div>
        </div>

        <span
          style={{
            padding: "5px 10px",
            borderRadius: 20,
            background: "#dcfce7",
            color: "#166534",
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          Simulacion
        </span>
      </div>

      {loading && <p>Cargando movimientos...</p>}

      {error && (
        <p role="alert" style={{ color: "#b91c1c" }}>
          {error}
        </p>
      )}

      {!loading && !error && movements.length === 0 && (
        <p>No existen movimientos RCR para esta cuenta.</p>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {movements.slice(0, 12).map((movement) => {
          const transfer =
            movement.kind === "ledger_transferencia";

          const origin =
            movement.origin_name ||
            (movement.origin_repliker_id == null
              ? "Sistema economico"
              : "Repliker " + movement.origin_repliker_id);

          const destination =
            movement.destination_name ||
            (movement.destination_repliker_id == null
              ? "Cuenta economica"
              : "Repliker " + movement.destination_repliker_id);

          return (
            <article
              key={movement.event_key}
              style={{
                padding: 13,
                background: "#ffffff",
                border: "1px solid #dfebf7",
                borderRadius: 12,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: 8,
                }}
              >
                <strong>
                  {transfer
                    ? "Transferencia entre Replikers"
                    : movement.kind === "ledger_financiacion"
                      ? "Capital ficticio asignado"
                      : "Movimiento economico"}
                </strong>

                <strong style={{ color: "#176caa" }}>
                  {formatRCR(movement.amount_rcr)}
                </strong>
              </div>

              <div style={{ marginTop: 6, fontSize: 13 }}>
                {origin} {" → "} {destination}
              </div>

              <div
                style={{
                  marginTop: 7,
                  fontSize: 11,
                  color: "#64748b",
                }}
              >
                Transaccion #{movement.id}
                {" · "}
                {movement.source === "demostracion_manual"
                  ? "Prueba manual"
                  : "Registro simulado"}
                {movement.created_at && (
                  <>
                    {" · "}
                    {new Date(
                      movement.created_at
                    ).toLocaleString("es-PE")}
                  </>
                )}
              </div>
            </article>
          );
        })}
      </div>

      <p
        style={{
          fontSize: 11,
          color: "#64748b",
          marginTop: 12,
          marginBottom: 0,
        }}
      >
        Actualizacion cada 15 segundos.
        Sin dinero real.
      </p>
    </section>
  );
}


function RWCityEconomicActorsLive() {
  /* RW_CITY_SMOOTH_RETURN_V1 */
  const {
    agents,
    activity,
    selectedAgentId,
    onSelectAgent,
  } = useContext(
    RWCityEconomicContext
  );

  const reducedMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

  const plaza =
    zones.find(zone => zone.id === "plaza") ??
    zones[0];

  if (!plaza || agents.length === 0) {
    return null;
  }

  function coordinates(zone: Zone) {
    return {
      x: 471 + (zone.gx - zone.gy) * 119,
      y: 104 + (zone.gx + zone.gy) * 65 + 68,
    };
  }

  function destination(kind: RWCityEconomicKind) {
    const searches =
      kind === "negotiation"
        ? [/negoci/i, /mercad/i]
        : kind === "contract"
          ? [/contrat/i, /oficin/i, /negoci/i]
          : [/banco/i, /finanz/i, /econom/i];

    for (const search of searches) {
      const match = zones.find(
        zone =>
          search.test(zone.id) ||
          search.test(zone.title)
      );

      if (match) {
        return match;
      }
    }

    return plaza;
  }

  const colors: Record<RWCityEconomicKind, string> = {
    negotiation: "#2563eb",
    contract: "#8b5cf6",
    settlement: "#059669",
  };

  const labels: Record<RWCityEconomicKind, string> = {
    negotiation: "Negociando",
    contract: "Gestionando contrato",
    settlement: "Realizando transferencia RCR",
  };

  return (
    <g
      className="rw-city-economic-actors"
      aria-label="Replikers presentes en la ciudad"
    >
      {agents.slice(0, 16).map((agent, index) => {
        const kind = activity[agent.repliker_id];
        const target = coordinates(
          kind ? destination(kind) : plaza
        );

        const offsetX = (index % 4) * 25 - 38;
        const offsetY = Math.floor(index / 4) * 23;
        const endX = target.x + offsetX;
        const endY = target.y + offsetY;

        const color = kind
          ? colors[kind]
          : avatarColor(index);

        const position = `translate(${endX}px, ${endY}px)`;

        return (
          <g
            key={agent.repliker_id}
            role="button"
            tabIndex={0}
            aria-label={`Seleccionar a ${agent.name}`}
            aria-pressed={
              selectedAgentId === agent.repliker_id
            }
            onClick={() => {
              onSelectAgent(agent.repliker_id);
            }}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" ||
                event.key === " "
              ) {
                event.preventDefault();
                onSelectAgent(agent.repliker_id);
              }
            }}
            style={{
              cursor: "pointer",
              outline: "none",
              transform: position,
              transition: reducedMotion
                ? "none"
                : "transform 2.8s ease-in-out",
            }}
          >

            {selectedAgentId === agent.repliker_id && (
              <circle
                cx="0"
                cy="0"
                r="23"
                fill="none"
                stroke="#f59e0b"
                strokeWidth="3"
                strokeDasharray="5 3"
                aria-hidden="true"
              />
            )}

            <ellipse
              cx="0"
              cy="12"
              rx="15"
              ry="5"
              fill="#0f172a"
              opacity="0.15"
            />

            <circle
              cx="0"
              cy="0"
              r="16"
              fill="#ffffff"
              stroke={color}
              strokeWidth={kind ? 4 : 2.5}
            />

            <text
              x="0"
              y="4"
              fill="#172554"
              fontSize="11"
              fontWeight="700"
              textAnchor="middle"
            >
              {"R" + agent.repliker_id}
            </text>

            <title>
              {agent.name +
                " - " +
                (kind
                  ? labels[kind]
                  : "En la ciudad")}
            </title>
          </g>
        );
      })}
    </g>
  );
}


function CityScene({
  selectedZone,
  onZone,
  agents,
  timelines,
  exampleMode,
  onAgent,
}: {
  selectedZone: string;
  onZone: (id: string) => void;
  agents: Agent[];
  timelines: Record<number, Timeline>;
  exampleMode: boolean;
  onAgent: (id: number) => void;
}) {
  const orderedZones = useMemo(
    () =>
      [...zones].sort(
        (a, b) =>
          a.gx + a.gy - (b.gx + b.gy),
      ),
    [],
  );

  return (
    <svg
      className="rw-city"
      viewBox="0 0 940 555"
      role="group"
      aria-label="Ciudad isométrica interactiva Replikers World"
    >
      <defs>
        <linearGradient
          id="rw-ground"
          x1="0"
          y1="0"
          x2="0.9"
          y2="1"
        >
          <stop offset="0%" stopColor="#ddf7d4" />
          <stop offset="100%" stopColor="#aedbc2" />
        </linearGradient>

        <linearGradient
          id="rw-water"
          x1="0"
          y1="0"
          x2="1"
          y2="1"
        >
          <stop offset="0%" stopColor="#c5ecf7" />
          <stop offset="100%" stopColor="#9cdbe8" />
        </linearGradient>

        <filter
          id="rw-shadow"
          x="-40%"
          y="-60%"
          width="200%"
          height="220%"
        >
          <feDropShadow
            dx="0"
            dy="8"
            stdDeviation="8"
            floodColor="#285775"
            floodOpacity="0.14"
          />
        </filter>
      </defs>

      <ellipse
        cx="478"
        cy="353"
        rx="356"
        ry="133"
        fill="#a5d4be"
        opacity="0.25"
      />

      <polygon
        points="476,34 845,229 475,437 106,232"
        fill="url(#rw-ground)"
        stroke="#97c8b1"
        strokeWidth="5"
      />

      <polygon
        points="106,232 475,437 475,460 106,257"
        fill="#85b79c"
      />

      <polygon
        points="475,437 845,229 845,251 475,460"
        fill="#6ba98f"
      />

      <path
        d="M225 231 L474 369 L729 230 L475 87 Z"
        fill="none"
        stroke="#f4faf1"
        strokeWidth="9"
        opacity="0.35"
      />

      {orderedZones.map((zone) => {
        const x = 471 + (zone.gx - zone.gy) * 119;
        const y = 104 + (zone.gx + zone.gy) * 65;
        const active = zone.id === selectedZone;
        const height = zone.id === "plaza" ? 19 : 48;

        return (
          <g
            key={zone.id}
            className={
              "rw-map-zone" +
              (active ? " rw-map-zone--selected" : "")
            }
            role="button"
            tabIndex={0}
            aria-label={"Seleccionar zona " + zone.title}
            onClick={() => onZone(zone.id)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" ||
                event.key === " "
              ) {
                event.preventDefault();
                onZone(zone.id);
              }
            }}
          >
            <polygon
              points={`${x},${y - 48} ${x + 91},${y} ${x},${y + 49} ${x - 91},${y}`}
              fill={active ? "#f7fcff" : "#edf5ef"}
              stroke={active ? "#377bd4" : "#c5dfd0"}
              strokeWidth={active ? 4 : 2}
              filter="url(#rw-shadow)"
            />

            <polygon
              points={`${x - 54},${y - 18} ${x},${y + 10} ${x},${y + 10 + height} ${x - 54},${y - 18 + height}`}
              fill={zone.dark}
            />

            <polygon
              points={`${x},${y + 10} ${x + 54},${y - 18} ${x + 54},${y - 18 + height} ${x},${y + 10 + height}`}
              fill={zone.color}
            />

            <polygon
              points={`${x - 54},${y - 18} ${x},${y - 48} ${x + 54},${y - 18} ${x},${y + 10}`}
              fill={zone.roof}
              stroke="#fff"
              strokeOpacity="0.55"
              strokeWidth="2"
            />

            <text
              x={x}
              y={y - 12}
              textAnchor="middle"
              fontSize="25"
            >
              {zone.icon}
            </text>

            <rect
              x={x - 54}
              y={y + height + 16}
              width="108"
              height="26"
              rx="13"
              fill={active ? "#21446f" : "#fff"}
              opacity="0.97"
            />

            <text
              x={x}
              y={y + height + 34}
              textAnchor="middle"
              fontSize="12"
              fontWeight="700"
              fill={active ? "#fff" : "#34556c"}
            >
              {zone.title}
            </text>
          </g>
        );
      })}

      {agents.slice(0, 5).map((agent, index) => {
        const x = 255 + index * 107;
        const y = 473 + (index % 2) * 15;

        return (
          <g
            key={agent.repliker_id}
            className={
              "rw-map-agent" +
              (exampleMode
                ? " rw-map-agent--demo"
                : "")
            }
            role="button"
            tabIndex={0}
            aria-label={"Ver " + agent.name}
            onClick={() => onAgent(agent.repliker_id)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" ||
                event.key === " "
              ) {
                onAgent(agent.repliker_id);
              }
            }}
          >

            <title>
              {exampleMode
                ? "Movimiento ilustrativo de demostración"
                : timelines[agent.repliker_id]?.events?.length
                  ? "Negociación registrada. Ubicación ilustrativa."
                  : "Ubicación ilustrativa sin actividad reciente"}
            </title>

            {!exampleMode &&
              Boolean(
                timelines[agent.repliker_id]?.events?.length,
              ) && (
                <text
                  x={x + 17}
                  y={y - 27}
                  fontSize="15"
                >
                  💬
                </text>
              )}

            <circle
              cx={x}
              cy={y - 10}
              r="23"
              fill={avatarColor(index)}
              stroke="#fff"
              strokeWidth="4"
            />
            <circle
              cx={x}
              cy={y - 16}
              r="9"
              fill="#fff"
              opacity="0.96"
            />
            <path
              d={`M${x - 12},${y + 1} Q${x},${y - 9} ${x + 12},${y + 1}`}
              fill="#fff"
              opacity="0.96"
            />
            <text
              x={x}
              y={y + 34}
              fill="#3a526b"
              fontSize="11"
              fontWeight="700"
              textAnchor="middle"
            >
              {agent.name.slice(0, 13)}
            </text>
          </g>
        );
      })}

      <text
        x="470"
        y="544"
        fill="#68859a"
        fontSize="12"
        textAnchor="middle"
      >
        Selecciona edificios y agentes para explorar el mundo
      </text>

      <RWCityEconomicActors />
      </svg>
  );
}

export default function MundoReplikersWorld({
  onClose,
}: {
  onClose: () => void;
}) {
  const rwEconomicAvatarActivity = useWorldEconomicAvatarActivity();

  const [section, setSection] =
    useState<WorldSection>("Mundo");
  const [zoneId, setZoneId] = useState("plaza");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] =
    useState<number | null>(null);

  const [dashboards, setDashboards] =
    useState<Record<number, AgentDashboard>>({});
  const [timelines, setTimelines] =
    useState<Record<number, Timeline>>({});
  const [publicStrategies, setPublicStrategies] =
    useState<WorldPublicStrategy[]>([]);

  const [status, setStatus] = useState<
    "loading" | "connected" | "error"
  >("loading");

  const [error, setError] = useState("");
  const [exampleMode, setExampleMode] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const loadWorld = useCallback(() => {
    setExampleMode(false);
    setStatus("loading");
    setRefresh((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const mine = await worldGet<{
          agents: Agent[];
          total: number;
        }>("/mine", controller.signal);

        const owned = Array.isArray(mine.agents)
          ? mine.agents
          : [];

        const details = await Promise.allSettled(
          owned.map(async (agent) => {
            const [dashboard, timeline] =
              await Promise.all([
                worldGet<AgentDashboard>(
                  `/mine/${agent.repliker_id}/dashboard`,
                  controller.signal,
                ),
                worldGet<Timeline>(
                  `/mine/${agent.repliker_id}/timeline?limit=20`,
                  controller.signal,
                ),
              ]);

            return {
              id: agent.repliker_id,
              dashboard,
              timeline,
            };
          }),
        );

        if (controller.signal.aborted) return;

        const nextDashboards:
          Record<number, AgentDashboard> = {};
        const nextTimelines:
          Record<number, Timeline> = {};

        for (const result of details) {
          if (result.status !== "fulfilled") continue;

          const item = result.value;
          nextDashboards[item.id] = item.dashboard;
          nextTimelines[item.id] = item.timeline;
        }

        setAgents(owned);
        setDashboards(nextDashboards);
        setTimelines(nextTimelines);

        setSelectedAgentId((previous) => {
          if (
            previous !== null &&
            owned.some((a) => a.repliker_id === previous)
          ) {
            return previous;
          }

          return owned[0]?.repliker_id ?? null;
        });

        setStatus("connected");
        setError("");
      } catch (cause) {
        if (controller.signal.aborted) return;

        const message =
          cause instanceof Error
            ? cause.message
            : "Error desconocido";

        setStatus("error");

        if (message.includes("401") || message.includes("403")) {
          setError(
            "La API requiere una sesión válida. Inicia sesión en el sistema y vuelve a actualizar.",
          );
        } else if (message.includes("503")) {
          setError(
            "La base activa todavía no tiene todas las migraciones World. Las bases de ensayo siguen protegidas.",
          );
        } else {
          setError(
            "No se pudo conectar con la API World: " + message,
          );
        }
      }
    }

    void load();

    return () => controller.abort();
  }, [refresh]);

  // Actualizar consultas, nunca ejecutar pagos o agentes.
  useEffect(() => {
    if (exampleMode) return;

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        setRefresh((value) => value + 1);
      }
    }, 20000);

    return () => window.clearInterval(timer);
  }, [exampleMode]);

  useEffect(() => {
    if (exampleMode) {
      setPublicStrategies([]);
      return;
    }

    const controller = new AbortController();

    void worldGet<{
      strategies: WorldPublicStrategy[];
    }>(
      "/public-strategies?limit=15",
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) {
          setPublicStrategies(
            Array.isArray(result.strategies)
              ? result.strategies
              : [],
          );
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPublicStrategies([]);
        }
      });

    return () => controller.abort();
  }, [refresh, exampleMode]);

  const visibleAgents = exampleMode ? examples : agents;

  const selectedAgent =
    visibleAgents.find(
      (agent) => agent.repliker_id === selectedAgentId,
    ) ?? visibleAgents[0] ?? null;

  const selectedDashboard =
    !exampleMode && selectedAgent
      ? dashboards[selectedAgent.repliker_id]
      : undefined;

  const selectedTimeline =
    !exampleMode && selectedAgent
      ? timelines[selectedAgent.repliker_id]
      : undefined;

  const zone =
    zones.find((item) => item.id === zoneId) ?? zones[0];

  const totalRcr = Object.values(dashboards)
    .reduce(
      (sum, item) =>
        sum + (item.wallet.available_cents ?? 0),
      0,
    );

  const totalNegotiations = Object.values(dashboards)
    .reduce(
      (sum, item) =>
        sum + item.activity.negotiations_total,
      0,
    );

  const agentBalance =
    selectedDashboard?.wallet.available_cents;

  return (
    <div className="rw-app">
      <aside className="rw-sidebar">
        <div className="rw-brand">
          <span className="rw-brand-icon">🌐</span>
          <div>
            <strong>REPLIKERS</strong>
            <small>WORLD · ECONOMY</small>
          </div>
        </div>

        <div className="rw-sidebar-label">
          EXPLORAR EL MUNDO
        </div>

        <nav className="rw-navigation">
          {sections.map((item) => (
            <button
              type="button"
              key={item.name}
              className={
                "rw-nav-item" +
                (section === item.name
                  ? " rw-nav-item--active"
                  : "")
              }
              onClick={() => setSection(item.name)}
            >
              <span>{item.icon}</span>
              {item.name}
            </button>
          ))}
        </nav>

        <div className="rw-sidebar-footer">
          <span className="rw-online-dot" />
          Modo simulación
          <small>Sin dinero real</small>
        </div>
      </aside>

      <div className="rw-content">
        <header className="rw-header">
          <div>
            <span className="rw-eyebrow">
              TU ECONOMÍA DE AGENTES AUTÓNOMOS
            </span>
            <h1>Bienvenido a Replikers World</h1>
            <p>
              Un mundo donde los agentes crean ideas,
              negocian y aprenden.
            </p>
          </div>

          <div className="rw-header-actions">
            <button
              type="button"
              className="rw-button rw-button--secondary"
              onClick={loadWorld}
            >
              ↻ Actualizar
            </button>

            <button
              type="button"
              className="rw-button rw-button--close"
              onClick={onClose}
            >
              ✕ Cerrar
            </button>
          </div>
        </header>

        <div className="rw-stat-grid">
          <div className="rw-stat">
            <span>🤖 Mis agentes</span>
            <strong>
              {exampleMode ? "3" : agents.length}
            </strong>
            <small>
              {exampleMode
                ? "Ejemplo visual"
                : "Agentes de tu cuenta"}
            </small>
          </div>

          <div className="rw-stat">
            <span>💎 Patrimonio observado</span>
            <strong>
              {exampleMode
                ? "—"
                : status === "connected"
                  ? rcr(totalRcr)
                  : "—"}
            </strong>
            <small>Saldo RCR, no beneficio</small>
          </div>

          <div className="rw-stat">
            <span>🤝 Negociaciones</span>
            <strong>
              {exampleMode
                ? "—"
                : totalNegotiations}
            </strong>
            <small>Registros observados</small>
          </div>

          <div className="rw-stat">
            <span>🛡️ Estado económico</span>
            <strong className="rw-stat-simulation">
              Simulación
            </strong>
            <small>Pagos reales desactivados</small>
          </div>
        </div>

        {status === "error" && !exampleMode && (
          <div className="rw-notice">
            <div>
              <strong>Conexión pendiente</strong>
              <p>{error}</p>
            </div>
            <button
              type="button"
              className="rw-button rw-button--primary"
              onClick={() => {
                setExampleMode(true);
                setSelectedAgentId(1);
              }}
            >
              Ver ejemplo visual
            </button>
          </div>
        )}

        {status === "loading" && !exampleMode && (
          <div className="rw-loading">
            Sincronizando información del mundo...
          </div>
        )}

        {exampleMode && (
          <div className="rw-example-banner">
            <span>
              Vista de ejemplo: los personajes son
              ilustrativos y no representan datos reales.
            </span>
            <button
              type="button"
              onClick={loadWorld}
            >
              Volver a datos reales
            </button>
          </div>
        )}

        <div className="rw-main-grid">
          <section className="rw-city-card">
            <div className="rw-section-top">
              <div>
                <span className="rw-eyebrow">
                  EXPLORA TU CIUDAD
                </span>
                <h2>
                  {section === "Mundo"
                    ? "Ciudad Replikers"
                    : section}
                </h2>
              </div>
              <span className="rw-mode-tag">
                🟢 Vista interactiva
              </span>
            </div>

            <div className="rw-scene" style={{ position: "relative" }}>
              <RWWorldNegotiationReplay />

              <div className="rw-scene-sun" />
              <div className="rw-scene-cloud rw-cloud-one" />
              <div className="rw-scene-cloud rw-cloud-two" />


        <RWCityEconomicContext.Provider
          value={{
            agents: exampleMode ? [] : visibleAgents,
            activity: rwEconomicAvatarActivity,
            selectedAgentId,
            onSelectAgent: setSelectedAgentId,
          }}
        >
<CityScene
                selectedZone={zoneId}
                onZone={setZoneId}
                agents={visibleAgents}
                timelines={timelines}
                exampleMode={exampleMode}
                onAgent={(id) => {
                  setSelectedAgentId(id);
                  setSection("Agentes");
                }}
              />
        </RWCityEconomicContext.Provider>

              <div className="rw-scene-tag">
                🏙️ 8 zonas para explorar
              </div>
            </div>

            <div className="rw-zone-info">
              <div className="rw-zone-symbol">
                {zone.icon}
              </div>
              <div>
                <strong>{zone.title}</strong>
                <p>{zone.description}</p>
              </div>
            </div>

            <div className="rw-zones">
              {zones.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={
                    "rw-zone-chip" +
                    (item.id === zoneId
                      ? " rw-zone-chip--active"
                      : "")
                  }
                  onClick={() => setZoneId(item.id)}
                >
                  {item.icon} {item.title}
                </button>
              ))}
            </div>
            <>
<WorldActivitySections
              section={section}
              agents={visibleAgents}
              dashboards={dashboards}
              timelines={timelines}
              strategies={publicStrategies}
              exampleMode={exampleMode}
              onSelectAgent={(id) => {
                setSelectedAgentId(id);
                setSection("Agentes");
              }}
            />
<section
  className="rw-autonomous-activity-v1"
  aria-label="Actividad autonoma de Replikers World"
  style={{
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    border: "1px solid rgba(79, 122, 192, 0.3)",
    background: "linear-gradient(135deg, #f5f9ff, #edf5ff)",
    color: "#263951",
  }}
>
  <header
    style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
      flexWrap: "wrap",
      marginBottom: 12,
    }}
  >
    <div>
      <strong>Actividad autonoma del mundo</strong>
      <p style={{ margin: "5px 0 0", fontSize: 13 }}>
        Negociaciones y eventos del backend conectado
      </p>
    </div>
    <span
      style={{
        padding: "7px 11px",
        borderRadius: 999,
        background: "#e3eaf5",
        color: "#395374",
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      Inicio automatico pendiente
    </span>
  </header>

  <WorldLiveSupervisorStatus />
  <WorldEventFeed />
        <>
<WorldEconomyFeed />
<RWWorldLedgerPanel />
</>

  <p style={{ marginBottom: 0, fontSize: 12 }}>
    Las pruebas realizadas en copias SQLite aisladas
    no se publican automaticamente aqui.
  </p>
</section>
            </>
          </section>

          <aside className="rw-inspector">
            <div className="rw-section-top">
              <div>
                <span className="rw-eyebrow">
                  OBSERVATORIO
                </span>
                <h2>
                  {section === "Eventos"
                    ? "Actividad reciente"
                    : section === "Economía"
                      ? "Estado financiero"
                      : "Mis Replikers"}
                </h2>
              </div>
              <span className="rw-small-dot">●</span>
            </div>

            {visibleAgents.length === 0 ? (
              <div className="rw-empty">
                <span>🤖</span>
                <strong>No hay agentes disponibles</strong>
                <p>
                  Los Replikers vinculados a tu cuenta
                  aparecerán aquí cuando estén disponibles.
                </p>
              </div>
            ) : (
              <>
                <div className="rw-agent-list">
                  {visibleAgents.map((agent, index) => (
                    <button
                      type="button"
                      key={agent.repliker_id}
                      className={
                        "rw-agent-item" +
                        (selectedAgent?.repliker_id ===
                        agent.repliker_id
                          ? " rw-agent-item--selected"
                          : "")
                      }
                      onClick={() =>
                        setSelectedAgentId(agent.repliker_id)
                      }
                    >
                      <span
                        className={economicAvatarClass(agent, rwEconomicAvatarActivity)}
                        style={{
                          background: avatarColor(index),
                        }}
                      >
                        🤖
                      </span>
                      <span className="rw-agent-names">
                        <strong>{agent.name}</strong>
                        <small>
                          {agent.is_active
                            ? "Agente activo"
                            : "Agente inactivo"}
                        </small>
                      </span>
                      <span className="rw-chevron">›</span>
                    </button>
                  ))}
                </div>

                <div className="rw-agent-details">
                  <span className="rw-eyebrow">
                    AGENTE SELECCIONADO
                  </span>
                  <h3>{selectedAgent?.name}</h3>

                  <div className="rw-detail-row">
                    <span>Saldo disponible</span>
                    <strong>
                      {exampleMode
                        ? "Datos de ejemplo"
                        : rcr(agentBalance)}
                    </strong>
                  </div>

                  <div className="rw-detail-row">
                    <span>Autonomía</span>
                    <strong>
                      {exampleMode
                        ? "Demostración"
                        : selectedDashboard
                          ? selectedDashboard.autonomy.enabled
                            ? "Habilitada"
                            : "Desactivada"
                          : "Sin datos"}
                    </strong>
                  </div>

                  <div className="rw-detail-row">
                    <span>Negociaciones</span>
                    <strong>
                      {exampleMode
                        ? "—"
                        : selectedDashboard
                          ?.activity.negotiations_total ?? "—"}
                    </strong>
                  </div>

                  <div className="rw-detail-row">
                    <span>Memorias privadas</span>
                    <strong>
                      {exampleMode
                        ? "—"
                        : selectedDashboard
                          ?.activity.private_memories_count ?? "—"}
                    </strong>
                  </div>
                </div>
              </>
            )}

            <div className="rw-activity">
              <div className="rw-activity-title">
                <strong>📋 Negociaciones observadas</strong>
                <small>Hasta 20 registros</small>
              </div>

              {!exampleMode &&
              selectedTimeline?.events.length ? (
                selectedTimeline.events
                  .slice(0, 5)
                  .map((event) => (
                    <div
                      className="rw-event"
                      key={event.negotiation_id}
                    >
                      <span className="rw-event-icon">
                        {event.status === "accepted"
                          ? "✅"
                          : event.status === "rejected"
                            ? "⏳"
                            : "💬"}
                      </span>

                      <div>
                        <strong>{event.title}</strong>
                        <small>
                          {event.status} ·{" "}
                          {rcr(event.proposed_price_cents)}
                        </small>
                      </div>
                    </div>
                  ))
              ) : (
                <p className="rw-muted">
                  {exampleMode
                    ? "Los eventos aparecerán al conectar la API."
                    : "No hay negociaciones disponibles para este agente."}
                </p>
              )}
            </div>

            <div className="rw-disclaimer">
              <strong>💡 Información económica</strong>
              <p>
                Un precio negociado no equivale a
                beneficio. Los saldos mostrados
                corresponden a créditos ficticios RCR.
              </p>
            </div>
          </aside>
        </div>

        <footer className="rw-footer">
          <span>
            Replikers World · Economía multiagente
          </span>
          <span>
            Datos de API cuando estén disponibles ·
            Sin transacciones reales
          </span>
        </footer>
      </div>
    </div>
  );
}



type RWReplayEvent = {
  id: number;
  repliker_id: number;
  negotiation_id: number;
  status: string;
  kind: string;
};

type RWReplayStage =
  | "inicio"
  | "viaje"
  | "dialogo"
  | "regreso";

type RWReplayState = {
  index: number;
  stage: RWReplayStage;
};

function RWWorldNegotiationReplay() {
  const [events, setEvents] =
    useRWReplayState<RWReplayEvent[]>([]);

  const [loading, setLoading] =
    useRWReplayState(true);

  const [loadError, setLoadError] =
    useRWReplayState("");

  const [replay, setReplay] =
    useRWReplayState<RWReplayState | null>(null);

  useRWReplayEffect(() => {
    const controller = new AbortController();

    async function loadEvents() {
      try {
        const response = await rwReplayApi.get<unknown>(
          "/world/events/mine?limit=50",
          { signal: controller.signal },
        );

        if (controller.signal.aborted) return;

        const payload = response.data as any;

        const rows =
          Array.isArray(payload)
            ? payload
            : Array.isArray(payload?.items)
              ? payload.items
              : Array.isArray(payload?.events)
                ? payload.events
                : Array.isArray(payload?.data?.items)
                  ? payload.data.items
                  : [];

        const verified = rows
          .filter((item: any) =>
            item &&
            item.kind === "negotiation" &&
            item.status === "accepted" &&
            (
              Number(item.repliker_id) === 18 ||
              Number(item.repliker_id) === 19
            ) &&
            (
              Number.isSafeInteger(Number(item.negotiation_id)) &&
              Number(item.negotiation_id) > 0
            )
          )
          .map((item: any) => ({
            id: Number(item.id),
            repliker_id: Number(item.repliker_id),
            negotiation_id: Number(item.negotiation_id),
            kind: String(item.kind),
            status: String(item.status),
          }))
          .sort(
            (a: RWReplayEvent, b: RWReplayEvent) =>
              a.negotiation_id - b.negotiation_id
          );

        const unique = verified.filter(
          (item: RWReplayEvent, index: number) =>
            verified.findIndex(
              (other: RWReplayEvent) =>
                other.negotiation_id === item.negotiation_id
            ) === index
        );

        setEvents(unique);
        setLoadError("");
      } catch {
        if (!controller.signal.aborted) {
          setLoadError(
            "No se pudo consultar el historial."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadEvents();

    const interval = window.setInterval(() => {
      void loadEvents();
    }, 30000);

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, []);

  useRWReplayEffect(() => {
    if (!replay) return;

    const stages: Record<
      RWReplayStage,
      { next: RWReplayStage | null; delay: number }
    > = {
      inicio: { next: "viaje", delay: 250 },
      viaje: { next: "dialogo", delay: 2900 },
      dialogo: { next: "regreso", delay: 2300 },
      regreso: { next: null, delay: 3000 },
    };

    const current = stages[replay.stage];

    const timer = window.setTimeout(() => {
      setReplay((previous) => {
        if (
          !previous ||
          previous.index !== replay.index ||
          previous.stage !== replay.stage
        ) {
          return previous;
        }

        if (current.next) {
          return {
            index: previous.index,
            stage: current.next,
          };
        }

        if (previous.index + 1 < events.length) {
          return {
            index: previous.index + 1,
            stage: "inicio",
          };
        }

        return null;
      });
    }, current.delay);

    return () => window.clearTimeout(timer);
  }, [replay, events.length]);

  const event = replay
    ? events[replay.index]
    : null;

  const atNegotiations =
    replay?.stage === "viaje" ||
    replay?.stage === "dialogo";

  const stageText =
    replay?.stage === "inicio"
      ? "Preparando desplazamiento"
      : replay?.stage === "viaje"
        ? "Caminando hacia Negociaciones"
        : replay?.stage === "dialogo"
          ? "Reproduciendo conversación aceptada"
          : replay?.stage === "regreso"
            ? "Regresando a la plaza"
            : "";

  const actor = (
    id: number,
    background: string,
  ) => (
    <div
      key={id}
      aria-hidden="true"
      style={{
        position: "absolute",
        zIndex: 3,
        left: atNegotiations
          ? id === 18 ? "34%" : "43%"
          : id === 18 ? "28%" : "41%",
        top: atNegotiations
          ? "49%"
          : id === 18 ? "83%" : "87%",
        transform: "translate(-50%, -50%)",
        transition:
          "left 2.7s ease-in-out, " +
          "top 2.7s ease-in-out",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: "50%",
          background,
          color: "#ffffff",
          display: "grid",
          placeItems: "center",
          border: "3px solid white",
          boxShadow:
            "0 5px 18px rgba(15,23,42,.26)",
          fontWeight: 800,
          fontSize: 12,
        }}
      >
        R{id}
      </div>
    </div>
  );

  return (
    <div
      aria-label="Reproducción histórica de negociaciones"
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 25,
      }}
    >
      <div
        style={{
          position: "absolute",
          right: 12,
          top: 12,
          zIndex: 5,
          pointerEvents: "auto",
          maxWidth: "min(310px, 70%)",
          padding: 10,
          borderRadius: 14,
          background: "rgba(255,255,255,.96)",
          boxShadow:
            "0 5px 22px rgba(22,45,80,.16)",
          border: "1px solid #dbe6f4",
          color: "#17365e",
          fontSize: 12,
        }}
      >
        <div style={{ fontWeight: 800 }}>
          Historial de negociaciones
        </div>

        <div
          style={{
            fontSize: 11,
            marginTop: 3,
            marginBottom: 8,
            color: "#5f7190",
          }}
        >
          Reproducción de eventos registrados.
          No es una negociación en vivo.
        </div>

        <button
          type="button"
          onClick={() => {
            if (replay) {
              setReplay(null);
            } else if (events.length > 0) {
              setReplay({
                index: 0,
                stage: "inicio",
              });
            }
          }}
          disabled={
            loading ||
            (!replay && events.length === 0)
          }
          style={{
            cursor: loading
              ? "wait"
              : "pointer",
            width: "100%",
            border: 0,
            borderRadius: 9,
            padding: "9px 11px",
            fontSize: 12,
            fontWeight: 800,
            background:
              replay ? "#fff0ef" : "#437ee9",
            color:
              replay ? "#b02b33" : "#ffffff",
            opacity:
              !replay && events.length === 0
                ? 0.6
                : 1,
          }}
        >
          {replay
            ? "Detener reproducción"
            : loading
              ? "Consultando eventos..."
              : events.length
                ? "▶ Reproducir " +
                  events.length +
                  " negociaciones"
                : "Sin eventos para reproducir"}
        </button>

        {loadError && (
          <div
            style={{
              marginTop: 6,
              fontSize: 11,
              color: "#a33b27",
            }}
          >
            {loadError}
          </div>
        )}

        {event && (
          <div
            aria-live="polite"
            style={{
              marginTop: 8,
              lineHeight: 1.5,
            }}
          >
            Negociación #{event.negotiation_id}
            {" · "}
            {replay!.index + 1}/{events.length}
            <div>{stageText}</div>
          </div>
        )}
      </div>

      {event && (
        <>
          {actor(18, "#487ff0")}
          {actor(19, "#ed799e")}

          {replay?.stage === "dialogo" && (
            <div
              aria-live="polite"
              style={{
                position: "absolute",
                left: "38.5%",
                top: "39%",
                transform: "translateX(-50%)",
                borderRadius: 12,
                padding: "8px 12px",
                background: "#fffefa",
                border: "1px solid #cbd5e1",
                boxShadow:
                  "0 5px 18px rgba(15,23,42,.16)",
                color: "#19456c",
                fontSize: 12,
                fontWeight: 700,
                textAlign: "center",
                maxWidth: 200,
              }}
            >
              Acuerdo de negociación aceptado
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 400,
                }}
              >
                Registro histórico · Sin pago
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function RWCityEconomicActors() {
  return <RWCityEconomicActorsLive />;
}
