/* RW_WORLD_AUTH_BRIDGE_V1 */
import { API_URL as rwSharedWorldAPIURL } from "../api";
import { getAccessToken as rwSharedWorldToken } from "../auth/sesion";

import { useEffect, useState } from "react";
import "./WorldEventFeed.css";

type EventRow = {
  id: number;
  repliker_name: string;
  kind: string;
  status: string;
  created_at: string;
  negotiation_id: number | null;
};

export function apiBase(): string {
          return rwSharedWorldAPIURL.replace(/\/+$/, "");
        }

export function accessToken(): string | null {
          return rwSharedWorldToken() ?? "";
        }

export default function WorldEventFeed() {
  const [events, setEvents] = useState<EventRow[]>([]);
  const [message, setMessage] = useState(
    "Consultando eventos del mundo...",
  );

  useEffect(() => {
    const controller = new AbortController();

    async function refreshEvents() {
      if (document.visibilityState !== "visible") return;

      const token = accessToken();

      const headers: Record<string, string> = {
        Accept: "application/json",
      };

      if (token) {
        headers.Authorization = "Bearer " + token;
      }

      try {
        const response = await fetch(
          apiBase() + "/world/events/mine?limit=20",
          {
            method: "GET",
            credentials: "include",
            headers,
            signal: controller.signal,
          },
        );

        if (!response.ok) {
          throw new Error(
            "HTTP " + response.status,
          );
        }

        const data = await response.json() as {
          events: EventRow[];
        };

        if (!controller.signal.aborted) {
          setEvents(
            Array.isArray(data.events)
              ? data.events
              : [],
          );

          setMessage(
            "Eventos registrados por el ejecutor gobernado.",
          );
        }
      } catch (error) {
        if (controller.signal.aborted) return;

        const code =
          error instanceof Error
            ? error.message
            : "Sin conexión";

        if (code.includes("503")) {
          setMessage(
            "La base activa necesita la migración de eventos World.",
          );
        } else if (
          code.includes("401") ||
          code.includes("403")
        ) {
          setMessage(
            "Inicia sesión para consultar el historial.",
          );
        } else {
          setMessage(
            "Eventos no disponibles: " + code,
          );
        }
      }
    }

    void refreshEvents();

    const interval = window.setInterval(
      () => void refreshEvents(),
      20000,
    );

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, []);

  return (
    <section
      className="rw-event-feed"
      aria-label="Historial persistente de eventos"
    >
      <h4>📡 Eventos persistentes</h4>
      <p>{message}</p>

      {events.length === 0 && (
        <p>
          No hay eventos disponibles para mostrar.
        </p>
      )}

      {events.map((event) => (
        <article
          className="rw-event-feed-item"
          key={event.id}
        >
          <strong>{event.repliker_name}</strong>

          <span>
            {event.kind === "governance"
              ? "🛡️ Bloqueo de política"
              : event.kind === "negotiation"
                ? "🤝 Negociación"
                : "⚙️ Actividad"}
            {" · "}
            {event.status}
          </span>

          <small>
            {event.created_at} · Ronda registrada
          </small>
        </article>
      ))}

      <small>
        Actividad registrada en simulación.
        No representa desplazamientos físicos ni beneficios.
      </small>
    </section>
  );
}
