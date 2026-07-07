/**
 * MOCK DATA — placeholder only.
 *
 * These orders are hand-written examples so the scaffold renders something
 * realistic. In later steps this is replaced by real rows read from Cloudflare
 * D1 (via the `DB` binding) that the Python ingestion pipeline writes.
 *
 * The five extracted fields per order are:
 *   value · awarder · duration · targetIndustry · description
 * plus a link to the original filing (sourceUrl) — every data point stays
 * source- and evidence-backed.
 */

export type AccentColor =
  | "indigo"
  | "emerald"
  | "amber"
  | "rose"
  | "sky"
  | "violet";

export interface Order {
  id: string;
  /** Company that received / disclosed the order. */
  company: string;
  /** Ticker or scrip code shown as a small badge. */
  ticker: string;
  /** Contract / order value, pre-formatted for display. */
  value: string;
  /** Who placed the order (customer / awarding entity). */
  awarder: string;
  /** Execution timeline of the order. */
  duration: string;
  /** Sector the order targets. */
  targetIndustry: string;
  /** One-line summary of the order. */
  description: string;
  /** Link to the original BSE filing / attachment (evidence). */
  sourceUrl: string;
  /** Where the data was extracted from (shown on the card). */
  sourceLabel: string;
  /** Filing date (ISO string). */
  filedAt: string;
  /** Accent color used for this card's highlights. */
  accent: AccentColor;
}

export const mockOrders: Order[] = [
  {
    id: "mock-1",
    company: "Larsen & Toubro",
    ticker: "LT",
    value: "₹2,900 Cr",
    awarder: "Ministry of Road Transport & Highways",
    duration: "36 months",
    targetIndustry: "Infrastructure",
    description:
      "EPC order to build a 4-lane access-controlled expressway package, including major bridges and interchanges.",
    sourceUrl: "https://www.bseindia.com/",
    sourceLabel: "BSE announcement (PDF)",
    filedAt: "2026-07-06",
    accent: "indigo",
  },
  {
    id: "mock-2",
    company: "Bharat Heavy Electricals",
    ticker: "BHEL",
    value: "₹1,240 Cr",
    awarder: "NTPC Ltd.",
    duration: "28 months",
    targetIndustry: "Power & Energy",
    description:
      "Supply and installation of flue-gas desulphurisation (FGD) systems across two thermal power units.",
    sourceUrl: "https://www.bseindia.com/",
    sourceLabel: "BSE announcement (PDF)",
    filedAt: "2026-07-05",
    accent: "emerald",
  },
  {
    id: "mock-3",
    company: "Rail Vikas Nigam",
    ticker: "RVNL",
    value: "₹785 Cr",
    awarder: "Central Railway",
    duration: "24 months",
    targetIndustry: "Railways",
    description:
      "Design and construction of railway electrification and automatic signalling upgrades on a busy trunk route.",
    sourceUrl: "https://www.bseindia.com/",
    sourceLabel: "BSE announcement (PDF)",
    filedAt: "2026-07-03",
    accent: "amber",
  },
];

export interface Stat {
  label: string;
  value: string;
  delta: string;
  /** Whether the delta is a positive trend. */
  positive: boolean;
  accent: AccentColor;
}

export const mockStats: Stat[] = [
  {
    label: "Orders tracked",
    value: "128",
    delta: "+12 this week",
    positive: true,
    accent: "indigo",
  },
  {
    label: "Total order value",
    value: "₹18,420 Cr",
    delta: "+₹3,100 Cr",
    positive: true,
    accent: "emerald",
  },
  {
    label: "Companies covered",
    value: "37",
    delta: "+3 new",
    positive: true,
    accent: "violet",
  },
  {
    label: "Latest filing",
    value: "Today",
    delta: "6 Jul 2026",
    positive: true,
    accent: "rose",
  },
];
