import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";

type Props = {
  ticker: string;
  prices: number[];
};

export const PriceAction: React.FC<Props> = ({ ticker, prices }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const chartWidth = width - 200;
  const chartHeight = 500;
  const chartTop = 300;
  const chartLeft = 100;

  const minPrice = Math.min(...prices) * 0.95;
  const maxPrice = Math.max(...prices) * 1.05;
  const priceRange = maxPrice - minPrice;

  const drawProgress = interpolate(frame, [30, 180], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const currentIdx = Math.min(Math.floor(drawProgress * prices.length), prices.length - 1);
  const currentPrice = prices[currentIdx];
  const priceChange = ((currentPrice - prices[0]) / prices[0]) * 100;
  const isPositive = priceChange >= 0;
  const accentColor = isPositive ? "#00ff88" : "#ff4757";

  const getX = (i: number) => chartLeft + (i / (prices.length - 1)) * chartWidth;
  const getY = (val: number) => chartTop + chartHeight - ((val - minPrice) / priceRange) * chartHeight;

  const visiblePoints = Math.ceil(drawProgress * prices.length);

  const linePath = prices
    .slice(0, visiblePoints)
    .map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i)} ${getY(p)}`)
    .join(" ");

  const areaPath = visiblePoints > 1
    ? `${linePath} L ${getX(visiblePoints - 1)} ${chartTop + chartHeight} L ${chartLeft} ${chartTop + chartHeight} Z`
    : "";

  const titleScale = spring({ frame, fps, from: 0.8, to: 1, config: { damping: 12 } });
  const titleOpacity = interpolate(frame, [0, 25], [0, 1], { extrapolateRight: "clamp" });

  const glowPulse = Math.sin(frame * 0.1) * 0.3 + 0.7;

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0a0a0f 0%, #151520 50%, #0a0a0f 100%)",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      {/* Grid */}
      <svg style={{ position: "absolute", inset: 0, opacity: 0.2 }} width="100%" height="100%">
        <defs>
          <pattern id="priceGrid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(0,212,255,0.1)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#priceGrid)" />
      </svg>

      {/* Glow */}
      <div
        style={{
          position: "absolute",
          top: "25%",
          left: "40%",
          width: 700,
          height: 400,
          background: `radial-gradient(ellipse, ${accentColor}15 0%, transparent 60%)`,
          filter: "blur(80px)",
        }}
      />

      {/* Header - Ticker */}
      <div
        style={{
          position: "absolute",
          top: 60,
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
            textShadow: `0 0 50px rgba(0, 212, 255, ${glowPulse})`,
            letterSpacing: 3,
          }}
        >
          {ticker}
        </div>
        <div style={{ fontSize: 20, color: "rgba(255,255,255,0.5)", letterSpacing: 4, marginTop: 6 }}>
          PRICE ACTION
        </div>
      </div>

      {/* Header - Price */}
      <div
        style={{
          position: "absolute",
          top: 60,
          right: 100,
          textAlign: "right",
          opacity: interpolate(frame, [20, 50], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        <div style={{ fontSize: 16, color: "rgba(255,255,255,0.4)", marginBottom: 6 }}>PRICE</div>
        <div style={{ fontSize: 56, fontWeight: 700, color: "#fff" }}>
          ${currentPrice.toLocaleString()}
        </div>
        <div style={{ fontSize: 28, fontWeight: 600, color: accentColor, marginTop: 6 }}>
          {isPositive ? "+" : ""}{priceChange.toFixed(2)}%
        </div>
      </div>

      {/* Chart */}
      <svg width={width} height={height} style={{ position: "absolute", top: 0, left: 0 }}>
        <defs>
          <linearGradient id="priceLineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={accentColor} />
            <stop offset="100%" stopColor="#00d4ff" />
          </linearGradient>
          <linearGradient id="priceAreaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={`${accentColor}35`} />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
          <filter id="priceGlow">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Horizontal grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((r) => (
          <line
            key={r}
            x1={chartLeft}
            y1={chartTop + chartHeight * r}
            x2={chartLeft + chartWidth}
            y2={chartTop + chartHeight * r}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />
        ))}

        {/* Vertical grid */}
        {prices.map((_, i) => (
          <line
            key={i}
            x1={getX(i)}
            y1={chartTop}
            x2={getX(i)}
            y2={chartTop + chartHeight}
            stroke="rgba(255,255,255,0.04)"
            strokeWidth={1}
          />
        ))}

        {/* Area */}
        {visiblePoints > 1 && <path d={areaPath} fill="url(#priceAreaGrad)" />}

        {/* Line */}
        {visiblePoints > 1 && (
          <path
            d={linePath}
            fill="none"
            stroke="url(#priceLineGrad)"
            strokeWidth={4}
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#priceGlow)"
          />
        )}

        {/* Current point */}
        {visiblePoints > 0 && (
          <>
            <circle
              cx={getX(visiblePoints - 1)}
              cy={getY(prices[visiblePoints - 1])}
              r={14 + Math.sin(frame * 0.15) * 4}
              fill={`${accentColor}25`}
            />
            <circle
              cx={getX(visiblePoints - 1)}
              cy={getY(prices[visiblePoints - 1])}
              r={7}
              fill={accentColor}
              filter="url(#priceGlow)"
            />
          </>
        )}
      </svg>

      {/* Price labels */}
      <div
        style={{
          position: "absolute",
          top: chartTop - 10,
          left: 25,
          height: chartHeight + 20,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          opacity: interpolate(frame, [25, 50], [0, 0.6], { extrapolateRight: "clamp" }),
        }}
      >
        {[maxPrice, (maxPrice + minPrice) / 2, minPrice].map((p, i) => (
          <div key={i} style={{ fontSize: 14, color: "rgba(255,255,255,0.5)" }}>
            ${p.toFixed(0)}
          </div>
        ))}
      </div>

      {/* Live indicator */}
      <div
        style={{
          position: "absolute",
          top: chartTop - 50,
          right: 100,
          display: "flex",
          alignItems: "center",
          gap: 10,
          opacity: interpolate(frame, [60, 90], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            backgroundColor: "#00ff88",
            boxShadow: `0 0 ${10 + Math.sin(frame * 0.2) * 5}px #00ff88`,
          }}
        />
        <span style={{ fontSize: 14, color: "rgba(255,255,255,0.6)", letterSpacing: 3 }}>LIVE</span>
      </div>
    </AbsoluteFill>
  );
};
