import { Container, Graphics } from "pixi.js";

type Point = [number, number];

type District = {
  id: string;
  x: number;
  y: number;
  accent: number;
  secondary: number;
};

const districts: District[] = [
  { id: "mercado", x: 471, y: 104, accent: 0xffa345, secondary: 0xffd27c },
  { id: "innovacion", x: 590, y: 169, accent: 0xab7aff, secondary: 0x63daff },
  { id: "banco", x: 709, y: 234, accent: 0x24eab8, secondary: 0x57baff },
  { id: "negociaciones", x: 352, y: 169, accent: 0xff638d, secondary: 0xb78aff },
  { id: "plaza", x: 471, y: 234, accent: 0x21d8ff, secondary: 0x92efff },
  { id: "oficinas", x: 590, y: 299, accent: 0x258aff, secondary: 0x55d6ff },
  { id: "arena", x: 233, y: 234, accent: 0xffc568, secondary: 0xff7b91 },
  { id: "reuniones", x: 471, y: 364, accent: 0xed70ff, secondary: 0x83d9ff },
];

function polygon(
  graphics: Graphics,
  points: Point[],
  color: number,
  alpha = 1,
) {
  const first = points[0];
  if (!first) return;

  graphics.moveTo(first[0], first[1]);

  for (const [x, y] of points.slice(1)) {
    graphics.lineTo(x, y);
  }

  graphics.closePath().fill({ color, alpha });
}

function line(
  graphics: Graphics,
  points: Point[],
  color: number,
  width = 2,
  alpha = 1,
) {
  const first = points[0];
  if (!first) return;

  graphics.moveTo(first[0], first[1]);

  for (const [x, y] of points.slice(1)) {
    graphics.lineTo(x, y);
  }

  graphics.stroke({ color, width, alpha });
}

function tower(
  graphics: Graphics,
  x: number,
  baseY: number,
  width: number,
  height: number,
  color: number,
  secondary: number,
  depth = 11,
) {
  const left = x - width / 2;
  const right = x + width / 2;
  const top = baseY - height;
  const lift = depth * 0.52;

  // Tres fachadas y techo con profundidad isometrica.
  polygon(graphics, [
    [left - depth, top - lift],
    [left, top],
    [left, baseY],
    [left - depth, baseY - lift],
  ], 0x071529);

  polygon(graphics, [
    [left, top],
    [right, top],
    [right, baseY],
    [left, baseY],
  ], 0x0a2344);

  polygon(graphics, [
    [right, top],
    [right + depth, top - lift],
    [right + depth, baseY - lift],
    [right, baseY],
  ], 0x194474);

  polygon(graphics, [
    [left - depth, top - lift],
    [right, top - lift],
    [right + depth, top - lift],
    [right, top],
    [left, top],
  ], 0x21578d);

  // Franjas de luz en los bordes.
  line(graphics, [
    [left, top],
    [left, baseY],
  ], color, 2.5, 0.96);

  line(graphics, [
    [right, top],
    [right, baseY],
  ], secondary, 2, 0.87);

  line(graphics, [
    [right, top],
    [right + depth, top - lift],
  ], color, 2, 0.9);

  line(graphics, [
    [left - depth, top - lift],
    [right, top - lift],
  ], secondary, 2, 0.75);

  // Ventanas iluminadas distribuidas por fachada.
  const columns = Math.max(1, Math.floor((width - 9) / 9));
  const rows = Math.max(1, Math.floor((height - 12) / 10));

  for (let row = 0; row < rows; row++) {
    for (let column = 0; column < columns; column++) {
      const visible = (row * 3 + column * 7) % 5 !== 0;

      if (!visible) continue;

      const windowX = left + 6 + column * 9;
      const windowY = top + 9 + row * 10;

      graphics.rect(windowX, windowY, 3.5, 5.5)
        .fill({
          color: (row + column) % 4 === 0
            ? secondary
            : color,
          alpha: (row + column) % 3 === 0 ? 0.96 : 0.49,
        });
    }
  }

  graphics.rect(left + 4, baseY - 5, width - 8, 3)
    .fill({ color, alpha: 0.67 });
}

function platform(graphics: Graphics, accent: number) {
  graphics.ellipse(3, 30, 61, 18)
    .fill({ color: accent, alpha: 0.12 });

  polygon(graphics, [
    [-61, 17],
    [0, -17],
    [61, 17],
    [0, 51],
  ], 0x0a2341, 0.96);

  line(graphics, [
    [-61, 17],
    [0, 51],
    [61, 17],
  ], accent, 3, 0.92);

  line(graphics, [
    [-61, 17],
    [0, -17],
    [61, 17],
  ], accent, 1.7, 0.4);

  for (let i = 0; i < 4; i++) {
    const offset = -27 + i * 18;

    line(graphics, [
      [offset, 12],
      [offset + 21, 24],
    ], accent, 1, 0.17);
  }
}

function beacon(
  graphics: Graphics,
  x: number,
  y: number,
  color: number,
) {
  graphics.circle(x, y, 9)
    .fill({ color, alpha: 0.17 });

  graphics.circle(x, y, 4)
    .fill({ color, alpha: 0.73 });

  graphics.circle(x, y, 1.6)
    .fill(0xf1ffff);
}

function monument(
  graphics: Graphics,
  color: number,
  secondary: number,
) {
  graphics.ellipse(0, 13, 39, 16)
    .fill(0x092f51)
    .stroke({ color, width: 5, alpha: 0.9 });

  graphics.ellipse(0, 13, 26, 10)
    .stroke({ color: secondary, width: 1.7, alpha: 0.8 });

  polygon(graphics, [
    [-10, -10], [0, -51], [10, -10], [0, 8],
  ], 0x1767b3, 0.95);

  line(graphics, [
    [0, -51], [0, 8],
  ], secondary, 3, 0.95);

  beacon(graphics, 0, -54, secondary);
}

function stadium(
  graphics: Graphics,
  color: number,
  secondary: number,
) {
  graphics.ellipse(0, 6, 49, 22)
    .fill(0x112443)
    .stroke({ color, width: 5, alpha: 0.9 });

  graphics.ellipse(0, 6, 39, 16)
    .fill(0x071c37)
    .stroke({ color: secondary, width: 1.8 });

  graphics.ellipse(0, 6, 26, 10)
    .stroke({ color, width: 2, alpha: 0.85 });

  for (let i = 0; i < 12; i++) {
    const angle = (i / 12) * Math.PI * 2;

    beacon(
      graphics,
      Math.cos(angle) * 43,
      6 + Math.sin(angle) * 19,
      i % 2 === 0 ? color : secondary,
    );
  }
}

function drawDistrict(district: District): Graphics {
  const graphics = new Graphics();
  const { id, accent, secondary } = district;

  graphics.position.set(district.x, district.y);
  platform(graphics, accent);

  if (id === "mercado") {
    tower(graphics, -22, 14, 29, 41, accent, secondary);
    tower(graphics, 17, 12, 31, 47, secondary, accent);
    line(graphics, [
      [-43, -6], [36, -6],
    ], accent, 3.5);
    beacon(graphics, -39, -8, accent);
  }

  if (id === "innovacion") {
    tower(graphics, -14, 12, 32, 89, accent, secondary);
    tower(graphics, 27, 14, 26, 53, secondary, accent);
    line(graphics, [
      [-14, -77], [-14, -112],
    ], accent, 3);
    beacon(graphics, -14, -116, secondary);
    graphics.ellipse(-14, -74, 23, 9)
      .stroke({ color: accent, width: 2.8, alpha: 0.9 });
  }

  if (id === "banco") {
    tower(graphics, -18, 13, 32, 81, accent, secondary);
    tower(graphics, 25, 13, 28, 63, secondary, accent);
    line(graphics, [
      [-31, -49], [35, -49],
    ], accent, 2.7);
    beacon(graphics, -18, -76, accent);
  }

  if (id === "negociaciones") {
    tower(graphics, -30, 13, 21, 55, accent, secondary);
    tower(graphics, 30, 13, 21, 55, secondary, accent);
    graphics.ellipse(0, -1, 33, 15)
      .fill({ color: 0x341c58, alpha: 0.9 })
      .stroke({ color: accent, width: 3.8 });
    line(graphics, [
      [-24, -13], [0, -45], [24, -13],
    ], accent, 3);
    beacon(graphics, 0, -46, secondary);
  }

  if (id === "plaza") {
    monument(graphics, accent, secondary);
  }

  if (id === "oficinas") {
    tower(graphics, -32, 15, 23, 63, secondary, accent);
    tower(graphics, -1, 15, 29, 105, accent, secondary);
    tower(graphics, 34, 15, 22, 77, secondary, accent);
    line(graphics, [
      [-1, -90], [-1, -124],
    ], secondary, 2.4);
    beacon(graphics, -1, -127, secondary);
  }

  if (id === "arena") {
    stadium(graphics, accent, secondary);
    line(graphics, [
      [-36, -3], [-36, -35], [0, -57],
      [36, -35], [36, -3],
    ], accent, 3);
    beacon(graphics, 0, -56, secondary);
  }

  if (id === "reuniones") {
    stadium(graphics, accent, secondary);
    graphics.ellipse(0, -7, 34, 23)
      .fill({ color: 0x661c88, alpha: 0.18 })
      .stroke({ color: accent, width: 2.8 });
    line(graphics, [
      [-30, -7], [0, -64], [30, -7],
    ], secondary, 2.3);
    beacon(graphics, 0, -66, accent);
  }

  return graphics;
}

export function createWorldPixiArchitecture(): Container {
  const architecture = new Container();
  architecture.eventMode = "none";

  const ordered = [...districts].sort(
    (a, b) => a.y - b.y,
  );

  for (const district of ordered) {
    architecture.addChild(drawDistrict(district));
  }

  return architecture;
}
