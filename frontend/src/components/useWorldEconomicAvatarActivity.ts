
import { useEffect, useState } from "react";
import { apiBase, accessToken } from "./WorldEventFeed";

type EconomyKind = "negotiation" | "contract" | "settlement";

type EconomyEvent = {
  id: string;
  kind: EconomyKind;
  seller_id: number;
  buyer_id: number;
};

type Activity = Record<number, EconomyKind>;

function isEconomicEvent(value: unknown): value is EconomyEvent {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const item = value as Record<string, unknown>;

  return (
    typeof item.id === "string" &&
    (
      item.kind === "negotiation" ||
      item.kind === "contract" ||
      item.kind === "settlement"
    ) &&
    Number.isSafeInteger(Number(item.seller_id)) &&
    Number.isSafeInteger(Number(item.buyer_id)) &&
    Number(item.seller_id) > 0 &&
    Number(item.buyer_id) > 0
  );
}

export function economicAvatarClass(
  agent: unknown,
  activity: Readonly<Activity>,
): string {
  if (typeof agent !== "object" || agent === null) {
    return "rw-avatar";
  }

  const fields = agent as Record<string, unknown>;

  const value =
    fields.repliker_id ??
    fields.replikerId ??
    fields.id;

  const agentId = Number(value);

  if (!Number.isSafeInteger(agentId) || agentId <= 0) {
    return "rw-avatar";
  }

  const kind = activity[agentId];

  return kind
    ? `rw-avatar rw-avatar-economy-${kind}`
    : "rw-avatar";
}

export default function useWorldEconomicAvatarActivity(): Activity {
  const [activity, setActivity] = useState<Activity>({});

  useEffect(() => {
    const controller = new AbortController();

    let previousIds: Set<string> | null = null;
    let previousToken: string | null = null;
    let requesting = false;
    let clearTimer: number | undefined;

    function clearHighlight() {
      if (clearTimer !== undefined) {
        window.clearTimeout(clearTimer);
        clearTimer = undefined;
      }

      setActivity({});
    }

    async function refresh() {
      if (
        controller.signal.aborted ||
        document.visibilityState !== "visible" ||
        requesting
      ) {
        return;
      }

      const token = accessToken();

      if (token !== previousToken) {
        previousToken = token;
        previousIds = null;
        clearHighlight();
      }

      if (!token) {
        return;
      }

      requesting = true;

      try {
        const response = await fetch(
          apiBase() + "/world/events/economy/mine?limit=100",
          {
            method: "GET",
            credentials: "include",
            headers: {
              Authorization: `Bearer ${token}`,
            },
            cache: "no-store",
            signal: controller.signal,
          },
        );

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            previousIds = null;
            clearHighlight();
          }

          return;
        }

        const payload = (await response.json()) as {
          events?: unknown[];
        };

        if (controller.signal.aborted) {
          return;
        }

        const events = Array.isArray(payload.events)
          ? payload.events.filter(isEconomicEvent)
          : [];

        const ids = new Set(events.map(event => event.id));

        // Primera respuesta: establece el historial sin animarlo.
        if (previousIds !== null) {
          const incoming = events.filter(
            event => !previousIds?.has(event.id),
          );

          if (incoming.length > 0) {
            const next: Activity = {};

            // Los eventos mas recientes prevalecen.
            for (const event of [...incoming].reverse()) {
              next[Number(event.seller_id)] = event.kind;
              next[Number(event.buyer_id)] = event.kind;
            }

            if (Object.keys(next).length > 0) {
              if (clearTimer !== undefined) {
                window.clearTimeout(clearTimer);
              }

              setActivity(next);

              clearTimer = window.setTimeout(() => {
                setActivity({});
                clearTimer = undefined;
              }, 5000);
            }
          }
        }

        previousIds = ids;

      } catch {
        // Una desconexion temporal no genera actividad ficticia.
      } finally {
        requesting = false;
      }
    }

    function onVisibilityChange() {
      if (document.visibilityState === "visible") {
        void refresh();
      } else {
        clearHighlight();
      }
    }

    void refresh();

    const interval = window.setInterval(() => {
      void refresh();
    }, 10000);

    document.addEventListener(
      "visibilitychange",
      onVisibilityChange,
    );

    return () => {
      controller.abort();
      window.clearInterval(interval);

      if (clearTimer !== undefined) {
        window.clearTimeout(clearTimer);
      }

      document.removeEventListener(
        "visibilitychange",
        onVisibilityChange,
      );
    };
  }, []);

  return activity;
}
