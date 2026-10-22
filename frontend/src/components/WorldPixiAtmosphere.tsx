import { useEffect, useRef } from "react";
import { Application, Graphics } from "pixi.js";
import "./WorldPixiAtmosphere.css";
import { createWorldPixiAvatarLayer, type WorldPixiAgent } from "./WorldPixiAvatars";
import { createWorldPixiArchitecture } from "./WorldPixiArchitecture";
import { createWorldPixiEnvironment }
  from "./WorldPixiEnvironment";

type Point = {
  x: number;
  y: number;
  color: number;
};

const points: Point[] = [
  { x: 471, y: 104, color: 0xffa542 },
  { x: 590, y: 169, color: 0xb36dff },
  { x: 709, y: 234, color: 0x23edbc },
  { x: 352, y: 169, color: 0xff658a },
  { x: 471, y: 234, color: 0x36dfff },
  { x: 590, y: 299, color: 0x318fff },
  { x: 233, y: 234, color: 0xffd26c },
  { x: 471, y: 364, color: 0xf875e9 },
];

const routes = [
  [4, 0],
  [4, 1],
  [4, 2],
  [4, 3],
  [4, 5],
  [4, 6],
  [4, 7],
  [0, 3],
  [1, 2],
  [5, 7],
] as const;

function curvePoint(a: Point, b: Point, fraction: number) {
  const controlX = (a.x + b.x) / 2;
  const controlY = Math.min(a.y, b.y) - 42;
  const inverse = 1 - fraction;

  return {
    x:
      inverse * inverse * a.x +
      2 * inverse * fraction * controlX +
      fraction * fraction * b.x,
    y:
      inverse * inverse * a.y +
      2 * inverse * fraction * controlY +
      fraction * fraction * b.y,
  };
}

export default function WorldPixiAtmosphere({
  agents,
  selectedId,
}: {
  agents: WorldPixiAgent[];
  selectedId: number | null;
}) {
  const holderRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<ReturnType<
    typeof createWorldPixiAvatarLayer
  > | null>(null);

  const latestRef = useRef({ agents, selectedId });

  useEffect(() => {
    latestRef.current = { agents, selectedId };
    avatarRef.current?.update(agents, selectedId);
  }, [agents, selectedId]);

  useEffect(() => {
    const holder = holderRef.current;
    if (!holder) return;

    const scene = holder.parentElement;
    const svg = scene?.querySelector<SVGSVGElement>(
      "svg.rw-city",
    );

    if (!scene || !svg) return;

    const app = new Application();

    let disposed = false;
    let ready = false;
    let observer: ResizeObserver | null = null;

    const syncPosition = () => {
      const svgRect = svg.getBoundingClientRect();
      const sceneRect = scene.getBoundingClientRect();

      if (svgRect.width <= 0 || svgRect.height <= 0) {
        return;
      }

      // Respetar la zona realmente dibujada por SVG.
      const ratio = 940 / 555;

      const width = Math.min(
        svgRect.width,
        svgRect.height * ratio,
      );

      const height = width / ratio;

      holder.style.left = `${
        svgRect.left - sceneRect.left +
        (svgRect.width - width) / 2
      }px`;

      holder.style.top = `${
        svgRect.top - sceneRect.top +
        (svgRect.height - height) / 2
      }px`;

      holder.style.width = `${width}px`;
      holder.style.height = `${height}px`;
    };

    const initialize = async () => {
      await app.init({
        width: 940,
        height: 555,
        backgroundAlpha: 0,
        antialias: true,
        autoDensity: true,
        resolution: Math.min(
          window.devicePixelRatio || 1,
          2,
        ),
        preference: "webgl",
      });

      if (disposed) {
        app.destroy(
          { removeView: true },
          { children: true },
        );
        return;
      }

      ready = true;
      app.stage.eventMode = "none";
      app.ticker.maxFPS = 30;

      const canvas = app.canvas;
      canvas.style.width = "100%";
      canvas.style.height = "100%";
      canvas.style.display = "block";
      canvas.style.pointerEvents = "none";
      canvas.setAttribute("aria-hidden", "true");

      holder.appendChild(canvas);

      const environment = createWorldPixiEnvironment();
      app.stage.addChild(environment.ground);

      const architecture = createWorldPixiArchitecture();
      // La arquitectura se dibuja despues de las rutas.

      // Ocultar edificios SVG solo cuando Pixi este listo.
      scene.classList.add("rw-pixi-city-ready");

      // Conexiones decorativas entre las ocho zonas.
      // No representan transacciones reales.
      const connections = new Graphics();

      for (const [from, to] of routes) {
        const a = points[from];
        const b = points[to];

        connections
          .moveTo(a.x, a.y)
          .quadraticCurveTo(
            (a.x + b.x) / 2,
            Math.min(a.y, b.y) - 42,
            b.x,
            b.y,
          )
          .stroke({
            color: a.color,
            width: 1.4,
            alpha: 0.22,
          });
      }

      app.stage.addChild(connections);

      // Edificios por delante de caminos luminosos.
      app.stage.addChild(architecture);

      const halos = points.map((point) => {
        const circle = new Graphics();

        circle
          .circle(0, 0, 20)
          .fill({
            color: point.color,
            alpha: 0.065,
          })
          .circle(0, 0, 13)
          .stroke({
            color: point.color,
            width: 1.7,
            alpha: 0.5,
          })
          .circle(0, 0, 4)
          .fill({
            color: 0xcafaff,
            alpha: 0.5,
          });

        circle.position.set(point.x, point.y);
        app.stage.addChild(circle);
        return circle;
      });

      // Luces que viajan visualmente por los caminos.
      const signals = routes.map(([from, to], index) => {
        const point = points[from];
        const glow = new Graphics();

        glow
          .circle(0, 0, 10)
          .fill({
            color: point.color,
            alpha: 0.1,
          })
          .circle(0, 0, 4)
          .fill({
            color: point.color,
            alpha: 0.7,
          })
          .circle(0, 0, 1.5)
          .fill({
            color: 0xffffff,
            alpha: 0.9,
          });

        app.stage.addChild(glow);

        return {
          graphic: glow,
          from,
          to,
          offset: (index * 0.173) % 1,
        };
      });

      // Partículas atmosféricas reproducibles.
      let seed = 20261021;

      const random = () => {
        seed = (1664525 * seed + 1013904223) >>> 0;
        return seed / 4294967296;
      };

      const particles = Array.from({ length: 48 }, () => {
        const x = 100 + random() * 740;
        const y = 75 + random() * 390;
        const radius = 0.8 + random() * 1.5;

        const particle = new Graphics();

        particle
          .circle(0, 0, radius)
          .fill({
            color: random() > 0.78
              ? 0xc879ff
              : 0x7fdfff,
            alpha: 0.5,
          });

        particle.position.set(x, y);
        app.stage.addChild(particle);

        return {
          graphic: particle,
          x,
          y,
          phase: random() * Math.PI * 2,
          speed: 0.3 + random() * 0.8,
        };
      });

      app.stage.addChild(environment.labels);

      const avatarLayer = createWorldPixiAvatarLayer();
      app.stage.addChild(avatarLayer.container);

      avatarRef.current = avatarLayer;

      avatarLayer.update(
        latestRef.current.agents,
        latestRef.current.selectedId,
      );

      let time = 0;

      app.ticker.add((ticker) => {
        time += Math.min(ticker.deltaMS, 50) / 1000;
        avatarLayer.animate(time);

        halos.forEach((halo, index) => {
          const pulse = Math.sin(time * 1.6 + index * 0.7);
          halo.scale.set(1 + pulse * 0.08);
          halo.alpha = 0.48 + pulse * 0.15;
        });

        signals.forEach((signal) => {
          const progress = (
            time * 0.095 + signal.offset
          ) % 1;

          const position = curvePoint(
            points[signal.from],
            points[signal.to],
            progress,
          );

          signal.graphic.position.set(
            position.x,
            position.y,
          );

          signal.graphic.alpha =
            Math.sin(Math.PI * progress) * 0.85;
        });

        particles.forEach((particle) => {
          const offset = time * particle.speed;

          particle.graphic.position.set(
            particle.x + Math.sin(
              offset + particle.phase,
            ) * 5,
            particle.y - (offset * 3) % 18,
          );

          particle.graphic.alpha =
            0.25 + Math.abs(Math.sin(
              time + particle.phase,
            )) * 0.45;
        });
      });

      const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;

      const updateVisibility = () => {
        if (
          disposed ||
          reducedMotion ||
          document.hidden
        ) {
          app.stop();
        } else {
          app.start();
        }
      };

      observer = new ResizeObserver(syncPosition);
      observer.observe(scene);
      observer.observe(svg);
      syncPosition();

      document.addEventListener(
        "visibilitychange",
        updateVisibility,
      );

      window.addEventListener(
        "resize",
        syncPosition,
      );

      updateVisibility();

      // Guardar una sola rutina de limpieza.
      cleanup = () => {
        if (avatarRef.current === avatarLayer) {
          avatarRef.current = null;
        }
        scene.classList.remove("rw-pixi-city-ready");
        document.removeEventListener(
          "visibilitychange",
          updateVisibility,
        );
        window.removeEventListener(
          "resize",
          syncPosition,
        );
        observer?.disconnect();
        app.destroy(
          { removeView: true },
          { children: true },
        );
      };
    };

    let cleanup: (() => void) | null = null;

    void initialize().catch((error: unknown) => {
      // Si WebGL no está disponible, SVG sigue funcionando.
      if (!disposed) {
        console.warn(
          "Replikers World: capa PixiJS no disponible.",
          error,
        );
      }
    });

    return () => {
      disposed = true;

      if (ready) {
        cleanup?.();
      }
    };
  }, []);

  return (
    <div
      ref={holderRef}
      className="rw-pixi-atmosphere"
      aria-hidden="true"
    />
  );
}
