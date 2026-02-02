import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";

type Asset = {
  ticker: string;
  name: string;
  change: number;
  marketCap: string;
  size: "large" | "medium" | "small";
};

type Props = {
  title: string;
  assets: Asset[];
};

const defaultAssets: Asset[] = [
  { ticker: "BTC", name: "Bitcoin", change: 5.42, marketCap: "$1.3T", size: "large" },
  { ticker: "ETH", name: "Ethereum", change: 3.21, marketCap: "$420B", size: "large" },
  { ticker: "SOL", name: "Solana", change: -2.15, marketCap: "$89B", size: "medium" },
  { ticker: "BNB", name: "Binance", change: 1.87, marketCap: "$95B", size: "medium" },
  { ticker: "XRP", name: "Ripple", change: -4.32, marketCap: "$67B", size: "medium" },
  { ticker: "ADA", name: "Cardano", change: 7.65, marketCap: "$45B", size: "medium" },
  { ticker: "AVAX", name: "Avalanche", change: -1.23, marketCap: "$28B", size: "small" },
  { ticker: "DOT", name: "Polkadot", change: 2.98, marketCap: "$22B", size: "small" },
  { ticker: "MATIC", name: "Polygon", change: -3.45, marketCap: "$18B", size: "small" },
  { ticker: "LINK", name: "Chainlink", change: 4.12, marketCap: "$15B", size: "small" },
  { ticker: "ATOM", name: "Cosmos", change: -0.87, marketCap: "$12B", size: "small" },
  { ticker: "UNI", name: "Uniswap", change: 6.23, marketCap: "$9B", size: "small" },
];

export const MarketHeatmap: React.FC<Props> = ({ title, assets = defaultAssets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const glowPulse = Math.sin(frame * 0.06) * 0.3 + 0.7;

  const titleOpacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" });
  const titleScale = spring({ frame, fps, from: 0.9, to: 1, config: { damping: 12 } });

  const getColor = (change: number, opacity: number = 1) => {
    if (change >= 5) return `rgba(0, 255, 136, ${opacity})`;
    if (change >= 2) return `rgba(0, 200, 100, ${opacity})`;
    if (change >= 0) return `rgba(80, 180, 100, ${opacity})`;
    if (change >= -2) return `rgba(200, 100, 80, ${opacity})`;
    if (change >= -5) return `rgba(255, 100, 80, ${opacity})`;
    return `rgba(255, 71, 87, ${opacity})`;
  };

  const getSize = (size: "large" | "medium" | "small") => {
    switch (size) {
      case "large": return { width: 380, height: 280 };
      case "medium": return { width: 280, height: 200 };
      case "small": return { width: 200, height: 150 };
    }
  };

  // Grid layout positions
  const positions = [
    // Large tiles (top row)
    { x: 100, y: 180 },
    { x: 500, y: 180 },
    // Medium tiles (second row)
    { x: 900, y: 180 },
    { x: 1200, y: 180 },
    { x: 900, y: 400 },
    { x: 1200, y: 400 },
    // Small tiles (bottom area)
    { x: 100, y: 480 },
    { x: 320, y: 480 },
    { x: 540, y: 480 },
    { x: 100, y: 650 },
    { x: 320, y: 650 },
    { x: 540, y: 650 },
  ];

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(145deg, #08080c 0%, #0f1018 50%, #0a0a10 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        overflow: "hidden",
      }}
    >
      {/* Animated grid background */}
      <svg style={{ position: "absolute", inset: 0, opacity: 0.15 }} width="100%" height="100%">
        <defs>
          <pattern id="heatmapGrid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(0,212,255,0.15)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#heatmapGrid)" />
      </svg>

      {/* Ambient glow orbs */}
      <div
        style={{
          position: "absolute",
          top: "10%",
          left: "20%",
          width: 600,
          height: 600,
          background: `radial-gradient(circle, rgba(0, 255, 136, ${0.08 * glowPulse}) 0%, transparent 70%)`,
          borderRadius: "50%",
          filter: "blur(100px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "10%",
          right: "20%",
          width: 500,
          height: 500,
          background: `radial-gradient(circle, rgba(255, 71, 87, ${0.08 * glowPulse}) 0%, transparent 70%)`,
          borderRadius: "50%",
          filter: "blur(80px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: 800,
          height: 800,
          background: `radial-gradient(circle, rgba(0, 212, 255, ${0.05 * glowPulse}) 0%, transparent 60%)`,
          borderRadius: "50%",
          filter: "blur(120px)",
        }}
      />

      {/* Title */}
      <div
        style={{
          position: "absolute",
          top: 50,
          left: 100,
          opacity: titleOpacity,
          transform: `scale(${titleScale})`,
        }}
      >
        <div
          style={{
            fontSize: 72,
            fontWeight: 800,
            color: "#fff",
            textShadow: `0 0 60px rgba(0, 212, 255, ${glowPulse * 0.8})`,
            letterSpacing: 4,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: 20,
            color: "rgba(255,255,255,0.4)",
            letterSpacing: 8,
            marginTop: 8,
          }}
        >
          REAL-TIME MARKET OVERVIEW
        </div>
      </div>

      {/* Live indicator */}
      <div
        style={{
          position: "absolute",
          top: 70,
          right: 100,
          display: "flex",
          alignItems: "center",
          gap: 12,
          opacity: interpolate(frame, [20, 50], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "#00ff88",
            boxShadow: `0 0 ${20 + Math.sin(frame * 0.15) * 10}px #00ff88`,
          }}
        />
        <span style={{ fontSize: 18, color: "#00ff88", letterSpacing: 4, fontWeight: 600 }}>LIVE</span>
      </div>

      {/* Heatmap tiles */}
      {assets.slice(0, 12).map((asset, i) => {
        const pos = positions[i] || { x: 100, y: 100 };
        const size = getSize(asset.size);
        const delay = i * 8;

        const tileOpacity = interpolate(frame, [30 + delay, 50 + delay], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        const tileScale = spring({
          frame: Math.max(0, frame - 30 - delay),
          fps,
          from: 0.8,
          to: 1,
          config: { damping: 15, stiffness: 100 },
        });

        const tileY = interpolate(frame, [30 + delay, 55 + delay], [40, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        const isPositive = asset.change >= 0;
        const color = getColor(asset.change);
        const bgColor = getColor(asset.change, 0.15);
        const borderColor = getColor(asset.change, 0.4);

        const tilePulse = Math.sin(frame * 0.08 + i * 0.5) * 0.1 + 0.9;

        return (
          <div
            key={asset.ticker}
            style={{
              position: "absolute",
              left: pos.x,
              top: pos.y,
              width: size.width,
              height: size.height,
              background: `linear-gradient(135deg, ${bgColor} 0%, rgba(20,20,30,0.9) 100%)`,
              border: `2px solid ${borderColor}`,
              borderRadius: 20,
              padding: 24,
              opacity: tileOpacity,
              transform: `scale(${tileScale}) translateY(${tileY}px)`,
              boxShadow: `0 0 ${40 * tilePulse}px ${getColor(asset.change, 0.3)}, inset 0 0 60px rgba(0,0,0,0.5)`,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              overflow: "hidden",
            }}
          >
            {/* Animated shine effect */}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: interpolate(frame, [30 + delay, 80 + delay], [-100, size.width + 100], {
                  extrapolateRight: "clamp",
                }),
                width: 100,
                height: "100%",
                background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)",
                transform: "skewX(-20deg)",
              }}
            />

            {/* Content */}
            <div>
              <div
                style={{
                  fontSize: asset.size === "large" ? 42 : asset.size === "medium" ? 32 : 24,
                  fontWeight: 800,
                  color: "#fff",
                  textShadow: `0 0 20px ${color}`,
                }}
              >
                {asset.ticker}
              </div>
              <div
                style={{
                  fontSize: asset.size === "large" ? 16 : 13,
                  color: "rgba(255,255,255,0.5)",
                  marginTop: 4,
                }}
              >
                {asset.name}
              </div>
            </div>

            <div>
              <div
                style={{
                  fontSize: asset.size === "large" ? 48 : asset.size === "medium" ? 36 : 28,
                  fontWeight: 700,
                  color: color,
                  textShadow: `0 0 30px ${getColor(asset.change, 0.6)}`,
                }}
              >
                {isPositive ? "+" : ""}{asset.change.toFixed(2)}%
              </div>
              <div
                style={{
                  fontSize: asset.size === "large" ? 16 : 13,
                  color: "rgba(255,255,255,0.4)",
                  marginTop: 4,
                }}
              >
                MCap: {asset.marketCap}
              </div>
            </div>

            {/* Mini chart indicator */}
            <svg
              style={{
                position: "absolute",
                bottom: 20,
                right: 20,
                opacity: 0.4,
              }}
              width={asset.size === "large" ? 80 : 50}
              height={asset.size === "large" ? 40 : 25}
            >
              <path
                d={isPositive
                  ? "M 0 35 Q 20 30 40 20 T 80 5"
                  : "M 0 5 Q 20 15 40 25 T 80 35"}
                fill="none"
                stroke={color}
                strokeWidth={3}
                strokeLinecap="round"
              />
            </svg>
          </div>
        );
      })}

      {/* Bottom stats bar */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          left: 100,
          right: 100,
          display: "flex",
          justifyContent: "space-between",
          opacity: interpolate(frame, [120, 150], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        {[
          { label: "TOTAL MARKET CAP", value: "$2.8T" },
          { label: "24H VOLUME", value: "$156B" },
          { label: "BTC DOMINANCE", value: "52.4%" },
          { label: "FEAR & GREED", value: "72 GREED" },
        ].map((stat, i) => (
          <div key={stat.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", letterSpacing: 3 }}>
              {stat.label}
            </div>
            <div
              style={{
                fontSize: 28,
                fontWeight: 700,
                color: "#fff",
                marginTop: 8,
                textShadow: "0 0 20px rgba(0,212,255,0.3)",
              }}
            >
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Scan line effect */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          height: 2,
          top: interpolate(frame % 180, [0, 180], [0, 1080]),
          background: "linear-gradient(90deg, transparent, rgba(0,212,255,0.3), transparent)",
          boxShadow: "0 0 20px rgba(0,212,255,0.5)",
        }}
      />
    </AbsoluteFill>
  );
};
