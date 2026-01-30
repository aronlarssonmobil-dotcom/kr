import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from "remotion";

type Props = {
  ticker: string;
  priceChange: number;
  currentPrice: number;
};

export const TradingVideo: React.FC<Props> = ({ ticker, priceChange, currentPrice }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();

  const isPositive = priceChange >= 0;
  const accentColor = isPositive ? "#00ff88" : "#ff4757";

  const headerOpacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: "clamp",
  });

  const headerScale = spring({
    frame,
    fps,
    from: 0.8,
    to: 1,
    config: { damping: 15 },
  });

  const chartProgress = interpolate(frame, [40, 200], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Generate chart data
  const chartPoints = 40;
  const chartData = Array.from({ length: chartPoints }, (_, i) => {
    const trend = isPositive ? i * 0.5 : -i * 0.3;
    const wave = Math.sin(i * 0.4) * 15 + Math.cos(i * 0.2) * 10;
    return 200 + trend + wave;
  });

  const chartWidth = width - 200;
  const chartHeight = 400;
  const chartTop = 280;
  const chartLeft = 100;

  const minVal = Math.min(...chartData) - 20;
  const maxVal = Math.max(...chartData) + 20;
  const range = maxVal - minVal;

  const visiblePoints = Math.floor(chartProgress * chartPoints);

  const getY = (val: number) => chartTop + chartHeight - ((val - minVal) / range) * chartHeight;
  const getX = (i: number) => chartLeft + (i / (chartPoints - 1)) * chartWidth;

  const linePath = chartData
    .slice(0, visiblePoints)
    .map((val, i) => `${i === 0 ? "M" : "L"} ${getX(i)} ${getY(val)}`)
    .join(" ");

  const areaPath = visiblePoints > 1
    ? `${linePath} L ${getX(visiblePoints - 1)} ${chartTop + chartHeight} L ${chartLeft} ${chartTop + chartHeight} Z`
    : "";

  const glowPulse = Math.sin(frame * 0.08) * 0.3 + 0.7;

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #0f0f1a 100%)",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      {/* Grid */}
      <svg style={{ position: "absolute", inset: 0, opacity: 0.25 }} width="100%" height="100%">
        <defs>
          <pattern id="gridMain" width="80" height="80" patternUnits="userSpaceOnUse">
            <path d="M 80 0 L 0 0 0 80" fill="none" stroke="rgba(0,212,255,0.08)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#gridMain)" />
      </svg>

      {/* Glow orbs */}
      <div
        style={{
          position: "absolute",
          top: "15%",
          left: "5%",
          width: 500,
          height: 500,
          background: `radial-gradient(circle, rgba(0, 212, 255, ${0.12 * glowPulse}) 0%, transparent 60%)`,
          borderRadius: "50%",
          filter: "blur(80px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "5%",
          right: "10%",
          width: 400,
          height: 400,
          background: `radial-gradient(circle, ${isPositive ? "rgba(0, 255, 136, 0.1)" : "rgba(255, 71, 87, 0.1)"} 0%, transparent 60%)`,
          borderRadius: "50%",
          filter: "blur(60px)",
        }}
      />

      {/* Header - Ticker */}
      <Sequence from={0}>
        <div
          style={{
            position: "absolute",
            top: 70,
            left: 100,
            opacity: headerOpacity,
            transform: `scale(${headerScale})`,
          }}
        >
          <div
            style={{
              fontSize: 80,
              fontWeight: 800,
              color: "#00d4ff",
              textShadow: `0 0 40px rgba(0, 212, 255, ${glowPulse})`,
              letterSpacing: 4,
            }}
          >
            {ticker}
          </div>
          <div style={{ fontSize: 22, color: "rgba(255,255,255,0.5)", letterSpacing: 5, marginTop: 8 }}>
            LIVE TRADING ANALYSIS
          </div>
        </div>
      </Sequence>

      {/* Header - Price */}
      <Sequence from={15}>
        <div
          style={{
            position: "absolute",
            top: 70,
            right: 100,
            textAlign: "right",
            opacity: interpolate(frame, [15, 45], [0, 1], { extrapolateRight: "clamp" }),
          }}
        >
          <div style={{ fontSize: 18, color: "rgba(255,255,255,0.4)", marginBottom: 8 }}>CURRENT PRICE</div>
          <div style={{ fontSize: 64, fontWeight: 700, color: "#fff" }}>
            ${currentPrice.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: 32, fontWeight: 600, color: accentColor, marginTop: 8 }}>
            {isPositive ? "▲" : "▼"} {isPositive ? "+" : ""}{priceChange.toFixed(2)}%
          </div>
        </div>
      </Sequence>

      {/* Chart */}
      <Sequence from={40}>
        <svg width={width} height={1080} style={{ position: "absolute", top: 0, left: 0 }}>
          <defs>
            <linearGradient id="chartGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={accentColor} />
              <stop offset="100%" stopColor="#00d4ff" />
            </linearGradient>
            <linearGradient id="areaFill" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={`${accentColor}40`} />
              <stop offset="100%" stopColor="transparent" />
            </linearGradient>
            <filter id="lineGlow">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Chart grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((r) => (
            <line
              key={r}
              x1={chartLeft}
              y1={chartTop + chartHeight * r}
              x2={chartLeft + chartWidth}
              y2={chartTop + chartHeight * r}
              stroke="rgba(255,255,255,0.05)"
              strokeWidth={1}
            />
          ))}

          {/* Area */}
          {visiblePoints > 1 && <path d={areaPath} fill="url(#areaFill)" />}

          {/* Line */}
          {visiblePoints > 1 && (
            <path
              d={linePath}
              fill="none"
              stroke="url(#chartGradient)"
              strokeWidth={4}
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#lineGlow)"
            />
          )}

          {/* Current point */}
          {visiblePoints > 0 && (
            <>
              <circle
                cx={getX(visiblePoints - 1)}
                cy={getY(chartData[visiblePoints - 1])}
                r={16 + Math.sin(frame * 0.15) * 4}
                fill={`${accentColor}30`}
              />
              <circle
                cx={getX(visiblePoints - 1)}
                cy={getY(chartData[visiblePoints - 1])}
                r={8}
                fill={accentColor}
                filter="url(#lineGlow)"
              />
            </>
          )}
        </svg>
      </Sequence>

      {/* Stats row */}
      <Sequence from={80}>
        <div
          style={{
            position: "absolute",
            bottom: 100,
            left: 100,
            right: 100,
            display: "flex",
            gap: 30,
          }}
        >
          {[
            { label: "24H VOLUME", value: "$4.2B", change: "+12.5%" },
            { label: "MARKET CAP", value: "$1.3T", change: "+8.2%" },
            { label: "OPEN INTEREST", value: "$28.5B", change: "+5.7%" },
            { label: "FUNDING RATE", value: "0.015%", change: "" },
          ].map((stat, i) => {
            const delay = i * 10;
            const cardOpacity = interpolate(frame - 80, [delay, delay + 20], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const cardY = interpolate(frame - 80, [delay, delay + 20], [30, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            return (
              <div
                key={stat.label}
                style={{
                  flex: 1,
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 16,
                  padding: "28px 24px",
                  opacity: cardOpacity,
                  transform: `translateY(${cardY}px)`,
                }}
              >
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", letterSpacing: 2, marginBottom: 12 }}>
                  {stat.label}
                </div>
                <div style={{ fontSize: 36, fontWeight: 700, color: "#fff" }}>{stat.value}</div>
                {stat.change && (
                  <div style={{ fontSize: 18, fontWeight: 600, color: "#00ff88", marginTop: 8 }}>{stat.change}</div>
                )}
              </div>
            );
          })}
        </div>
      </Sequence>

      {/* Footer */}
      <Sequence from={120}>
        <div
          style={{
            position: "absolute",
            bottom: 35,
            left: 0,
            right: 0,
            textAlign: "center",
            opacity: interpolate(frame, [120, 150], [0, 0.5], { extrapolateRight: "clamp" }),
          }}
        >
          <span style={{ fontSize: 14, color: "rgba(255,255,255,0.4)", letterSpacing: 8 }}>
            POWERED BY ADVANCED ANALYTICS
          </span>
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};
