import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  captureScreenshot,
  check,
  evaluate,
  finishReceipt,
  launchChrome,
  navigate,
  setViewport,
  waitForAppReady,
} from "./ui-verify-chrome.mjs";

const url = process.env.AIBI_UI_URL ?? "http://127.0.0.1:8686/?section=views";
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-visual-"));
const viewports = [
  { key: "landscape", label: "landscape", width: 1440, height: 900 },
  { key: "portrait", label: "portrait", width: 900, height: 1440 },
  { key: "square", label: "square", width: 1100, height: 1100 },
];

function visualMetrics() {
  const text = document.body?.innerText || "";
  const insideClosedDetails = (element) => {
    const details = element.closest("details");
    return Boolean(details && !details.open && element !== details.querySelector("summary") && !element.closest("summary"));
  };
  const visible = (element) => {
    if (insideClosedDetails(element)) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || "1") > 0.01 &&
      rect.width > 1 &&
      rect.height > 1 &&
      rect.bottom >= 0 &&
      rect.top <= window.innerHeight &&
      rect.right >= 0 &&
      rect.left <= window.innerWidth;
  };
  const pickText = (element) => {
    const tag = String(element.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return element.placeholder || element.value || "";
    return ((element.innerText || element.textContent || "").replace(/\s+/g, " ").trim());
  };
  const rectData = (element) => {
    if (!element) return null;
    const rect = element.getBoundingClientRect();
    return {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
      right: Math.round(rect.right),
      bottom: Math.round(rect.bottom),
    };
  };
  const textNodes = Array.from(document.querySelectorAll("button,a,label,span,strong,h1,h2,h3,p,small,dt,dd,summary,input,select,textarea"))
    .filter(visible)
    .map((element) => ({ element, text: pickText(element), rect: element.getBoundingClientRect(), style: getComputedStyle(element) }))
    .filter((item) => item.text.length > 0 && !item.element.closest(".agentFloatButton"));
  const skinnyText = textNodes
    .filter(({ text: itemText, rect }) => itemText.length > 8 && rect.width < 72)
    .slice(0, 12)
    .map(({ text: itemText, rect }) => ({ text: itemText, w: Math.round(rect.width), h: Math.round(rect.height), x: Math.round(rect.x), y: Math.round(rect.y) }));
  const clippingText = textNodes
    .filter(({ element, rect, style }) => {
      const overflowed = element.scrollWidth > element.clientWidth + 2 || element.scrollHeight > element.clientHeight + 2;
      return overflowed && (style.overflow === "hidden" || style.textOverflow === "ellipsis" || style.whiteSpace === "nowrap") && rect.width > 35;
    })
    .slice(0, 12)
    .map(({ text: itemText, rect }) => ({ text: itemText, w: Math.round(rect.width), h: Math.round(rect.height), x: Math.round(rect.x), y: Math.round(rect.y) }));
  const important = Array.from(document.querySelectorAll(".mainPanel button, .mainPanel input, .mainPanel summary, .agentCommandDock.floating, .viewQueryPanel, .viewListPanel, .businessPathStep"))
    .filter(visible)
    .map((element) => ({ element, text: pickText(element) || String(element.className || element.tagName), rect: element.getBoundingClientRect() }));
  const overlapPairs = [];
  for (let i = 0; i < important.length; i += 1) {
    for (let j = i + 1; j < important.length; j += 1) {
      const a = important[i];
      const b = important[j];
      if (a.element.contains(b.element) || b.element.contains(a.element)) continue;
      const x = Math.max(0, Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left));
      const y = Math.max(0, Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top));
      const area = x * y;
      if (area > 120) {
        overlapPairs.push({
          a: String(a.text).slice(0, 48),
          b: String(b.text).slice(0, 48),
          area: Math.round(area),
        });
      }
    }
  }
  const tableScroll = document.querySelector(".viewTableScroll");
  const table = tableScroll?.querySelector("table");
  const mainPanel = document.querySelector(".mainPanel");
  const contentShell = document.querySelector(".contentShell");
  const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
  return {
    title: document.title,
    url: location.href,
    connected: text.includes("数据服务已连接") || text.includes("Data service connected"),
    hasErrorBoundary,
    hasFrameworkOverlay: Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay")),
    samplesVisible: /样例|示例|demo data|test data|fallback source|mock data|lorem/i.test(text),
    overflow: {
      documentX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
      bodyX: Math.max(0, document.body.scrollWidth - window.innerWidth),
      mainPanelX: Boolean(mainPanel && mainPanel.scrollWidth > mainPanel.clientWidth + 2),
      contentShellX: Boolean(contentShell && contentShell.scrollWidth > contentShell.clientWidth + 2),
    },
    tableScroll: tableScroll ? {
      clientWidth: Math.round(tableScroll.clientWidth),
      scrollWidth: Math.round(tableScroll.scrollWidth),
      hasHorizontalScroll: tableScroll.scrollWidth > tableScroll.clientWidth + 2,
      columnCount: table ? table.querySelectorAll("th").length : 0,
    } : null,
    skinnyText,
    clippingText,
    overlapPairs,
    agentButton: rectData(document.querySelector(".agentFloatButton")),
  };
}

const checks = [];
const viewportResults = [];
let browserInfo = null;
const browserIssues = [];

try {
  for (const viewport of viewports) {
    let browser = null;
    try {
      browser = await launchChrome();
      browserInfo ??= { chromePath: browser.chromePath, chromeName: browser.chromeName };
      await setViewport(browser.client, viewport);
      await navigate(browser.client, url);
      const ready = await waitForAppReady(browser.client, null, 25000);
      const metrics = await evaluate(browser.client, visualMetrics, null, 10000);
      const screenshot = await captureScreenshot(browser.client, join(screenshotDir, `${viewport.key}-${viewport.width}x${viewport.height}.png`));
      const prefix = `visual-${viewport.key}`;
      checks.push(
        check(`${prefix}-ready`, ready.ok, { ready }),
        check(`${prefix}-no-error-boundary`, !metrics.hasErrorBoundary, { metrics: { hasErrorBoundary: metrics.hasErrorBoundary } }),
        check(`${prefix}-no-framework-overlay`, !metrics.hasFrameworkOverlay),
        check(`${prefix}-no-global-x-overflow`, metrics.overflow.documentX === 0 && metrics.overflow.bodyX === 0, { overflow: metrics.overflow }),
        check(`${prefix}-no-panel-x-overflow`, !metrics.overflow.mainPanelX && !metrics.overflow.contentShellX, { overflow: metrics.overflow }),
        check(`${prefix}-no-empty-table-horizontal-scroll`, !metrics.tableScroll?.hasHorizontalScroll, { tableScroll: metrics.tableScroll }),
        check(`${prefix}-no-visible-overlap`, metrics.overlapPairs.length === 0, { overlapPairs: metrics.overlapPairs }),
        check(`${prefix}-no-clipped-text`, metrics.clippingText.length === 0, { clippingText: metrics.clippingText }),
        check(`${prefix}-no-user-facing-sample-copy`, !metrics.samplesVisible),
      );
      viewportResults.push({
        viewport,
        ready,
        metrics,
        screenshot,
      });
    } finally {
      if (browser) {
        browserIssues.push({ viewport: viewport.key, issues: browser.client.consoleIssues() });
        await browser.close();
      }
    }
  }
} catch (error) {
  checks.push(check("ui-visual-runtime", false, { error: error instanceof Error ? error.message : String(error) }));
}

const receipt = finishReceipt({
  ok: false,
  generatedBy: "scripts/verify-ui-visual.mjs",
  url,
  browser: browserInfo,
  screenshotDir,
  browserIssues,
  viewportResults: viewportResults.map((result) => ({
    viewport: result.viewport,
    screenshot: result.screenshot,
    ready: result.ready,
    metrics: {
      connected: result.metrics.connected,
      overflow: result.metrics.overflow,
      tableScroll: result.metrics.tableScroll,
      skinnyTextCount: result.metrics.skinnyText.length,
      clippingTextCount: result.metrics.clippingText.length,
      overlapCount: result.metrics.overlapPairs.length,
      agentButton: result.metrics.agentButton,
    },
  })),
  checks,
});

console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
