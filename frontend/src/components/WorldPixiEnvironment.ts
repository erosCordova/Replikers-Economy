import { Container, Graphics, Text } from "pixi.js";

type Point = {
  x: number;
  y: number;
};

type ZoneVisual = Point & {
  id: string;
  title: string;
  accent: number;
};

const zones: ZoneVisual[] = [
  {
    id: "mercado", title: "Mercado",
    x: 471, y: 104, accent: 0xff933c,
  },
  {
    id: "innovacion", title: "Innovación",
    x: 590, y: 169, accent: 0xa66cff,
  },
  {
    id: "banco", title: "Banco",
    x: 709, y: 234, accent: 0x22db9c,
  },
  {
    id: "negociaciones", title: "Negociaciones",
    x: 352, y: 169, accent: 0xff557f,
  },
  {
    id: "plaza", title: "Plaza central",
    x: 471, y: 234, accent: 0x14cfff,
  },
  {
    id: "oficinas", title: "Oficinas",
    x: 590, y: 299, accent: 0x258bff,
  },
  {
    id: "arena", title: "Arena",
    x: 233, y: 234, accent: 0xffbf47,
  },
  {
    id: "reuniones", title: "Reuniones",
    x: 471, y: 364, accent: 0xf367de,
  },
];

const island: Point[] = [
  { x: 476, y: 34 },
  { x: 845, y: 229 },
  { x: 475, y: 437 },
  { x: 106, y: 232 },
];

function polygon(
  g: Graphics,
  points: Point[],
  color: number,
  alpha = 1,
) {
  const first = points[0];

  if (!first) return;

  g.moveTo(first.x, first.y);

  for (const p of points.slice(1)) {
    g.lineTo(p.x, p.y);
  }

  g.closePath().fill({ color, alpha });
}

function insideIsland(x: number, y: number) {
  let inside = false;

  for (
    let i = 0, j = island.length - 1;
    i < island.length;
    j = i++
  ) {
    const a = island[i];
    const b = island[j];

    const crosses =
      (a.y > y) !== (b.y > y);

    if (
      crosses &&
      x <
        ((b.x - a.x) * (y - a.y)) /
          (b.y - a.y) +
          a.x
    ) {
      inside = !inside;
    }
  }

  return inside;
}

function addTree(
  g: Graphics,
  x: number,
  y: number,
  scale: number,
) {
  g.ellipse(x, y + 5, scale * 9, scale * 4)
    .fill({ color: 0x00152b, alpha: 0.55 });

  g.rect(
    x - scale * 1.5,
    y - scale * 9,
    scale * 3,
    scale * 14,
  ).fill(0x2c4a58);

  g.moveTo(x, y - scale * 32)
    .lineTo(x - scale * 10, y - scale * 10)
    .lineTo(x + scale * 10, y - scale * 10)
    .closePath()
    .fill(0x0e7c8e);

  g.moveTo(x, y - scale * 24)
    .lineTo(x - scale * 12, y - scale * 3)
    .lineTo(x + scale * 12, y - scale * 3)
    .closePath()
    .fill(0x085b73);

  g.moveTo(x, y - scale * 33)
    .lineTo(x - scale * 4, y - scale * 22)
    .lineTo(x + scale * 4, y - scale * 22)
    .closePath()
    .fill({ color: 0x36d9ce, alpha: 0.65 });
}

function addLamp(
  g: Graphics,
  x: number,
  y: number,
) {
  g.moveTo(x, y)
    .lineTo(x, y - 14)
    .stroke({
      color: 0x3678ac,
      width: 2,
    });

  g.circle(x, y - 15, 7)
    .fill({
      color: 0x2aceff,
      alpha: 0.12,
    });

  g.circle(x, y - 15, 2.5)
    .fill(0xb7fbff);
}

function addRoad(
  g: Graphics,
  from: Point,
  to: Point,
) {
  const middle = {
    x: (from.x + to.x) / 2,
    y: (from.y + to.y) / 2,
  };

  g.moveTo(from.x, from.y)
    .lineTo(middle.x, middle.y)
    .lineTo(to.x, to.y)
    .stroke({
      color: 0x031425,
      width: 20,
      alpha: 0.9,
    });

  g.moveTo(from.x, from.y)
    .lineTo(to.x, to.y)
    .stroke({
      color: 0x157bb4,
      width: 6,
      alpha: 0.7,
    });

  g.moveTo(from.x, from.y)
    .lineTo(to.x, to.y)
    .stroke({
      color: 0x67dfff,
      width: 1.5,
      alpha: 0.65,
    });
}

function createGround(): Container {
  const root = new Container();
  root.eventMode = "none";

  const terrain = new Graphics();

  // Acantilados de la isla.
  polygon(terrain, [
    { x: 106, y: 232 },
    { x: 475, y: 437 },
    { x: 475, y: 465 },
    { x: 106, y: 260 },
  ], 0x12395b);

  polygon(terrain, [
    { x: 475, y: 437 },
    { x: 845, y: 229 },
    { x: 845, y: 259 },
    { x: 475, y: 465 },
  ], 0x092b51);

  polygon(terrain, island, 0x092c4b);

  terrain.moveTo(476, 34)
    .lineTo(845, 229)
    .lineTo(475, 437)
    .lineTo(106, 232)
    .closePath()
    .stroke({
      color: 0x24baf3,
      width: 4,
      alpha: 0.83,
    });

  // Trazados discretos de la infraestructura.
  for (let x = 130; x < 820; x += 28) {
    for (let y = 65; y < 420; y += 28) {
      if (
        insideIsland(x, y) &&
        (x * 3 + y) % 5 !== 0
      ) {
        terrain.circle(x, y, 0.75)
          .fill({
            color: 0x2684b5,
            alpha: 0.34,
          });
      }
    }
  }

  const center = zones.find(
    (zone) => zone.id === "plaza",
  )!;

  // Caminos entre distritos: son decorativos,
  // no representan operaciones económicas.
  for (const zone of zones) {
    if (zone.id === "plaza") continue;
    addRoad(terrain, center, zone);
  }

  // Plaza central con anillos concéntricos.
  terrain.ellipse(center.x, center.y + 12, 69, 33)
    .fill(0x082a52)
    .stroke({
      color: 0x30d0ff,
      width: 3.5,
      alpha: 0.87,
    });

  terrain.ellipse(center.x, center.y + 12, 53, 24)
    .stroke({
      color: 0x84f0ff,
      width: 1.5,
      alpha: 0.7,
    });

  // Vegetación generada de forma reproducible.
  let seed = 20261021;

  const random = () => {
    seed = (
      1664525 * seed + 1013904223
    ) >>> 0;

    return seed / 4294967296;
  };

  const trees: {
    x: number;
    y: number;
    scale: number;
  }[] = [];

  for (let i = 0; i < 240; i++) {
    const x = 135 + random() * 670;
    const y = 70 + random() * 320;

    if (!insideIsland(x, y)) continue;

    const nearBuilding = zones.some(
      (zone) => {
        const dx = (x - zone.x) / 83;
        const dy = (y - zone.y) / 59;
        return dx * dx + dy * dy < 1;
      },
    );

    if (nearBuilding) continue;

    trees.push({
      x,
      y,
      scale: 0.42 + random() * 0.45,
    });

    if (trees.length >= 62) break;
  }

  trees.sort((a, b) => a.y - b.y);

  for (const tree of trees) {
    addTree(
      terrain,
      tree.x,
      tree.y,
      tree.scale,
    );
  }

  // Farolas a lo largo del paseo de la ciudad.
  for (const zone of zones) {
    addLamp(
      terrain,
      zone.x - 66,
      zone.y + 28,
    );

    addLamp(
      terrain,
      zone.x + 66,
      zone.y + 28,
    );
  }

  // Reflejos y pequeñas cascadas bajo el borde.
  for (let i = 0; i < 12; i++) {
    const x = 150 + i * 28;
    const y = 259 + i * 15.6;

    terrain.moveTo(x, y)
      .lineTo(x - 2, y + 12)
      .stroke({
        color: 0x48d7ff,
        width: i % 3 === 0 ? 4 : 2,
        alpha: i % 2 === 0 ? 0.5 : 0.24,
      });
  }

  for (let i = 0; i < 12; i++) {
    const x = 512 + i * 27;
    const y = 437 - i * 15.5;

    terrain.moveTo(x, y)
      .lineTo(x + 2, y + 12)
      .stroke({
        color: 0x69dbff,
        width: i % 3 === 0 ? 4 : 2,
        alpha: i % 2 === 0 ? 0.47 : 0.24,
      });
  }

  root.addChild(terrain);
  return root;
}

function createLabels(): Container {
  const root = new Container();
  root.eventMode = "none";

  for (const zone of zones) {
    const group = new Container();
    const label = new Text({
      text: zone.title,
      style: {
        fontFamily: "Arial, sans-serif",
        fontSize: 12,
        fontWeight: "bold",
        fill: 0xf2fbff,
      },
    });

    label.anchor.set(0.5);

    const width = Math.max(
      86,
      Math.ceil(label.width) + 29,
    );

    const frame = new Graphics();

    frame.roundRect(
      -width / 2,
      -14,
      width,
      28,
      10,
    ).fill({
      color: 0x061a37,
      alpha: 0.96,
    }).stroke({
      color: zone.accent,
      width: 2.1,
      alpha: 0.94,
    });

    frame.roundRect(
      -width / 2 + 3,
      -11,
      width - 6,
      22,
      8,
    ).stroke({
      color: zone.accent,
      width: 0.8,
      alpha: 0.32,
    });

    group.addChild(frame);
    group.addChild(label);

    group.position.set(
      zone.x,
      zone.y + 66,
    );

    root.addChild(group);
  }

  return root;
}

export function createWorldPixiEnvironment() {
  return {
    ground: createGround(),
    labels: createLabels(),
  };
}
