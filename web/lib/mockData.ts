import type { Order } from "./orders";

/**
 * Accent colors for the design system (cards, badges, stat tiles).
 * Card accents are assigned in the UI, not stored in the DB.
 */
export type AccentColor =
  | "indigo"
  | "emerald"
  | "amber"
  | "rose"
  | "sky"
  | "violet";

/**
 * DEMO fallback orders — used by getOrders() ONLY when the D1 `DB` binding
 * isn't available (e.g. plain `next dev` without the Cloudflare context), so
 * the dashboard still renders. Real rows come from D1 (see db/seed.sql for the
 * seeded demo data, and Steps 3-5 for real ingestion). Shape matches `Order`.
 */
export const mockOrders: Order[] = [
  {
    id: 1,
    companyName: "Larsen & Toubro",
    bseScripCode: "500510",
    nseSymbol: "LT",
    isin: "INE018A01030",
    orderValueText: "INR 2,900.00 Crore",
    orderValueCrore: 2900,
    awarder: "Ministry of Road Transport & Highways",
    durationText: "36.0 Months",
    durationMonths: 36,
    targetIndustry: "Infrastructure - Roads",
    description:
      "EPC order to build a 4-lane access-controlled expressway package, including major bridges and interchanges.",
    exchange: "BSE",
    category: "Award of Order / Receipt of Order",
    headline: "L&T wins Rs 2,900 crore expressway EPC order (demo fallback)",
    attachmentUrl: "https://www.bseindia.com/",
    sourceLabel: "BSE Filing",
    extractionConfidence: 0.93,
    extractionModel: "gpt-4o",
    bseAnnouncementId: "MOCK-LT-1",
    dedupKey: "MOCK-LT-1",
    filedAt: "2026-07-06T10:00:00Z",
    createdAt: "2026-07-06T10:05:00Z",
    updatedAt: "2026-07-06T10:05:00Z",
  },
  {
    id: 2,
    companyName: "Bharat Heavy Electricals",
    bseScripCode: "500103",
    nseSymbol: "BHEL",
    isin: "INE257A01026",
    orderValueText: "INR 1,240.00 Crore",
    orderValueCrore: 1240,
    awarder: "NTPC Ltd.",
    durationText: "28.0 Months",
    durationMonths: 28,
    targetIndustry: "Capital Goods - Electrical Equipment",
    description:
      "Supply and installation of flue-gas desulphurisation (FGD) systems across two thermal power units.",
    exchange: "BSE",
    category: "Award of Order / Receipt of Order",
    headline: "BHEL bags Rs 1,240 crore FGD order from NTPC (demo fallback)",
    attachmentUrl: "https://www.bseindia.com/",
    sourceLabel: "BSE Filing",
    extractionConfidence: 0.94,
    extractionModel: "gpt-4o",
    bseAnnouncementId: "MOCK-BHEL-1",
    dedupKey: "MOCK-BHEL-1",
    filedAt: "2026-07-05T09:30:00Z",
    createdAt: "2026-07-05T09:35:00Z",
    updatedAt: "2026-07-05T09:35:00Z",
  },
  {
    id: 3,
    companyName: "Rail Vikas Nigam",
    bseScripCode: "542649",
    nseSymbol: "RVNL",
    isin: "INE415G01027",
    orderValueText: "INR 785.00 Crore",
    orderValueCrore: 785,
    awarder: "Central Railway",
    durationText: "24.0 Months",
    durationMonths: 24,
    targetIndustry: "Infrastructure - Railways",
    description:
      "Design and construction of railway electrification and automatic signalling upgrades on a busy trunk route.",
    exchange: "BSE",
    category: "Award of Order / Receipt of Order",
    headline: "RVNL secures Rs 785 crore railway electrification order (demo fallback)",
    attachmentUrl: "https://www.bseindia.com/",
    sourceLabel: "BSE Filing",
    extractionConfidence: 0.89,
    extractionModel: "gpt-4o",
    bseAnnouncementId: "MOCK-RVNL-1",
    dedupKey: "MOCK-RVNL-1",
    filedAt: "2026-07-03T13:15:00Z",
    createdAt: "2026-07-03T13:20:00Z",
    updatedAt: "2026-07-03T13:20:00Z",
  },
];
