import { Container, Graphics, Text } from "pixi.js";

export type WorldPixiAgent = {
  id: number;
  name: string;
  active: boolean;
};

const colors = [
  0x328dff,
  0xf36eaa,
  0xa878ff,
  0x13dcbb,
  0xffb74f,
];

type AnimatedAvatar = {
  container: Container;
  baseY: number;
  phase: number;
};

function createAvatar(
  agent: WorldPixiAgent,
  index: number,
  selected: boolean,
): AnimatedAvatar {
  const root = new Container();
  root.eventMode = "none";

  const x = 255 + index * 107;
  const baseY = 463 + (index % 2) * 15;
  const accent = colors[index % colors.length];

  root.position.set(x, baseY);

  const graphic = new Graphics();

  // Resplandor y plataforma de proyección.
  graphic.ellipse(0, 29, 37, 9)
    .fill({ color: accent, alpha: 0.18 });

  graphic.ellipse(0, 29, 26, 6)
    .stroke({
      color: accent,
      width: 2,
      alpha: 0.84,
    });

  if (selected) {
    graphic.circle(0, -3, 35)
      .stroke({
        color: 0x8df7ff,
        width: 2.5,
        alpha: 0.95,
      });

    graphic.circle(0, -3, 39)
      .stroke({
        color: accent,
        width: 1,
        alpha: 0.48,
      });
  }

  // Cuerpo con traje tecnológico.
  graphic.moveTo(-18, 12)
    .lineTo(-12, 0)
    .lineTo(12, 0)
    .lineTo(18, 12)
    .lineTo(16, 25)
    .lineTo(-16, 25)
    .closePath()
    .fill(0x0e3059)
    .stroke({
      color: accent,
      width: 2.3,
    });

  graphic.moveTo(-9, 3)
    .lineTo(0, 12)
    .lineTo(9, 3)
    .stroke({
      color: 0x9aeaff,
      width: 1.7,
    });

  graphic.roundRect(-5, 10, 10, 7, 2)
    .fill({ color: accent, alpha: 0.87 });

  // Casco holográfico.
  graphic.roundRect(-19, -28, 38, 36, 12)
    .fill(0x10294d)
    .stroke({
      color: accent,
      width: 3,
      alpha: 0.98,
    });

  graphic.roundRect(-15, -22, 30, 21, 8)
    .fill(0x071a36)
    .stroke({
      color: 0x85deff,
      width: 1,
      alpha: 0.62,
    });

  // Visor con expresión.
  graphic.roundRect(-11, -16, 9, 5, 2)
    .fill(0x8deeff);

  graphic.roundRect(2, -16, 9, 5, 2)
    .fill(0x8deeff);

  graphic.moveTo(-5, -6)
    .quadraticCurveTo(0, -2, 5, -6)
    .stroke({
      color: accent,
      width: 1.8,
    });

  // Antena y auriculares.
  graphic.moveTo(0, -28)
    .lineTo(0, -36)
    .stroke({
      color: accent,
      width: 2,
    });

  graphic.circle(0, -39, 3.5)
    .fill(0xd9ffff);

  graphic.roundRect(-23, -17, 6, 12, 3)
    .fill(accent);

  graphic.roundRect(17, -17, 6, 12, 3)
    .fill(accent);

  // Indicador de actividad, no de autonomía.
  graphic.circle(16, -30, 5)
    .fill(agent.active ? 0x22e9b3 : 0xffb24f)
    .stroke({
      color: 0x062139,
      width: 1.5,
    });

  root.addChild(graphic);

  const name = new Text({
    text: agent.name.length > 18
      ? agent.name.slice(0, 17) + "…"
      : agent.name,
    style: {
      fontFamily: "Arial, sans-serif",
      fontSize: 11,
      fontWeight: "bold",
      fill: 0xe8f7ff,
      stroke: {
        color: 0x03142e,
        width: 3,
      },
    },
  });

  name.anchor.set(0.5, 0);
  name.position.set(0, 37);
  root.addChild(name);

  const identifier = new Text({
    text: `R${agent.id}`,
    style: {
      fontFamily: "Arial, sans-serif",
      fontSize: 9,
      fontWeight: "bold",
      fill: selected ? 0x92f6ff : accent,
    },
  });

  identifier.anchor.set(0.5, 0);
  identifier.position.set(0, 52);
  root.addChild(identifier);

  return {
    container: root,
    baseY,
    phase: index * 0.9,
  };
}

export function createWorldPixiAvatarLayer() {
  const container = new Container();
  container.eventMode = "none";

  let animated: AnimatedAvatar[] = [];

  return {
    container,

    update(
      agents: WorldPixiAgent[],
      selectedId: number | null,
    ) {
      for (const child of container.removeChildren()) {
        child.destroy({ children: true });
      }

      animated = [];

      agents.slice(0, 5).forEach((agent, index) => {
        const avatar = createAvatar(
          agent,
          index,
          agent.id === selectedId,
        );

        container.addChild(avatar.container);
        animated.push(avatar);
      });
    },

    animate(time: number) {
      for (const avatar of animated) {
        avatar.container.position.y =
          avatar.baseY +
          Math.sin(time * 1.8 + avatar.phase) * 2.2;
      }
    },
  };
}
