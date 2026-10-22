import "./NeonCityArchitecture.css";

type ArchitectureProps = {
  id: string;
  x: number;
  y: number;
  active: boolean;
};

type TowerProps = {
  x: number;
  width: number;
  height: number;
  accent: string;
};

const accentByZone: Record<string, string> = {
  mercado: "#ff9b39",
  innovacion: "#b473ff",
  banco: "#19e5ae",
  negociaciones: "#ff5a80",
  plaza: "#30dcff",
  oficinas: "#329eff",
  arena: "#ffd15c",
  reuniones: "#fa69e4",
};

function Tower({
  x,
  width,
  height,
  accent,
}: TowerProps) {
  const bottom = 23;
  const top = bottom - height;
  const depth = 10;

  const rows = Math.max(2, Math.floor((height - 10) / 10));
  const cols = Math.max(2, Math.floor((width - 9) / 10));

  return (
    <g className="rw-neon-tower">
      <rect
        x={x}
        y={top}
        width={width}
        height={height}
        fill="#071a35"
        stroke={accent}
        strokeOpacity=".65"
        strokeWidth="1.4"
      />

      <polygon
        points={[
          `${x + width},${top}`,
          `${x + width + depth},${top - 7}`,
          `${x + width + depth},${bottom - 7}`,
          `${x + width},${bottom}`,
        ].join(" ")}
        fill="#10386a"
        stroke={accent}
        strokeOpacity=".35"
      />

      <polygon
        points={[
          `${x},${top}`,
          `${x + depth},${top - 7}`,
          `${x + width + depth},${top - 7}`,
          `${x + width},${top}`,
        ].join(" ")}
        fill="#1b5a93"
        stroke={accent}
        strokeWidth="1.4"
      />

      <line
        x1={x + 2}
        y1={top + 2}
        x2={x + 2}
        y2={bottom - 2}
        stroke={accent}
        strokeWidth="2"
        opacity=".9"
      />

      <line
        x1={x + width - 2}
        y1={top + 2}
        x2={x + width - 2}
        y2={bottom - 2}
        stroke={accent}
        strokeWidth="1.5"
        opacity=".85"
      />

      {Array.from({ length: rows }, (_, row) =>
        Array.from({ length: cols }, (_, col) => (
          <rect
            key={`${row}-${col}`}
            x={x + 6 + col * 10}
            y={top + 7 + row * 10}
            width="4"
            height="5"
            rx=".7"
            fill={accent}
            opacity={(row + col) % 3 === 0 ? ".95" : ".42"}
          />
        )),
      )}

      <path
        d={`M${x + 5} ${top + 3} H${x + width - 3}`}
        fill="none"
        stroke="#d6faff"
        strokeWidth="1.2"
        opacity=".8"
      />
    </g>
  );
}

function Orb({
  color,
  size = 19,
}: {
  color: string;
  size?: number;
}) {
  return (
    <g className="rw-neon-orb">
      <circle
        cx="0"
        cy="-20"
        r={size + 6}
        fill={color}
        opacity=".12"
      />
      <circle
        cx="0"
        cy="-20"
        r={size}
        fill="#0b3975"
        stroke={color}
        strokeWidth="2.5"
      />
      <ellipse
        cx="0"
        cy="-20"
        rx={size * .4}
        ry={size}
        fill="none"
        stroke="#7aeaff"
        strokeWidth="1.5"
        opacity=".9"
      />
      <ellipse
        cx="0"
        cy="-20"
        rx={size}
        ry={size * .28}
        fill="none"
        stroke={color}
        strokeWidth="1.7"
      />
      <path
        d={`M${-size} -20 H${size}`}
        stroke="#b2f8ff"
        strokeWidth="1"
        opacity=".9"
      />
      <circle
        cx="-5"
        cy="-27"
        r="4"
        fill="#f3fdff"
        opacity=".85"
      />
    </g>
  );
}

function Stadium({
  accent,
  title,
}: {
  accent: string;
  title?: string;
}) {
  return (
    <g>
      <ellipse
        cx="0"
        cy="10"
        rx="46"
        ry="22"
        fill="#04172d"
        stroke={accent}
        strokeWidth="6"
      />
      <ellipse
        cx="0"
        cy="7"
        rx="37"
        ry="17"
        fill="#123664"
        stroke="#94e9ff"
        strokeWidth="1.5"
      />
      <ellipse
        cx="0"
        cy="7"
        rx="26"
        ry="10"
        fill="#052041"
        stroke={accent}
        strokeWidth="1.5"
        strokeDasharray="5 4"
      />
      {Array.from({ length: 12 }, (_, i) => {
        const angle = (i * Math.PI) / 6;
        return (
          <circle
            key={i}
            cx={Math.cos(angle) * 40}
            cy={7 + Math.sin(angle) * 18}
            r="2.7"
            fill={i % 2 ? "#a4f1ff" : accent}
          />
        );
      })}
      {title && (
        <text
          x="0"
          y="11"
          fontSize="10"
          fontWeight="900"
          textAnchor="middle"
          fill="#fff9df"
        >
          {title}
        </text>
      )}
    </g>
  );
}

export default function NeonCityArchitecture({
  id,
  x,
  y,
  active,
}: ArchitectureProps) {
  const accent = accentByZone[id] ?? "#31c9ff";

  return (
    <g
      className={
        "rw-neon-architecture" +
        (active ? " rw-neon-architecture--active" : "")
      }
      transform={`translate(${x} ${y - 27})`}
      pointerEvents="none"
      aria-hidden="true"
      style={{ "--rw-zone-accent": accent } as React.CSSProperties}
    >
      <ellipse
        cx="0"
        cy="25"
        rx="55"
        ry="17"
        fill={accent}
        opacity=".16"
      />

      <path
        d="M-47 23 L0 47 L47 23"
        fill="none"
        stroke={accent}
        strokeWidth="2"
        strokeOpacity=".65"
      />

      {id === "mercado" && (
        <g>
          <Tower x={-36} width={61} height={38} accent={accent} />
          <path
            d="M-41 -17 H34 L42 -3 H-45 Z"
            fill="#a64822"
            stroke="#ffc66d"
            strokeWidth="2"
          />
          {Array.from({ length: 6 }, (_, i) => (
            <path
              key={i}
              d={`M${-40 + i * 13} -16
                  h13 l5 13 h-14 Z`}
              fill={i % 2 ? "#fff0b4" : "#ff684b"}
              opacity=".95"
            />
          ))}
          <rect
            x="-21"
            y="-35"
            width="43"
            height="12"
            rx="5"
            fill="#a93c22"
            stroke="#ffba61"
          />
          <text
            x="0"
            y="-26"
            fontSize="9"
            fontWeight="900"
            textAnchor="middle"
            fill="#fff"
          >
            MERCADO
          </text>
        </g>
      )}

      {id === "innovacion" && (
        <g>
          <Tower x={-37} width={26} height={62} accent={accent} />
          <Tower x={17} width={22} height={49} accent="#4bccff" />
          <ellipse
            cy="5"
            rx="36"
            ry="12"
            fill="#28135b"
            stroke="#b979ff"
            strokeWidth="4"
          />
          <g transform="translate(0 -23)">
            <Orb color="#a46aff" size={22} />
          </g>
        </g>
      )}

      {id === "banco" && (
        <g>
          <Tower x={-39} width={29} height={61} accent={accent} />
          <Tower x={8} width={34} height={72} accent="#18bbff" />
          <rect
            x="-30"
            y="-5"
            width="63"
            height="28"
            rx="2"
            fill="#073d4f"
            stroke="#30f4c9"
            strokeWidth="2"
          />
          <text
            x="1"
            y="13"
            fontSize="17"
            fontWeight="900"
            fill="#eaffce"
            textAnchor="middle"
          >
            RCR
          </text>
        </g>
      )}

      {id === "negociaciones" && (
        <g>
          <Tower x={-39} width={26} height={40} accent="#ff5c76" />
          <Tower x={22} width={21} height={38} accent="#ff5c76" />
          <Stadium accent={accent} />
          <path
            d="M-20 -18 Q0 -44 20 -18"
            fill="none"
            stroke="#ff88ae"
            strokeWidth="3"
          />
          <circle cx="-17" cy="-21" r="5" fill="#ff8da9" />
          <circle cx="17" cy="-21" r="5" fill="#ff8da9" />
          <path
            d="M-10 -21 L0 -29 L10 -21"
            fill="none"
            stroke="#fff0f7"
            strokeWidth="2"
          />
        </g>
      )}

      {id === "plaza" && (
        <g>
          <ellipse
            cx="0"
            cy="14"
            rx="43"
            ry="19"
            fill="#05204b"
            stroke="#1fe0ff"
            strokeWidth="5"
          />
          <ellipse
            cx="0"
            cy="14"
            rx="31"
            ry="13"
            fill="none"
            stroke="#9eefff"
            strokeWidth="1.8"
            strokeDasharray="5 3"
          />
          <g transform="translate(0 -16)">
            <Orb color="#23d9ff" size={26} />
          </g>
          <path
            d="M-16 23 H16"
            stroke="#b7f6ff"
            strokeWidth="3"
          />
        </g>
      )}

      {id === "oficinas" && (
        <g>
          <Tower x={-40} width={31} height={70} accent={accent} />
          <Tower x={-4} width={26} height={83} accent="#1fcbff" />
          <Tower x={23} width={18} height={51} accent="#7292ff" />
          <path
            d="M-4 -65 L9 -77"
            stroke="#e5fcff"
            strokeWidth="2"
          />
        </g>
      )}

      {id === "arena" && (
        <g>
          <Stadium accent={accent} title="ARENA" />
          <path
            d="M-35 -4 L-35 -30 M35 -4 L35 -30"
            stroke={accent}
            strokeWidth="4"
          />
          <path
            d="M-44 -30 H44"
            stroke="#fff0a1"
            strokeWidth="2"
          />
          <path
            d="M-43 -32 Q0 -67 43 -32"
            fill="none"
            stroke={accent}
            strokeWidth="3"
          />
          <circle cx="0" cy="-39" r="5" fill="#ffe59b" />
        </g>
      )}

      {id === "reuniones" && (
        <g>
          <Stadium accent={accent} />
          <path
            d="M-33 -6 Q0 -70 33 -6"
            fill="#ba51ef"
            fillOpacity=".13"
            stroke="#fa7ef4"
            strokeWidth="2.5"
          />
          <path
            d="M-24 -9 Q0 -47 24 -9"
            fill="none"
            stroke="#8ceaff"
            strokeWidth="1.7"
          />
          <circle cx="-15" cy="-5" r="5" fill="#fcb3ee" />
          <circle cx="0" cy="-14" r="5" fill="#d4f6ff" />
          <circle cx="15" cy="-5" r="5" fill="#fcb3ee" />
          <path
            d="M-26 9 Q0 -2 26 9"
            stroke="#fa7ef4"
            strokeWidth="2"
            fill="none"
          />
        </g>
      )}

      <circle
        cx="-48"
        cy="23"
        r="2.5"
        fill="#c5f9ff"
        opacity=".85"
      />
      <circle
        cx="48"
        cy="23"
        r="2.5"
        fill={accent}
        opacity=".85"
      />
    </g>
  );
}
