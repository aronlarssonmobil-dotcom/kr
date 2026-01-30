import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";

type Props = {
  title: string;
  subtitle: string;
};

export const TradingIntro: React.FC<Props> = ({ title, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleScale = spring({
    frame,
    fps,
    from: 0.5,
    to: 1,
    config: { damping: 12 },
  });

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });

  const subtitleOpacity = interpolate(frame, [30, 60], [0, 1], {
    extrapolateRight: "clamp",
  });

  const lineWidth = interpolate(frame, [20, 80], [0, 500], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const glowPulse = Math.sin(frame * 0.1) * 0.3 + 0.7;

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(180deg, #0a0a0f 0%, #1a1a2e 100%)",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      {/* Grid background */}
      <svg
        style={{ position: "absolute", inset: 0, opacity: 0.3 }}
        width="100%"
        height="100%"
      >
        <defs>
          <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(0,212,255,0.1)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      {/* Glow effect */}
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          background: `radial-gradient(circle, rgba(0, 212, 255, ${0.15 * glowPulse}) 0%, transparent 60%)`,
          borderRadius: "50%",
          filter: "blur(80px)",
        }}
      />

      {/* Title */}
      <div
        style={{
          fontSize: 140,
          fontWeight: 800,
          color: "#fff",
          letterSpacing: 20,
          opacity: titleOpacity,
          transform: `scale(${titleScale})`,
          textShadow: `0 0 60px rgba(0, 212, 255, ${glowPulse}), 0 0 120px rgba(0, 212, 255, 0.4)`,
        }}
      >
        {title}
      </div>

      {/* Animated line */}
      <div
        style={{
          width: lineWidth,
          height: 4,
          background: "linear-gradient(90deg, transparent, #00d4ff, transparent)",
          marginTop: 40,
          marginBottom: 40,
          boxShadow: "0 0 30px rgba(0, 212, 255, 0.8)",
        }}
      />

      {/* Subtitle */}
      <div
        style={{
          fontSize: 36,
          color: "rgba(255, 255, 255, 0.7)",
          letterSpacing: 15,
          opacity: subtitleOpacity,
          textTransform: "uppercase",
        }}
      >
        {subtitle}
      </div>

      {/* Corner brackets */}
      {[
        { top: 50, left: 50, rotate: 0 },
        { top: 50, right: 50, rotate: 90 },
        { bottom: 50, left: 50, rotate: -90 },
        { bottom: 50, right: 50, rotate: 180 },
      ].map((pos, i) => {
        const delay = i * 8;
        const opacity = interpolate(frame, [delay, delay + 25], [0, 0.6], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              ...pos,
              width: 70,
              height: 70,
              borderLeft: "3px solid #00d4ff",
              borderTop: "3px solid #00d4ff",
              transform: `rotate(${pos.rotate}deg)`,
              opacity,
              boxShadow: "0 0 15px rgba(0, 212, 255, 0.5)",
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
