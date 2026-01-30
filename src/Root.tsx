import { Composition } from "remotion";
import { z } from "zod";
import { TradingVideo } from "./TradingVideo";
import { TradingIntro } from "./TradingIntro";
import { PriceAction } from "./PriceAction";

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
    </>
  );
};
