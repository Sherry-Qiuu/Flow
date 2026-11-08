import { motion } from "framer-motion";
import { useI18n } from "../i18n";
import type { FaceMood } from "../state/types";

interface FaceExpressionProps {
  mood: FaceMood;
  size?: number;
  quiet?: boolean;
}

const CLOSED_EYES = new Set<FaceMood>(["sleepy", "resting"]);

export function FaceExpression({
  mood,
  size = 280,
  quiet = false,
}: FaceExpressionProps) {
  const closed = CLOSED_EYES.has(mood);
  const happy = mood === "happy" || mood === "excited";
  const thinking = mood === "thinking";
  const concerned = mood === "concerned";
  const listening = mood === "listening";
  const { t } = useI18n();

  return (
    <motion.div
      className="face"
      style={{ width: size, height: size }}
      role="img"
      aria-label={t.face.aria(mood)}
      animate={quiet ? { y: 0 } : { y: [0, -5, 0] }}
      transition={{
        duration: 4.5,
        repeat: quiet ? 0 : Infinity,
        ease: "easeInOut",
      }}
    >
      <svg viewBox="0 0 280 280" width="100%" height="100%">
        <defs>
          <radialGradient id="faceGlow" cx="50%" cy="38%" r="70%">
            <stop offset="0%" stopColor="#3a2b1f" />
            <stop offset="100%" stopColor="#241b15" />
          </radialGradient>
          <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="12" />
          </filter>
        </defs>
        <circle
          cx="140"
          cy="140"
          r="104"
          fill="var(--flow-amber)"
          opacity="0.13"
          filter="url(#softGlow)"
        />
        <circle
          cx="140"
          cy="140"
          r="100"
          fill="url(#faceGlow)"
          stroke="var(--flow-line)"
          strokeWidth="2"
        />
        {closed ? (
          <g
            stroke="var(--flow-text)"
            strokeWidth="6"
            strokeLinecap="round"
            fill="none"
          >
            <path d="M92 130 Q110 116 128 130" />
            <path d="M152 130 Q170 116 188 130" />
          </g>
        ) : (
          <g>
            <ellipse
              cx={thinking ? 114 : 110}
              cy="128"
              rx={listening ? 10 : 9}
              ry={listening ? 13 : 10}
              fill="var(--flow-text)"
            />
            <ellipse
              cx={thinking ? 174 : 170}
              cy="128"
              rx={listening ? 10 : 9}
              ry={listening ? 13 : 10}
              fill="var(--flow-text)"
            />
            {listening && (
              <>
                <circle cx="113" cy="131" r="3" fill="var(--flow-bg)" />
                <circle cx="173" cy="131" r="3" fill="var(--flow-bg)" />
              </>
            )}
          </g>
        )}
        {concerned && (
          <g
            stroke="var(--flow-text)"
            strokeWidth="4"
            strokeLinecap="round"
            opacity="0.8"
          >
            <path d="M92 106 L126 112" />
            <path d="M154 112 L188 106" />
          </g>
        )}
        {happy && (
          <>
            <ellipse cx="94" cy="158" rx="12" ry="7" fill="var(--flow-amber)" opacity="0.25" />
            <ellipse cx="186" cy="158" rx="12" ry="7" fill="var(--flow-amber)" opacity="0.25" />
          </>
        )}
        {thinking && (
          <g fill="var(--flow-amber)" opacity="0.85">
            <circle cx="210" cy="86" r="4" />
            <circle cx="224" cy="72" r="3" />
            <circle cx="234" cy="58" r="2" />
          </g>
        )}
        {mood === "excited" && (
          <g fill="var(--flow-amber)">
            <motion.path
              d="M48 84 L52 94 L62 98 L52 102 L48 112 L44 102 L34 98 L44 94 Z"
              animate={{ opacity: [0.4, 1, 0.4], rotate: [0, 12, 0] }}
              transition={{ duration: 2.4, repeat: Infinity }}
              style={{ transformOrigin: "48px 98px" }}
            />
            <motion.path
              d="M228 148 L231 156 L239 159 L231 162 L228 170 L225 162 L217 159 L225 156 Z"
              animate={{ opacity: [0.3, 1, 0.3], rotate: [0, -10, 0] }}
              transition={{ duration: 1.8, repeat: Infinity, delay: 0.4 }}
              style={{ transformOrigin: "228px 159px" }}
            />
          </g>
        )}
        <Mouth mood={mood} />
      </svg>
    </motion.div>
  );
}

function Mouth({ mood }: { mood: FaceMood }) {
  if (mood === "excited") {
    return (
      <motion.path
        d="M104 164 Q140 210 176 164 Q160 222 140 222 Q120 222 104 164"
        fill="var(--flow-amber)"
        animate={{ scaleY: [0.9, 1, 0.9] }}
        transition={{ duration: 2.2, repeat: Infinity }}
        style={{ transformOrigin: "140px 190px" }}
      />
    );
  }
  if (mood === "happy") {
    return (
      <path
        d="M104 164 Q140 202 176 164"
        fill="none"
        stroke="var(--flow-text)"
        strokeWidth="6"
        strokeLinecap="round"
      />
    );
  }
  if (mood === "listening") {
    return (
      <ellipse
        cx="140"
        cy="178"
        rx="9"
        ry="11"
        fill="none"
        stroke="var(--flow-text)"
        strokeWidth="5"
      />
    );
  }
  if (mood === "thinking") {
    return (
      <path
        d="M114 178 Q140 190 166 176"
        fill="none"
        stroke="var(--flow-text)"
        strokeWidth="5"
        strokeLinecap="round"
      />
    );
  }
  if (mood === "concerned") {
    return (
      <path
        d="M112 188 Q140 168 168 188"
        fill="none"
        stroke="var(--flow-text)"
        strokeWidth="5"
        strokeLinecap="round"
      />
    );
  }
  if (mood === "sleepy" || mood === "resting") {
    return (
      <path
        d="M122 180 Q140 186 158 180"
        fill="none"
        stroke="var(--flow-text)"
        strokeWidth="5"
        strokeLinecap="round"
      />
    );
  }
  return (
    <path
      d="M118 178 Q140 184 162 178"
      fill="none"
      stroke="var(--flow-text)"
      strokeWidth="5"
      strokeLinecap="round"
    />
  );
}
