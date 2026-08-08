import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import {
  captureScreenshot,
  check,
  evaluate,
  finishReceipt,
  launchChrome,
  navigate,
  setViewport,
  waitFor,
} from "./ui-verify-chrome.mjs";
import { withTemporaryWorkspace } from "./ui-verify-workspace.mjs";

const baseUrl = process.env.AIBI_UI_BASE_URL ?? "http://127.0.0.1:8787";
const url = process.env.AIBI_UI_URL ?? `${baseUrl}/?section=home`;
const screenshotDir = resolve(process.env.AIBI_UI_SCREENSHOT_DIR ?? join("tmp", "qa", "responsive-typography"));
const receiptPath = join(screenshotDir, "receipt.json");
const viewports = [
  { key: "portrait-floor", label: "portrait floor", width: 720, height: 1280, orientation: "portrait", mode: "responsive" },
  { key: "portrait-under-floor", label: "portrait one pixel under floor", width: 719, height: 1280, orientation: "portrait", mode: "scaled" },
  { key: "portrait-half", label: "portrait half-scale", width: 360, height: 640, orientation: "portrait", mode: "scaled" },
  { key: "landscape-floor", label: "landscape floor", width: 1280, height: 720, orientation: "landscape", mode: "responsive" },
  { key: "landscape-under-floor", label: "landscape one pixel under floor", width: 1280, height: 719, orientation: "landscape", mode: "scaled" },
  { key: "landscape-half", label: "landscape half-scale", width: 640, height: 360, orientation: "landscape", mode: "scaled" },
  { key: "landscape-letterbox", label: "landscape non-16:9 scale", width: 800, height: 600, orientation: "landscape", mode: "scaled" },
  { key: "portrait-daily", label: "portrait daily", width: 900, height: 1440, orientation: "portrait", mode: "responsive" },
  { key: "common-laptop", label: "common laptop", width: 1366, height: 768, orientation: "landscape", mode: "responsive" },
  { key: "wide-desktop", label: "wide desktop", width: 1440, height: 900, orientation: "landscape", mode: "responsive" },
];

mkdirSync(screenshotDir, { recursive: true });

function collectCssFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return collectCssFiles(path);
    return entry.isFile() && entry.name.endsWith(".css") ? [path] : [];
  });
}

function responsiveSourceGuard() {
  const root = resolve("src");
  const viewportMedia = [];
  const viewportUnits = [];
  for (const file of collectCssFiles(root)) {
    const relative = file.slice(root.length + 1).replaceAll("\\", "/");
    const lines = readFileSync(file, "utf8").split(/\r?\n/);
    let activeSelector = "";
    lines.forEach((line, index) => {
      const trimmed = line.trim();
      if (trimmed.endsWith("{")) activeSelector = trimmed.slice(0, -1).trim();
      if (/@media\s*\([^)]*(?:max|min)-(?:width|height)\s*:/.test(line)) {
        viewportMedia.push({ file: relative, line: index + 1, source: line.trim() });
      }
      const units = line.match(/(?:\d*\.?\d+)(?:dvh|dvw|svh|svw|lvh|lvw|vh|vw|vmin|vmax)\b/g) ?? [];
      const isPhysicalFrameUnit = relative === "styles.css"
        && units.length === 1
        && units[0] === "100dvh"
        && ((activeSelector === "body" && /min-height:\s*100dvh/.test(line))
          || (activeSelector === ".viewportScaleFrame" && /height:\s*100dvh/.test(line)));
      if (units.length && !isPhysicalFrameUnit) {
        viewportUnits.push({ file: relative, line: index + 1, source: line.trim(), units });
      }
      if (trimmed === "}") activeSelector = "";
    });
  }
  return { viewportMedia, viewportUnits };
}

function typographyMetrics() {
  const preciseNumber = (value) => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const number = (value) => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? Math.round(parsed * 100) / 100 : null;
  };
  const frame = document.querySelector('[data-testid="viewport-scale-frame"]');
  const surface = document.querySelector('[data-testid="viewport-scale-surface"]');
  const viewportState = document.documentElement.dataset;
  const scale = preciseNumber(viewportState.viewportScale) ?? 1;
  const surfaceRect = surface?.getBoundingClientRect();
  const logicalRect = (element) => {
    const rect = element?.getBoundingClientRect();
    if (!rect || !surfaceRect) return null;
    return {
      x: number((rect.left - surfaceRect.left) / scale),
      y: number((rect.top - surfaceRect.top) / scale),
      width: number(rect.width / scale),
      height: number(rect.height / scale),
    };
  };
  const measure = (selector) => {
    const element = document.querySelector(selector);
    if (!element) return null;
    const style = getComputedStyle(element);
    const lineHeight = number(style.lineHeight);
    const clipsInline = ["hidden", "clip"].includes(style.overflowX) || ["hidden", "clip"].includes(style.overflow);
    const clipsBlock = ["hidden", "clip"].includes(style.overflowY) || ["hidden", "clip"].includes(style.overflow);
    return {
      selector,
      fontSize: number(style.fontSize),
      renderedFontSize: number(number(style.fontSize) * scale),
      lineHeight,
      lineCount: lineHeight ? Math.max(1, Math.round(element.clientHeight / lineHeight)) : null,
      logicalWidth: element.clientWidth,
      logicalHeight: element.clientHeight,
      rect: logicalRect(element),
      clippedX: clipsInline && element.scrollWidth > element.clientWidth + 2,
      clippedY: clipsBlock && element.scrollHeight > element.clientHeight + 2,
    };
  };
  const intro = document.querySelector(".workspaceHomeIntro");
  const primaryAction = document.querySelector('[data-testid="workspace-connect-data"]');
  const mainPanel = document.querySelector(".mainPanel");
  const contentShell = document.querySelector(".contentShell");
  const appShell = document.querySelector(".appShell");
  const sidebar = document.querySelector(".workspaceSidebar");
  const workspaceNav = document.querySelector(".workspaceNav");
  const topBar = document.querySelector(".topBar");
  const journey = document.querySelector('[data-testid="workspace-journey"]');
  const primaryTask = document.querySelector('[data-testid="workspace-primary-task"]');
  const rootStyle = getComputedStyle(document.documentElement);
  const introStyle = intro ? getComputedStyle(intro) : null;
  const actionRect = primaryAction?.getBoundingClientRect();
  const surfaceStyle = surface ? getComputedStyle(surface) : null;
  const transform = surfaceStyle?.transform && surfaceStyle.transform !== "none"
    ? new DOMMatrixReadOnly(surfaceStyle.transform)
    : null;
  const text = document.body?.innerText || "";
  return {
    url: location.href,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    frame: {
      mode: viewportState.viewportMode ?? null,
      orientation: viewportState.viewportOrientation ?? null,
      scale,
      transformScaleX: preciseNumber(transform?.a ?? 1),
      transformScaleY: preciseNumber(transform?.d ?? 1),
      logicalWidth: number(viewportState.logicalWidth),
      logicalHeight: number(viewportState.logicalHeight),
      baselineWidth: number(viewportState.baselineWidth),
      baselineHeight: number(viewportState.baselineHeight),
      devicePixelRatio: preciseNumber(viewportState.viewportDevicePixelRatio),
      resolutionWidth: number(viewportState.viewportResolutionWidth),
      resolutionHeight: number(viewportState.viewportResolutionHeight),
      surfaceClientWidth: surface?.clientWidth ?? null,
      surfaceClientHeight: surface?.clientHeight ?? null,
      surfaceRect: surfaceRect ? {
        left: number(surfaceRect.left),
        top: number(surfaceRect.top),
        width: number(surfaceRect.width),
        height: number(surfaceRect.height),
      } : null,
    },
    ready: Boolean(document.querySelector(".appShell")) && Boolean(document.querySelector(".workspaceHome")),
    isHomeRoute: new URL(location.href).searchParams.get("section") === "home",
    hasServiceDiagnostics: Boolean(document.querySelector('[data-testid="service-diagnostics"]')),
    hasErrorBoundary: Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复"),
    typography: {
      topBarTitle: measure(".topBarTitle h1"),
      pageTitle: measure(".workspaceHomeIntro h1"),
      pageBody: measure(".workspaceHomeIntro p"),
      summaryValue: measure(".workspaceFacts dd"),
      taskTitle: measure(".workspaceTaskEmpty h3"),
      taskBody: measure(".workspaceTaskEmpty p"),
      navigationLabel: measure(".workspaceNavItem > span"),
    },
    spacing: {
      introInline: introStyle ? number(introStyle.paddingLeft) : null,
      introTop: introStyle ? number(introStyle.paddingTop) : null,
    },
    layout: {
      appShellGrid: appShell ? getComputedStyle(appShell).gridTemplateColumns : null,
      sidebarDisplay: sidebar ? getComputedStyle(sidebar).display : null,
      sidebarWidth: sidebar?.clientWidth ?? null,
      workspaceNavGrid: workspaceNav ? getComputedStyle(workspaceNav).gridTemplateColumns : null,
      topBarFlexDirection: topBar ? getComputedStyle(topBar).flexDirection : null,
      introDisplay: introStyle?.display ?? null,
      journeyGrid: journey ? getComputedStyle(journey).gridTemplateColumns : null,
      primaryTaskGrid: primaryTask ? getComputedStyle(primaryTask).gridTemplateColumns : null,
    },
    geometry: {
      sidebar: logicalRect(sidebar),
      contentShell: logicalRect(contentShell),
      intro: logicalRect(intro),
      journey: logicalRect(journey),
      primaryTask: logicalRect(primaryTask),
      primaryAction: logicalRect(primaryAction),
    },
    primaryAction: actionRect ? {
      width: number(actionRect.width),
      height: number(actionRect.height),
      logicalWidth: number(actionRect.width / scale),
      logicalHeight: number(actionRect.height / scale),
      bottom: number(actionRect.bottom),
    } : null,
    overflow: {
      documentX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
      bodyX: Math.max(0, document.body.scrollWidth - window.innerWidth),
      frameX: frame ? Math.max(0, frame.scrollWidth - frame.clientWidth) : null,
      mainPanelX: Boolean(mainPanel && mainPanel.scrollWidth > mainPanel.clientWidth + 2),
      contentShellX: Boolean(contentShell && contentShell.scrollWidth > contentShell.clientWidth + 2),
    },
    tokens: {
      textXs: rootStyle.getPropertyValue("--text-xs").trim(),
      textSm: rootStyle.getPropertyValue("--text-sm").trim(),
      textPrimary: rootStyle.getPropertyValue("--text-primary").trim(),
      textSecondary: rootStyle.getPropertyValue("--text-secondary").trim(),
      borderSubtle: rootStyle.getPropertyValue("--border-subtle").trim(),
      warningText: rootStyle.getPropertyValue("--warning-text").trim(),
      space1: rootStyle.getPropertyValue("--space-1").trim(),
      space2: rootStyle.getPropertyValue("--space-2").trim(),
      space3: rootStyle.getPropertyValue("--space-3").trim(),
      space4: rootStyle.getPropertyValue("--space-4").trim(),
      radiusMd: rootStyle.getPropertyValue("--radius-md").trim(),
      pageTitle: rootStyle.getPropertyValue("--ui-font-page-title").trim(),
      metric: rootStyle.getPropertyValue("--ui-font-metric").trim(),
    },
  };
}

async function waitForHomeReady(client, workspaceId, timeoutMs = 25000) {
  return waitFor(client, (expectedWorkspaceId) => {
    const selectedWorkspace = document.querySelector('select[aria-label="选择工作区"]')?.value || "";
    const hasServiceDiagnostics = Boolean(document.querySelector('[data-testid="service-diagnostics"]'));
    const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel"));
    const hasHome = Boolean(document.querySelector(".workspaceHome"));
    const hasPrimaryTask = Boolean(document.querySelector('[data-testid="workspace-primary-task"]'));
    return {
      ok: selectedWorkspace === expectedWorkspaceId && hasHome && hasPrimaryTask && !hasServiceDiagnostics && !hasErrorBoundary,
      workspace: selectedWorkspace,
      hasHome,
      hasPrimaryTask,
      hasServiceDiagnostics,
      hasErrorBoundary,
    };
  }, workspaceId, { timeoutMs, intervalMs: 250 });
}

const checks = [];
const viewportResults = [];
let lifecycle = null;
let browserInfo = null;
let consoleIssues = [];
let zoomAccessibilityResult = null;
let lowResolutionDprResult = null;
const sourceGuard = responsiveSourceGuard();
checks.push(
  check("responsive-layout-uses-logical-viewport-container", sourceGuard.viewportMedia.length === 0, {
    unexpectedViewportMedia: sourceGuard.viewportMedia,
  }),
  check("component-styles-avoid-physical-viewport-units", sourceGuard.viewportUnits.length === 0, {
    unexpectedViewportUnits: sourceGuard.viewportUnits,
  }),
);

try {
  const run = await withTemporaryWorkspace("typography", async ({ temporaryWorkspaceId }) => {
    let browser = null;
    try {
      browser = await launchChrome();
      browserInfo = { chromePath: browser.chromePath, chromeName: browser.chromeName };
      for (const viewport of viewports) {
        await setViewport(browser.client, viewport);
        const viewportUrl = new URL(url, baseUrl);
        viewportUrl.searchParams.set("section", "home");
        viewportUrl.searchParams.set("viewport", viewport.key);
        await navigate(browser.client, viewportUrl.toString());
        const ready = await waitForHomeReady(browser.client, temporaryWorkspaceId);
        const metrics = await evaluate(browser.client, typographyMetrics, null, 10000);
        const screenshot = await captureScreenshot(browser.client, join(screenshotDir, `${viewport.key}-${viewport.width}x${viewport.height}.png`));
        const prefix = `typography-${viewport.key}`;
        const type = metrics.typography;
        const expectedBaseline = viewport.orientation === "portrait"
          ? { width: 720, height: 1280 }
          : { width: 1280, height: 720 };
        const expectedScale = viewport.mode === "scaled"
          ? Math.min(viewport.width / expectedBaseline.width, viewport.height / expectedBaseline.height)
          : 1;
        const expectedLogical = viewport.mode === "scaled"
          ? expectedBaseline
          : { width: viewport.width, height: viewport.height };
        checks.push(
          check(`${prefix}-ready`, ready.ok && metrics.ready, { ready }),
          check(`${prefix}-home-route`, metrics.isHomeRoute),
          check(`${prefix}-no-runtime-error`, !metrics.hasServiceDiagnostics && !metrics.hasErrorBoundary),
          check(`${prefix}-viewport-mode`, metrics.frame.mode === viewport.mode && metrics.frame.orientation === viewport.orientation, {
            expected: { mode: viewport.mode, orientation: viewport.orientation },
            actual: metrics.frame,
          }),
          check(`${prefix}-scale-contract`,
            Math.abs(metrics.frame.scale - expectedScale) <= 0.001
              && Math.abs(metrics.frame.transformScaleX - expectedScale) <= 0.001
              && Math.abs(metrics.frame.transformScaleY - expectedScale) <= 0.001,
            { expectedScale, frame: metrics.frame }),
          check(`${prefix}-logical-canvas`,
            Math.abs(metrics.frame.logicalWidth - expectedLogical.width) <= 1
              && Math.abs(metrics.frame.logicalHeight - expectedLogical.height) <= 1
              && Math.abs(metrics.frame.surfaceClientWidth - expectedLogical.width) <= 1
              && Math.abs(metrics.frame.surfaceClientHeight - expectedLogical.height) <= 1,
            { expectedLogical, frame: metrics.frame }),
          check(`${prefix}-scaled-canvas-size`,
            Math.abs(metrics.frame.surfaceRect.width - expectedLogical.width * expectedScale) <= 1
              && Math.abs(metrics.frame.surfaceRect.height - expectedLogical.height * expectedScale) <= 1
              && Math.abs(metrics.frame.surfaceRect.left - (viewport.width - expectedLogical.width * expectedScale) / 2) <= 1
              && Math.abs(metrics.frame.surfaceRect.top - (viewport.height - expectedLogical.height * expectedScale) / 2) <= 1,
            { expectedScale, expectedLogical, frame: metrics.frame }),
          check(`${prefix}-no-horizontal-overflow`, metrics.overflow.documentX === 0 && metrics.overflow.bodyX === 0 && metrics.overflow.frameX === 0 && !metrics.overflow.mainPanelX && !metrics.overflow.contentShellX, { overflow: metrics.overflow }),
          check(`${prefix}-readable-floor`,
            (type.topBarTitle === null || type.topBarTitle?.fontSize >= 14) &&
            type.pageTitle?.fontSize >= 22 &&
            type.pageBody?.fontSize >= 13 &&
            type.summaryValue?.fontSize >= 18 &&
            type.taskTitle?.fontSize >= 15 &&
            type.taskBody?.fontSize >= 13 &&
            type.navigationLabel?.fontSize >= 10,
            { typography: type }),
          check(`${prefix}-headline-wrap`, type.pageTitle?.lineCount <= 2 && !type.pageTitle?.clippedX && !type.pageTitle?.clippedY, { pageTitle: type.pageTitle }),
          check(`${prefix}-logical-touch-target`, metrics.primaryAction?.logicalHeight >= 36, { primaryAction: metrics.primaryAction }),
          check(`${prefix}-primary-action-visible`, metrics.primaryAction?.bottom <= viewport.height, {
            viewportHeight: viewport.height,
            primaryAction: metrics.primaryAction,
          }),
          check(`${prefix}-tokens-defined`, Object.values(metrics.tokens).every(Boolean), { tokens: metrics.tokens }),
        );
        viewportResults.push({ viewport, ready, metrics, screenshot });
      }
      await browser.client.send("Emulation.setDeviceMetricsOverride", {
        width: 640,
        height: 360,
        deviceScaleFactor: 2,
        mobile: false,
      });
      const zoomUrl = new URL(url, baseUrl);
      zoomUrl.searchParams.set("section", "home");
      zoomUrl.searchParams.set("viewport", "browser-zoom-200");
      await navigate(browser.client, zoomUrl.toString());
      const zoomReady = await waitForHomeReady(browser.client, temporaryWorkspaceId);
      const zoomMetrics = await evaluate(browser.client, typographyMetrics, null, 10000);
      const zoomScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "browser-zoom-200-640x360@2x.png"));
      zoomAccessibilityResult = { ready: zoomReady, metrics: zoomMetrics, screenshot: zoomScreenshot };
      checks.push(
        check("browser-zoom-keeps-responsive-mode", zoomReady.ok
          && zoomMetrics.frame.mode === "responsive"
          && zoomMetrics.frame.scale === 1
          && zoomMetrics.frame.transformScaleX === 1
          && zoomMetrics.frame.transformScaleY === 1, { zoomAccessibilityResult }),
        check("browser-zoom-uses-device-pixel-resolution", zoomMetrics.frame.devicePixelRatio === 2
          && zoomMetrics.frame.resolutionWidth === 1280
          && zoomMetrics.frame.resolutionHeight === 720, { frame: zoomMetrics.frame }),
      );
      await browser.client.send("Emulation.setDeviceMetricsOverride", {
        width: 875,
        height: 875,
        deviceScaleFactor: 0.8,
        mobile: false,
      });
      const lowResolutionDprUrl = new URL(url, baseUrl);
      lowResolutionDprUrl.searchParams.set("section", "home");
      lowResolutionDprUrl.searchParams.set("viewport", "resolution-700-square");
      await navigate(browser.client, lowResolutionDprUrl.toString());
      const lowResolutionDprReady = await waitForHomeReady(browser.client, temporaryWorkspaceId);
      const lowResolutionDprMetrics = await evaluate(browser.client, typographyMetrics, null, 10000);
      const lowResolutionDprScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "resolution-700-square-875x875@0.8x.png"));
      lowResolutionDprResult = {
        ready: lowResolutionDprReady,
        metrics: lowResolutionDprMetrics,
        screenshot: lowResolutionDprScreenshot,
      };
      const lowResolutionDprExpectedScale = Math.min(875 / 720, 875 / 1280);
      checks.push(
        check("sub-one-dpr-enters-scaled-mode", lowResolutionDprReady.ok
          && lowResolutionDprMetrics.frame.mode === "scaled"
          && lowResolutionDprMetrics.frame.orientation === "portrait"
          && Math.abs(lowResolutionDprMetrics.frame.scale - lowResolutionDprExpectedScale) <= 0.001
          && Math.abs(lowResolutionDprMetrics.frame.transformScaleX - lowResolutionDprExpectedScale) <= 0.001
          && Math.abs(lowResolutionDprMetrics.frame.transformScaleY - lowResolutionDprExpectedScale) <= 0.001, {
          expectedScale: lowResolutionDprExpectedScale,
          lowResolutionDprResult,
        }),
        check("sub-one-dpr-uses-device-pixel-resolution", lowResolutionDprMetrics.frame.devicePixelRatio === 0.8
          && lowResolutionDprMetrics.frame.resolutionWidth === 700
          && lowResolutionDprMetrics.frame.resolutionHeight === 700
          && lowResolutionDprMetrics.frame.logicalWidth === 720
          && lowResolutionDprMetrics.frame.logicalHeight === 1280, { frame: lowResolutionDprMetrics.frame }),
      );
      consoleIssues = browser.client.consoleIssues();
      checks.push(check("typography-no-console-issues", consoleIssues.length === 0, { consoleIssues }));
    } finally {
      if (browser) await browser.close();
    }
    return {};
  });
  lifecycle = run.lifecycle;
} catch (error) {
  lifecycle = error?.lifecycle ?? lifecycle;
  checks.push(check("responsive-typography-runtime", false, { error: error instanceof Error ? error.message : String(error) }));
}

const resultByKey = Object.fromEntries(viewportResults.map((result) => [result.viewport.key, result]));
const size = (key, metric) => resultByKey[key]?.metrics.typography[metric]?.fontSize ?? 0;
const padding = (key) => resultByKey[key]?.metrics.spacing.introInline ?? 0;
const near = (left, right, tolerance = 1) => Number.isFinite(left) && Number.isFinite(right) && Math.abs(left - right) <= tolerance;
const sameOptionalNumber = (left, right, tolerance = 1) => left == null || right == null
  ? left === right
  : near(left, right, tolerance);
const sameLogicalTypography = (floorKey, scaledKey) => {
  const floor = resultByKey[floorKey]?.metrics.typography;
  const scaled = resultByKey[scaledKey]?.metrics.typography;
  if (!floor || !scaled) return false;
  return Object.keys(floor).every((key) => sameOptionalNumber(floor[key]?.fontSize, scaled[key]?.fontSize, 0.05)
    && sameOptionalNumber(floor[key]?.lineHeight, scaled[key]?.lineHeight, 0.05)
    && floor[key]?.lineCount === scaled[key]?.lineCount);
};
const sameLayoutFingerprint = (floorKey, scaledKey) => {
  const floor = resultByKey[floorKey]?.metrics.layout;
  const scaled = resultByKey[scaledKey]?.metrics.layout;
  return Boolean(floor && scaled && Object.keys(floor).every((key) => floor[key] === scaled[key]));
};
const sameLogicalGeometry = (floorKey, scaledKey) => {
  const floor = resultByKey[floorKey]?.metrics.geometry;
  const scaled = resultByKey[scaledKey]?.metrics.geometry;
  if (!floor || !scaled) return false;
  return Object.keys(floor).every((key) => {
    if (!floor[key] || !scaled[key]) return floor[key] === scaled[key];
    return ["x", "y", "width", "height"].every((field) => near(floor[key][field], scaled[key][field], 1.5));
  });
};
if (viewportResults.length === viewports.length) {
  checks.push(
    check("portrait-subfloor-keeps-logical-typography", sameLogicalTypography("portrait-floor", "portrait-half"), {
      floor: resultByKey["portrait-floor"]?.metrics.typography,
      scaled: resultByKey["portrait-half"]?.metrics.typography,
    }),
    check("landscape-subfloor-keeps-logical-typography", sameLogicalTypography("landscape-floor", "landscape-half"), {
      floor: resultByKey["landscape-floor"]?.metrics.typography,
      scaled: resultByKey["landscape-half"]?.metrics.typography,
    }),
    check("portrait-subfloor-keeps-layout", sameLayoutFingerprint("portrait-floor", "portrait-half") && sameLogicalGeometry("portrait-floor", "portrait-half"), {
      floorLayout: resultByKey["portrait-floor"]?.metrics.layout,
      scaledLayout: resultByKey["portrait-half"]?.metrics.layout,
      floorGeometry: resultByKey["portrait-floor"]?.metrics.geometry,
      scaledGeometry: resultByKey["portrait-half"]?.metrics.geometry,
    }),
    check("landscape-subfloor-keeps-layout", sameLayoutFingerprint("landscape-floor", "landscape-half") && sameLogicalGeometry("landscape-floor", "landscape-half"), {
      floorLayout: resultByKey["landscape-floor"]?.metrics.layout,
      scaledLayout: resultByKey["landscape-half"]?.metrics.layout,
      floorGeometry: resultByKey["landscape-floor"]?.metrics.geometry,
      scaledGeometry: resultByKey["landscape-half"]?.metrics.geometry,
    }),
    check("landscape-letterbox-keeps-floor-contract", sameLogicalTypography("landscape-floor", "landscape-letterbox")
      && sameLayoutFingerprint("landscape-floor", "landscape-letterbox")
      && sameLogicalGeometry("landscape-floor", "landscape-letterbox"), {
      floorTypography: resultByKey["landscape-floor"]?.metrics.typography,
      letterboxTypography: resultByKey["landscape-letterbox"]?.metrics.typography,
      floorLayout: resultByKey["landscape-floor"]?.metrics.layout,
      letterboxLayout: resultByKey["landscape-letterbox"]?.metrics.layout,
      floorGeometry: resultByKey["landscape-floor"]?.metrics.geometry,
      letterboxGeometry: resultByKey["landscape-letterbox"]?.metrics.geometry,
    }),
    check("subfloor-rendering-is-uniform-half-scale",
      near(resultByKey["portrait-half"]?.metrics.typography.pageTitle?.renderedFontSize, size("portrait-floor", "pageTitle") * 0.5, 0.05)
        && near(resultByKey["landscape-half"]?.metrics.typography.pageTitle?.renderedFontSize, size("landscape-floor", "pageTitle") * 0.5, 0.05), {
        portrait: resultByKey["portrait-half"]?.metrics.typography.pageTitle,
        landscape: resultByKey["landscape-half"]?.metrics.typography.pageTitle,
      }),
    check("page-title-remains-fluid-above-floor", size("wide-desktop", "pageTitle") >= size("landscape-floor", "pageTitle") + 1, {
      wide: size("wide-desktop", "pageTitle"),
      floor: size("landscape-floor", "pageTitle"),
    }),
    check("page-gutter-remains-fluid-above-floor", padding("wide-desktop") >= padding("landscape-floor") + 4, {
      wide: padding("wide-desktop"),
      floor: padding("landscape-floor"),
    }),
  );
}

const receipt = finishReceipt({
  ok: false,
  generatedBy: "scripts/verify-responsive-typography.mjs",
  url,
  browser: browserInfo,
  screenshotDir,
  receiptPath,
  lifecycle,
  consoleIssues,
  zoomAccessibilityResult,
  lowResolutionDprResult,
  viewportResults,
  checks,
});

writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
