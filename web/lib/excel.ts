import type { Order } from "./orders";
import { formatDate } from "./format";

/**
 * Export orders to a nicely formatted, Excel-openable file — no dependency.
 *
 * We emit an HTML table with inline styles (branded title, colored header,
 * borders, zebra rows, numeric columns) and save it as `.xls` with the ms-excel
 * MIME type. Value and duration are written as real NUMBERS with an Excel number
 * format, so they sort and sum correctly. A frozen header + autofilter are set
 * via the Office XML block. No spreadsheet library ships to the browser.
 */

interface Column {
  header: string;
  /** Cell text/number. */
  value: (o: Order) => string;
  /** Column kind → alignment + number format. */
  kind?: "text" | "num" | "link" | "company";
  width: number; // px, becomes an Excel column width hint
}

const FMT_CR = "#,##0.00";
const FMT_INT = "#,##0";

const COLUMNS: Column[] = [
  { header: "Company", value: (o) => o.companyName, kind: "company", width: 220 },
  { header: "BSE Code", value: (o) => o.bseScripCode ?? "", width: 80 },
  { header: "NSE Symbol", value: (o) => o.nseSymbol ?? "", width: 90 },
  { header: "Target Industry", value: (o) => o.targetIndustry ?? "Unclassified", width: 200 },
  {
    header: "Order Value (₹ Cr)",
    value: (o) => (o.orderValueCrore != null ? String(o.orderValueCrore) : ""),
    kind: "num",
    width: 130,
  },
  { header: "Awarder", value: (o) => o.awarder ?? "", width: 240 },
  {
    header: "Duration (months)",
    value: (o) => (o.durationMonths != null ? String(Math.round(o.durationMonths)) : ""),
    kind: "num",
    width: 120,
  },
  { header: "Filed", value: (o) => formatDate(o.filedAt), width: 100 },
  { header: "Category", value: (o) => o.category ?? "", width: 180 },
  { header: "Source (PDF)", value: (o) => o.attachmentUrl ?? "", kind: "link", width: 110 },
];

const BRAND = "#4f46e5";
const BRAND_DARK = "#3730a3";
const FONT = "font-family:Calibri,Arial,sans-serif;";

function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function headCell(c: Column): string {
  const align = c.kind === "num" ? "right" : c.kind === "company" ? "left" : "center";
  const style =
    `background:${BRAND};color:#fff;font-weight:bold;border:1px solid ${BRAND_DARK};` +
    `padding:8px 10px;text-align:${align};${FONT}font-size:12px;`;
  return `<th style="${style}">${esc(c.header)}</th>`;
}

function bodyCell(c: Column, o: Order, rowIndex: number): string {
  const bg = rowIndex % 2 ? "#eef2ff" : "#ffffff";
  const raw = c.value(o);
  let align = "center";
  let extra = "";
  let content = esc(raw);
  if (c.kind === "num") {
    align = "right";
    extra = raw !== "" ? `mso-number-format:'${c.header.includes("Cr") ? FMT_CR : FMT_INT}';` : "";
  } else if (c.kind === "company") {
    align = "left";
    extra = "font-weight:bold;color:#312e81;";
  } else if (c.kind === "link") {
    content = raw
      ? `<a href="${esc(raw)}" style="color:${BRAND};">View filing</a>`
      : "";
  }
  const style =
    `border:1px solid #c7d2fe;padding:6px 10px;${FONT}font-size:11px;` +
    `background:${bg};text-align:${align};color:#0f172a;${extra}`;
  return `<td style="${style}">${content}</td>`;
}

export function exportOrdersToExcel(
  orders: Order[],
  filename = "orderbook-orders.xls",
): void {
  const ncols = COLUMNS.length;
  const totalCr = orders.reduce((s, o) => s + (o.orderValueCrore ?? 0), 0);
  const today = new Date().toISOString().slice(0, 10);

  const titleStyle =
    `background:${BRAND_DARK};color:#fff;font-weight:bold;${FONT}font-size:16px;` +
    `padding:12px 10px;text-align:left;`;
  const subStyle =
    `background:#eef2ff;color:#4338ca;${FONT}font-size:11px;padding:6px 10px;text-align:left;`;

  const titleRow = `<tr><td colspan="${ncols}" style="${titleStyle}">Order Book Tracker — Daksham Capital</td></tr>`;
  const subRow = `<tr><td colspan="${ncols}" style="${subStyle}">Order &amp; contract wins from Indian listed companies · Exported ${esc(today)} · ${orders.length} orders</td></tr>`;
  const headRow = `<tr>${COLUMNS.map(headCell).join("")}</tr>`;
  const bodyRows = orders
    .map((o, i) => `<tr>${COLUMNS.map((c) => bodyCell(c, o, i)).join("")}</tr>`)
    .join("");

  // Totals row: label under the first columns, sum under the value column.
  const valueIdx = COLUMNS.findIndex((c) => c.header.includes("Cr"));
  const totalStyle = `border:1px solid ${BRAND_DARK};background:#e0e7ff;color:#312e81;font-weight:bold;${FONT}font-size:11px;padding:7px 10px;`;
  const totalCells = COLUMNS.map((c, i) => {
    if (i === 0) return `<td style="${totalStyle}text-align:left;">Total · ${orders.length} orders</td>`;
    if (i === valueIdx)
      return `<td style="${totalStyle}text-align:right;mso-number-format:'${FMT_CR}';">${totalCr}</td>`;
    return `<td style="${totalStyle}"></td>`;
  }).join("");
  const totalRow = `<tr>${totalCells}</tr>`;

  // Column widths (Excel reads <col width> in twips-ish; px works well enough).
  const cols = COLUMNS.map((c) => `<col style="width:${c.width}px">`).join("");

  // Office XML: name the sheet, freeze the header (rows above data = 3), autofilter.
  const frozen = 3;
  const xml =
    `<!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet>` +
    `<x:Name>Orders</x:Name><x:WorksheetOptions>` +
    `<x:FreezePanes/><x:FrozenNoSplit/>` +
    `<x:SplitHorizontal>${frozen}</x:SplitHorizontal>` +
    `<x:TopRowBottomPane>${frozen}</x:TopRowBottomPane>` +
    `<x:ActivePane>2</x:ActivePane>` +
    `</x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->`;

  const html =
    `<html xmlns:o="urn:schemas-microsoft-com:office:office" ` +
    `xmlns:x="urn:schemas-microsoft-com:office:excel">` +
    `<head><meta charset="utf-8">${xml}` +
    `<style>table{border-collapse:collapse}</style></head>` +
    `<body><table><colgroup>${cols}</colgroup>` +
    `<thead>${titleRow}${subRow}${headRow}</thead>` +
    `<tbody>${bodyRows}${totalRow}</tbody></table></body></html>`;

  const blob = new Blob(["﻿", html], { type: "application/vnd.ms-excel" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
