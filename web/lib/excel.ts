import type { Order } from "./orders";
import { formatDate, formatValue, formatDuration } from "./format";

/**
 * Export orders to a formatted, Excel-openable file — no dependency.
 *
 * We emit an HTML table with inline styles (colored header, borders, zebra
 * rows) and save it as `.xls` with the ms-excel MIME type. Excel renders the
 * inline styling, giving a colorful, bordered sheet without shipping a
 * spreadsheet library to the browser.
 */

const HEADERS = [
  "Company",
  "BSE Code",
  "NSE Symbol",
  "Filed Date",
  "Order Value",
  "Awarder",
  "Duration",
  "Target Industry",
  "Source (PDF)",
] as const;

function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function rowValues(o: Order): string[] {
  return [
    o.companyName,
    o.bseScripCode ?? "",
    o.nseSymbol ?? "",
    formatDate(o.filedAt),
    formatValue(o),
    o.awarder ?? "",
    formatDuration(o),
    o.targetIndustry ?? "Unclassified",
    o.attachmentUrl ?? "",
  ];
}

const HEAD_STYLE =
  "background:#4f46e5;color:#ffffff;font-weight:bold;border:1px solid #3730a3;" +
  "padding:8px 10px;text-align:center;font-family:Calibri,Arial,sans-serif;font-size:12px;";

function cellStyle(rowIndex: number, first: boolean): string {
  const bg = rowIndex % 2 ? "#eef2ff" : "#ffffff";
  const align = first
    ? "text-align:left;font-weight:bold;color:#312e81;"
    : "text-align:center;color:#0f172a;";
  return (
    `border:1px solid #c7d2fe;padding:6px 10px;` +
    `font-family:Calibri,Arial,sans-serif;font-size:11px;background:${bg};${align}`
  );
}

export function exportOrdersToExcel(
  orders: Order[],
  filename = "orderbook-orders.xls",
): void {
  const thead = `<tr>${HEADERS.map((h) => `<th style="${HEAD_STYLE}">${esc(h)}</th>`).join("")}</tr>`;
  const tbody = orders
    .map(
      (o, i) =>
        `<tr>${rowValues(o)
          .map((c, ci) => `<td style="${cellStyle(i, ci === 0)}">${esc(c)}</td>`)
          .join("")}</tr>`,
    )
    .join("");

  const html =
    `<html xmlns:o="urn:schemas-microsoft-com:office:office" ` +
    `xmlns:x="urn:schemas-microsoft-com:office:excel">` +
    `<head><meta charset="utf-8"><style>table{border-collapse:collapse}</style></head>` +
    `<body><table><thead>${thead}</thead><tbody>${tbody}</tbody></table></body></html>`;

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
