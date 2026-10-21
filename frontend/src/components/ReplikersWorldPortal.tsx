
import {
  type ReactNode,
  useState,
} from "react";

import MundoReplikersWorld from "./MundoReplikersWorld";

export default function ReplikersWorldPortal({
  children,
}: {
  children: ReactNode;
}) {
  const [open, setOpen] = useState(() => {
    return (
      new URLSearchParams(
        window.location.search,
      ).get("world") === "1"
    );
  });

  return (
    <>
      {children}

      {!open && (
        <button
          type="button"
          className="rw-launch"
          onClick={() => setOpen(true)}
          aria-label="Abrir Replikers World"
        >
          <span>🌍</span>
          <strong>Replikers World</strong>
        </button>
      )}

      {open && (
        <div
          className="rw-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Replikers World"
        >
          <MundoReplikersWorld
            onClose={() => setOpen(false)}
          />
        </div>
      )}
    </>
  );
}
