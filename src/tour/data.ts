import cars from "./cars.json";
export const CARS = cars;
export type Car = (typeof CARS)[number];
export type Point = [number, number];
export interface Road {
  id: number;
  name: string;
  kind: string;
  points: Point[];
  width: number;
  foot: boolean;
  bridge: boolean;
  tunnel: boolean;
  layer?: number;
  oneway?: string;
}
export interface Building {
  id: number;
  name: string;
  points: Point[];
  height: number;
  heightSource: string;
  kind: string;
}
export interface Route {
  id: string;
  name: string;
  subtitle: string;
  description: string;
  focus: string;
  speed: number;
  points: Point[];
  length: number;
  sourceWays: number[];
  directed: boolean;
  closed?: boolean;
  elevations?: number[];
  segmentWays?: number[];
  tunnels?: { start: number; end: number; depth: number; name: string }[];
}
export interface City {
  origin: Point;
  attribution: string;
  buildings: Building[];
  parks: { id: number; name: string; points: Point[] }[];
  roads: Road[];
  water: { id: number; points: Point[] }[];
  routes: Route[];
  legacyRoutes?: Route[];
}
export function project(lon: number, lat: number): Point {
  return [
    (lon - 121.494) * Math.cos((31.239 * Math.PI) / 180) * 111320,
    -(lat - 31.239) * 111320,
  ];
}
export const LANDMARKS = [
  {
    id: "pearl",
    name: "东方明珠",
    lon: 121.495265,
    lat: 31.2418972,
    way: 40778038,
    heading: 0,
    height: 468,
    about:
      "三个大球体串起浦东的城市记忆。沿陆家嘴环路，可从不同角度观察塔身与江岸的关系。",
  },
  {
    id: "shanghai-tower",
    name: "上海中心大厦",
    lon: 121.5012688,
    lat: 31.2355923,
    way: 165792123,
    heading: 0,
    height: 632,
    about:
      "632 米的螺旋轮廓，是陆家嘴天际线的最高点。外层玻璃随高度旋转，逐渐收束。",
  },
  {
    id: "financial-center",
    name: "上海环球金融中心",
    lon: 121.5029934,
    lat: 31.2365912,
    way: 10691100,
    heading: 0.36,
    height: 492,
    about: "顶部的梯形开口与两侧清晰的轮廓，让这座摩天楼很容易辨认。",
  },
  {
    id: "jinmao",
    name: "金茂大厦",
    lon: 121.5013931,
    lat: 31.2372638,
    way: 376075961,
    heading: 0.36,
    height: 420.5,
    about:
      "逐级收分的塔身借鉴传统塔式建筑，在玻璃幕墙之间保留了层层叠起的节奏。",
  },
  {
    id: "peace-hotel",
    name: "和平饭店",
    lon: 121.48503,
    lat: 31.24109,
    way: -23763660,
    heading: -Math.PI / 2,
    height: 77,
    about:
      "铜绿色金字塔屋顶是外滩最醒目的标志之一。沿江行驶，石材立面与屋顶会依次进入视野。",
  },
  {
    id: "customs-house",
    name: "江海关大楼",
    lon: 121.485423,
    lat: 31.2386295,
    way: 178407318,
    heading: -Math.PI / 2,
    height: 79,
    about:
      "钟楼高出沿江的历史建筑群。立面的柱廊、窗格和台阶，构成外滩熟悉的街景。",
  },
  {
    id: "hsbc-bund",
    name: "原汇丰银行大楼",
    lon: 121.48534495,
    lat: 31.23796275,
    way: -23809960,
    heading: -Math.PI / 2,
    height: 60,
    about:
      "宽阔的石砌立面、柱廊与中央穹顶，形成外滩建筑群中格外平稳的水平轮廓。",
  },
  {
    id: "bank-china",
    name: "中国银行大楼",
    lon: 121.4852492,
    lat: 31.2415246,
    way: 177995050,
    heading: -Math.PI / 2,
    height: 69,
    about: "带有传统屋顶意向的高层建筑，与相邻的和平饭店共同勾勒出外滩北段。",
  },
  {
    id: "palace-hotel",
    name: "和平饭店南楼",
    lon: 121.4847803,
    lat: 31.2406195,
    way: 177998982,
    heading: -Math.PI / 2,
    height: 42,
    about: "原汇中饭店的转角与屋顶细部，延续了外滩街区的历史尺度。",
  },
] as const;
export type Landmark = (typeof LANDMARKS)[number];
export async function loadCity(): Promise<City> {
  const r = await fetch("/tour-city.json");
  if (!r.ok) throw new Error("地图加载失败");
  return r.json();
}
