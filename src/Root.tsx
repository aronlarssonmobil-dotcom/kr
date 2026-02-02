import { Composition } from "remotion";
import { z } from "zod";
import { TradingVideo } from "./TradingVideo";
import { TradingIntro } from "./TradingIntro";
import { PriceAction } from "./PriceAction";
import { MarketHeatmap } from "./MarketHeatmap";

export const tradingVideoSchema = z.object({
  ticker: z.string(),
  priceChange: z.number(),
  currentPrice: z.number(),
});

export const tradingIntroSchema = z.object({
  title: z.string(),
  subtitle: z.string(),
});

export const priceActionSchema = z.object({
  ticker: z.string(),
  prices: z.array(z.number()),
});

export const marketHeatmapSchema = z.object({
  title: z.string(),
  assets: z.array(z.object({
    ticker: z.string(),
    name: z.string(),
    change: z.number(),
    marketCap: z.string(),
    size: z.enum(["large", "medium", "small"]),
  })),
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="TradingVideo"
        component={TradingVideo}
        schema={tradingVideoSchema}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          ticker: "BTC/USD",
          priceChange: 12.5,
          currentPrice: 67432.5,
        }}
      />
      <Composition
        id="TradingIntro"
        component={TradingIntro}
        schema={tradingIntroSchema}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          title: "MARKET UPDATE",
          subtitle: "Daily Trading Analysis",
        }}
      />
      <Composition
        id="PriceAction"
        component={PriceAction}
        schema={priceActionSchema}
        durationInFrames={240}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          ticker: "ETH/USD",
          prices: [2100, 2150, 2080, 2200, 2350, 2300, 2450, 2500],
        }}
      />
      <Composition
        id="MarketHeatmap"
        component={MarketHeatmap}
        schema={marketHeatmapSchema}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          title: "CRYPTO MARKET",
          assets: [
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
          ],
        }}
      />
    </>
  );
};
