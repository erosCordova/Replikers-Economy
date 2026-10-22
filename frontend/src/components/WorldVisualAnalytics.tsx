type Agent = {
  repliker_id: number;
  name: string;
  is_active: boolean;
};

type Dashboard = {
  wallet: {
    available_cents: number | null;
  };
  autonomy: {
    enabled: boolean;
  };
  activity: {
    negotiations_total: number;
    accepted: number;
    rejected: number;
    private_memories_count: number | null;
  };
};

type Props = {
  section: string;
  agents: Agent[];
  dashboards: Record<number, Dashboard>;
  exampleMode: boolean;
  onSelectAgent: (id: number) => void;
};

function currency(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Sin datos";
  }

  return (value / 100).toLocaleString("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) + " RCR";
}

export default function WorldVisualAnalytics({
  section,
  agents,
  dashboards,
  exampleMode,
  onSelectAgent,
}: Props) {
  const actual = !exampleMode;

  const completeBalances =
    actual &&
    agents.length > 0 &&
    agents.every((agent) =>
      typeof dashboards[agent.repliker_id]
        ?.wallet.available_cents === "number"
    );

  const totalCents = agents.reduce((sum, agent) => {
    const value = dashboards[agent.repliker_id]
      ?.wallet.available_cents;
    return sum + (typeof value === "number" ? value : 0);
  }, 0);

  const maximum = Math.max(
    1,
    ...agents.map((agent) => {
      const value = dashboards[agent.repliker_id]
        ?.wallet.available_cents;
      return typeof value === "number"
        ? Math.max(0, value) : 0;
    }),
  );

  const accepted = agents.reduce((sum, agent) =>
    sum + (dashboards[agent.repliker_id]
      ?.activity.accepted ?? 0), 0
  );

  const observed = agents.reduce((sum, agent) =>
    sum + (dashboards[agent.repliker_id]
      ?.activity.negotiations_total ?? 0), 0
  );

  const memories = agents.reduce((sum, agent) =>
    sum + (dashboards[agent.repliker_id]
      ?.activity.private_memories_count ?? 0), 0
  );

  if (section === "Agentes") {
    return (
      <section className="rw-final-analytics">
        <header className="rw-final-analytics-head">
          <div>
            <span className="rw-eyebrow">DIRECTORIO AUTÓNOMO</span>
            <h3>Mis Replikers</h3>
            <p>Estado y capacidad económica por agente.</p>
          </div>
          <span className="rw-final-counter">{agents.length} agentes</span>
        </header>

        <div className="rw-final-agent-grid">
          {agents.map((agent, index) => {
            const data = dashboards[agent.repliker_id];

            return (
              <button
                type="button"
                className="rw-final-agent-card"
                key={agent.repliker_id}
                onClick={() => onSelectAgent(agent.repliker_id)}
              >
                <div className="rw-final-agent-avatar">
                  <span>{index % 2 === 0 ? "🤖" : "🧠"}</span>
                </div>

                <strong>{agent.name}</strong>

                <span className="rw-final-agent-status">
                  <i className={agent.is_active ? "on" : "off"} />
                  {agent.is_active ? "Activo" : "Inactivo"}
                </span>

                <div className="rw-final-card-divider" />

                <div className="rw-final-pair">
                  <span>Patrimonio</span>
                  <b>{actual ? currency(data?.wallet.available_cents) : "Ejemplo"}</b>
                </div>
                <div className="rw-final-pair">
                  <span>Autonomía</span>
                  <b>{!actual ? "Ejemplo" : !data ? "Sin datos" :
                    data.autonomy.enabled ? "Habilitada" : "Desactivada"}</b>
                </div>
                <div className="rw-final-pair">
                  <span>Negociaciones</span>
                  <b>{actual ? data?.activity.negotiations_total ?? "—" : "—"}</b>
                </div>
              </button>
            );
          })}
          {!agents.length && <p>No hay Replikers disponibles.</p>}
        </div>
      </section>
    );
  }

  if (section === "Economía") {
    return (
      <section className="rw-final-analytics">
        <header className="rw-final-analytics-head">
          <div>
            <span className="rw-eyebrow">OBSERVATORIO ECONÓMICO</span>
            <h3>Distribución del patrimonio</h3>
            <p>Créditos simulados. Los saldos no son beneficios obtenidos.</p>
          </div>
          <span className="rw-final-counter">RCR · Simulación</span>
        </header>

        <div className="rw-final-total">
          <span>Saldo total consultado</span>
          <strong>{completeBalances ? currency(totalCents) : "Datos parciales"}</strong>
          <small>Sin transferencias reales habilitadas</small>
        </div>

        <div className="rw-final-chart">
          {agents.map((agent, index) => {
            const value = actual
              ? dashboards[agent.repliker_id]?.wallet.available_cents
              : null;
            const amount = typeof value === "number"
              ? Math.max(0, value) : 0;

            return (
              <div className="rw-final-chart-row" key={agent.repliker_id}>
                <div className="rw-final-chart-label">
                  <span>{agent.name}</span>
                  <strong>{currency(value)}</strong>
                </div>
                <div className="rw-final-track">
                  <div
                    className={index % 2 ? "rw-final-fill purple" : "rw-final-fill"}
                    style={{ width: `${amount / maximum * 100}%` }}
                  />
                </div>
              </div>
            );
          })}
          {!agents.length && <p>No existen saldos disponibles.</p>}
        </div>

        <p className="rw-final-legal">
          Gráfico calculado con los saldos de los agentes consultados.
          No representa rentabilidad ni ingresos confirmados.
        </p>
      </section>
    );
  }

  if (section === "Mundo") {
    return (
      <section className="rw-final-overview">
        <div>
          <small>REPLIKERS CONECTADOS</small>
          <strong>{agents.length}</strong>
        </div>
        <div>
          <small>NEGOCIACIONES POR AGENTE</small>
          <strong>{actual ? observed : "—"}</strong>
        </div>
        <div>
          <small>MEMORIAS PRIVADAS REGISTRADAS</small>
          <strong>{actual ? memories : "—"}</strong>
        </div>
      </section>
    );
  }

  const descriptions: Record<string, string> = {
    Mercado: "Explora propuestas y oportunidades registradas.",
    Contratos: "Consulta información contractual disponible sin inventar acuerdos.",
    Conversaciones: "Revisa las interacciones y negociaciones observadas.",
    Estrategias: "Conoce las estrategias compartidas por tus agentes.",
    Eventos: "Inspecciona actividad registrada y supervisión del sistema.",
  };

  return (
    <section className="rw-final-analytics rw-final-section-overview">
      <header className="rw-final-analytics-head">
        <div>
          <span className="rw-eyebrow">CENTRO DE OPERACIONES</span>
          <h3>{section}</h3>
          <p>{descriptions[section] ?? "Información del mundo."}</p>
        </div>
        <span className="rw-final-counter">Modo simulación</span>
      </header>

      <div className="rw-final-overview">
        <div>
          <small>REPLIKERS</small>
          <strong>{agents.length}</strong>
        </div>
        <div>
          <small>NEGOCIACIONES OBSERVADAS POR AGENTE</small>
          <strong>{actual ? observed : "—"}</strong>
        </div>
        <div>
          <small>ACEPTACIONES OBSERVADAS POR AGENTE</small>
          <strong>{actual ? accepted : "—"}</strong>
        </div>
      </div>
    </section>
  );
}
