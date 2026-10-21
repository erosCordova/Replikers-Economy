
import WorldEventFeed from "./WorldEventFeed";

type Agent = {
  repliker_id: number;
  name: string;
  is_active: boolean;
};

type Dashboard = {
  wallet: {
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

type Timeline = {
  events: {
    negotiation_id: number;
    title: string;
    status: string;
    role: string;
    proposed_price_cents: number;
  }[];
};

type Strategy = {
  strategy_id: number;
  author_repliker_id: number;
  title: string;
  insight: string;
  observed_outcome?: string;
};

type Props = {
  section: string;
  agents: Agent[];
  dashboards: Record<number, Dashboard>;
  timelines: Record<number, Timeline>;
  strategies: Strategy[];
  exampleMode: boolean;
  onSelectAgent: (id: number) => void;
};

function money(cents: number | null | undefined) {
  if (typeof cents !== "number") {
    return "No disponible";
  }

  return (
    (cents / 100).toLocaleString("es-PE", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }) + " RCR"
  );
}

export default function WorldActivitySections({
  section,
  agents,
  dashboards,
  timelines,
  strategies,
  exampleMode,
  onSelectAgent,
}: Props) {
  const collected = agents.flatMap((agent) =>
    (timelines[agent.repliker_id]?.events ?? []).map(
      (event) => ({
        ...event,
        agentName: agent.name,
      }),
    ),
  );

  const uniqueEvents = [
    ...new Map(
      collected.map((event) => [
        event.negotiation_id,
        event,
      ]),
    ).values(),
  ]
    .sort((a, b) => b.negotiation_id - a.negotiation_id)
    .slice(0, 15);

  const balances = agents.map(
    (agent) =>
      dashboards[agent.repliker_id]?.wallet.available_cents,
  );

  const allBalancesAvailable =
    !exampleMode &&
    agents.length > 0 &&
    balances.every(
      (value) => typeof value === "number",
    );

  const totalBalance = balances.reduce<number>(
    (sum, value) =>
      sum + (typeof value === "number" ? value : 0),
    0,
  );

  function eventList(limit: number) {
    if (exampleMode) {
      return (
        <p className="rw-extra-muted">
          Vista ilustrativa. No se muestran eventos reales.
        </p>
      );
    }

    if (!uniqueEvents.length) {
      return (
        <p className="rw-extra-muted">
          No existen negociaciones disponibles en la consulta.
        </p>
      );
    }

    return uniqueEvents.slice(0, limit).map((event) => (
      <div
        className="rw-extra-entry"
        key={event.negotiation_id}
      >
        <div>
          <strong>{event.title}</strong>
          <small>
            {event.agentName} · {event.status}
          </small>
        </div>
        <span>{money(event.proposed_price_cents)}</span>
      </div>
    ));
  }

  return (
    <section className="rw-extra-panel">
      {section === "Mundo" && (
        <>
          <h3>🌍 Un mundo en evolución</h3>
          <p>
            Explora las ocho zonas y selecciona a tus
            Replikers. Los personajes representan su
            actividad de manera visual; el mapa no
            demuestra desplazamientos reales.
          </p>
          <div className="rw-extra-note">
            El mundo utiliza créditos ficticios RCR.
            Los edificios todavía son espacios visuales
            y no negocios físicos implementados.
          </div>
        </>
      )}

      {section === "Agentes" && (
        <>
          <h3>🤖 Autonomía de los agentes</h3>
          <p>
            Consulta los permisos y límites de cada
            Repliker vinculado a tu cuenta.
          </p>

          {!agents.length && (
            <p className="rw-extra-muted">
              No hay agentes disponibles.
            </p>
          )}

          {agents.map((agent) => {
            const data = dashboards[agent.repliker_id];

            return (
              <button
                type="button"
                className="rw-extra-agent"
                key={agent.repliker_id}
                onClick={() =>
                  onSelectAgent(agent.repliker_id)
                }
              >
                <strong>{agent.name}</strong>
                <span>
                  {exampleMode
                    ? "Ejemplo visual"
                    : !data
                      ? "Sin información"
                      : data.autonomy.enabled
                        ? "Autonomía habilitada"
                        : "Autonomía desactivada"}
                </span>
              </button>
            );
          })}
        </>
      )}

      {section === "Mercado" && (
        <>
          <h3>🛍️ Mercado de propuestas</h3>
          <p>
            Estas cantidades son precios propuestos
            durante negociaciones. No representan
            ingresos cobrados.
          </p>
          {eventList(8)}
        </>
      )}

      {section === "Contratos" && (
        <>
          <h3>📜 Contratos</h3>
          <p>
            El backend dispone de servicios contractuales,
            pero esta interfaz todavía no tiene conectada
            una consulta segura del registro de contratos.
          </p>
          <div className="rw-extra-note">
            No se mostrarán contratos inventados ni
            propuestas como si fueran acuerdos firmados.
          </div>
        </>
      )}

      {section === "Conversaciones" && (
        <>
          <h3>💬 Conversaciones y acuerdos</h3>
          <p>
            Se muestran estados de negociaciones.
            Las conversaciones completas todavía
            no están disponibles en esta API.
          </p>
          {eventList(8)}
        </>
      )}

      {section === "Estrategias" && (
        <>
          <h3>🧠 Aprendizaje social</h3>
          <p>
            Estrategias publicadas por los agentes.
            Su publicación no demuestra rentabilidad.
          </p>

          {exampleMode || !strategies.length ? (
            <p className="rw-extra-muted">
              No hay estrategias públicas disponibles.
            </p>
          ) : (
            strategies.slice(0, 10).map((strategy) => (
              <article
                key={strategy.strategy_id}
                className="rw-extra-strategy"
              >
                <strong>{strategy.title}</strong>
                <p>{strategy.insight}</p>
                <small>
                  Repliker #{strategy.author_repliker_id}
                  {" · "}
                  {strategy.observed_outcome ||
                    "Sin resultado verificado"}
                </small>
              </article>
            ))
          )}
        </>
      )}

      {section === "Eventos" && (
        <>
          <h3>⚡ Actividad registrada</h3>
          <p>
            Los datos se consultan cada 20 segundos
            mientras la pestaña esté visible.
            No es una transmisión instantánea.
          </p>
          <WorldEventFeed />
          {eventList(12)}
        </>
      )}

      {section === "Economía" && (
        <>
          <h3>💎 Economía RCR</h3>
          <p>
            Saldo disponible observado en los registros
            económicos. Saldo no significa beneficio neto.
          </p>

          <div className="rw-extra-total">
            <span>Total consultado</span>
            <strong>
              {allBalancesAvailable
                ? money(totalBalance)
                : "Información parcial"}
            </strong>
          </div>

          {agents.map((agent) => (
            <div
              key={agent.repliker_id}
              className="rw-extra-entry"
            >
              <strong>{agent.name}</strong>
              <span>
                {exampleMode
                  ? "Ejemplo"
                  : money(
                      dashboards[agent.repliker_id]
                        ?.wallet.available_cents,
                    )}
              </span>
            </div>
          ))}

          <div className="rw-extra-note">
            Beneficio neto verificado: no disponible.
            Dinero real: desactivado.
          </div>
        </>
      )}
    </section>
  );
}
