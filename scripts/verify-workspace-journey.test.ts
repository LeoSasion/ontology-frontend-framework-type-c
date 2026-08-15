import assert from "node:assert/strict";
import test from "node:test";
import type { AgentAskResult, ImportPreview, SourceIntelligenceRunSummary, WorkbenchPayload, WorkspaceStatus } from "../src/types";
import type { AnalysisJob } from "../src/typesJobs";
import { buildSourceWorkbenchGuidance } from "../src/sourceWorkbenchGuidanceModel";
import { buildWorkspaceJourney, sourceIntelligenceInputs } from "../src/workspaceJourneyModel";
import { buildTrustedAnswerCoordinator } from "../src/trustedAnswerCoordinator";

function status(tableCount = 0, actionDrafts = 0): WorkspaceStatus {
  return {
    ok: true,
    workspace: { id: "journey-test", name: "Journey test" },
    counts: {
      tables: tableCount,
      sourceRuns: tableCount,
      fields: 0,
      metrics: 0,
      relationships: 0,
      dashboards: 0,
      actionDrafts,
      sourceIntelligenceRuns: 0,
    },
    sourceRuns: [],
    health: { ok: true, notes: [] },
  };
}

function workbench(options: { hasData?: boolean; runs?: SourceIntelligenceRunSummary[] } = {}): WorkbenchPayload {
  return {
    ok: true,
    tables: options.hasData ? [{
      table_key: "orders",
      display_name: "Orders",
      source_file: "C:\\data\\orders.xlsx",
      row_count: 12,
      column_count: 4,
      data_version: 1,
    }] : [],
    fields: [],
    metrics: [],
    relationships: [],
    importJobs: options.hasData ? [{
      job_key: "import-1",
      source_file: "C:\\data\\orders.xlsx",
      mode: "create",
      status: "success",
      row_count: 12,
      created_at: "2026-07-28T00:00:00.000Z",
    }] : [],
    savedViews: [],
    sourceIntelligenceRuns: options.runs ?? [],
    fieldRoles: [],
    fieldUsages: [],
    safeAggregations: [],
    formulaDsl: { allowedFunctions: [], fieldReference: "field", acceptsSql: false },
  };
}

function agent(patch: Partial<AgentAskResult> = {}): AgentAskResult {
  return {
    ok: true,
    workspaceId: "",
    llm: { configured: false, mode: "deterministic-fallback" },
    matched: {
      table: null,
      tableSelectionConfidence: "none",
      dashboard: null,
      dashboardSelectionConfidence: "none",
    },
    plan: [],
    recommendedCommands: [],
    requiresConfirmation: false,
    actionDraft: { actionKey: "", kind: "", status: "" },
    ontology: { version: 1, objects: [], functions: [], links: [], actions: [], evidenceFiles: [] },
    coreSemanticRuntime: {} as AgentAskResult["coreSemanticRuntime"],
    sourcePipelineContract: {} as AgentAskResult["sourcePipelineContract"],
    ...patch,
  };
}

function run(fresh = true): SourceIntelligenceRunSummary {
  return {
    run_key: "source-run-1",
    label: "Workspace evidence",
    status: "succeeded",
    source_count: 1,
    table_count: 1,
    field_candidate_count: 4,
    relationship_count: 0,
    metric_sql_plan_count: 2,
    metric_sql_executable_count: 2,
    created_at: "2026-07-28T00:01:00.000Z",
    inputRoots: ["C:\\data\\orders.xlsx"],
    freshness: { usableForPlanning: fresh },
  } as SourceIntelligenceRunSummary;
}

function job(statusValue: string, progress = 0): AnalysisJob {
  return {
    schema: "aibi-analysis-job/v1",
    jobKey: "source-job-1",
    workspaceId: "journey-test",
    parentJobKey: null,
    kind: "source-intelligence",
    capabilityId: "source-intelligence",
    label: "Workspace evidence",
    status: statusValue,
    progress,
    stage: "profile",
    cancelRequested: false,
    inputFingerprint: "inputs",
    input: {},
    result: null,
    error: statusValue === "failed" ? { message: "test failure" } : null,
    artifactRefs: [],
    evidenceRefs: [],
    queryReceiptKey: null,
    analysisRunKey: null,
    sourceRunId: null,
    createdAt: "2026-07-28T00:00:00.000Z",
    queuedAt: null,
    startedAt: null,
    updatedAt: "2026-07-28T00:00:01.000Z",
    finishedAt: null,
  };
}

test("empty workspace begins with one connect-data action", () => {
  const journey = buildWorkspaceJourney({ status: status(), workbench: workbench(), agent: agent() });
  assert.equal(journey.phase, "connect");
  assert.deepEqual(journey.stepStates, ["current", "upcoming", "upcoming", "upcoming"]);
  assert.equal(journey.understanding.state, "empty");
});

test("durable Source Intelligence progress survives as the understanding phase", () => {
  const journey = buildWorkspaceJourney({
    status: status(1),
    workbench: workbench({ hasData: true }),
    agent: agent(),
    sourceIntelligenceJobs: [job("running", 47)],
  });
  assert.equal(journey.phase, "understand");
  assert.equal(journey.understanding.state, "running");
  assert.equal(journey.understanding.progress, 47);
  assert.deepEqual(journey.stepStates, ["complete", "current", "upcoming", "upcoming"]);
});

test("usable evidence moves directly to asking and retains source inputs", () => {
  const journey = buildWorkspaceJourney({
    status: status(1),
    workbench: workbench({ hasData: true, runs: [run()] }),
    agent: agent(),
  });
  assert.equal(journey.phase, "ask");
  assert.equal(journey.understanding.state, "ready");
  assert.deepEqual(sourceIntelligenceInputs(workbench({ hasData: true, runs: [run()] })), ["C:\\data\\orders.xlsx"]);
});

test("usable partial evidence stays analyzable while refresh remains suggested", () => {
  const partialRun = run();
  partialRun.fileCoverage = { complete: false } as SourceIntelligenceRunSummary["fileCoverage"];
  const currentWorkbench = workbench({ hasData: true, runs: [partialRun] });
  const journey = buildWorkspaceJourney({
    status: status(1),
    workbench: currentWorkbench,
    agent: agent(),
  });
  const guidance = buildSourceWorkbenchGuidance({
    busy: null,
    preview: {
      ok: false,
      profile: { rowCount: 0, columnCount: 0 },
    } as ImportPreview,
    tables: currentWorkbench.tables,
    fields: currentWorkbench.fields,
    latestSourceProfile: partialRun,
  });

  assert.equal(journey.hasCurrentEvidence, true);
  assert.equal(guidance.sourceProfileAvailable, true);
  assert.equal(guidance.sourceProfileComplete, false);
  assert.equal(guidance.recommendedPrimaryAction, "start-analysis");
  assert.match(guidance.beginnerPlan.find((item) => item.key === "profile")?.state ?? "", /建议更新|refresh suggested/i);
});

test("a completed answer moves to review, while a pending write takes confirmation priority", () => {
  const answered = agent({
    workspaceId: "journey-test",
    llm: {
      configured: false,
      mode: "deterministic-fallback",
      response: {
        summary: "Revenue changed.",
        rationale: [],
        clarification: null,
        nextActions: [],
        citedEvidence: [],
        certainty: "grounded",
      },
    },
  });
  const review = buildWorkspaceJourney({
    status: status(1),
    workbench: workbench({ hasData: true, runs: [run()] }),
    agent: answered,
  });
  assert.equal(review.phase, "review");
  assert.equal(review.resultState, "ready");

  const confirm = buildWorkspaceJourney({
    status: status(1, 1),
    workbench: workbench({ hasData: true, runs: [run()] }),
    agent: { ...answered, requiresConfirmation: true },
    pendingDraftCount: 1,
  });
  assert.equal(confirm.phase, "confirm");
  assert.equal(confirm.currentStep, 3);
});

test("a blocked analysis remains reviewable without claiming a trusted result", () => {
  const blocked = buildWorkspaceJourney({
    status: status(1),
    workbench: workbench({ hasData: true, runs: [run()] }),
    agent: agent({
      workspaceId: "journey-test",
      answerCard: {
        kind: "analysis-gap",
        resultState: "blocked",
        title: { zh: "需要澄清", en: "Clarification required" },
        summary: { zh: "没有发布数字", en: "No number was published" },
        confidence: "blocked",
        metrics: [],
        rows: [],
        evidenceRefs: [],
        nextActions: [],
      },
    }),
  });
  assert.equal(blocked.phase, "review");
  assert.equal(blocked.resultState, "blocked");
});

test("failed and stale understanding are explicit rather than silently treated as ready", () => {
  const failed = buildWorkspaceJourney({
    status: status(1),
    workbench: workbench({ hasData: true }),
    agent: agent(),
    sourceIntelligenceJobs: [job("failed")],
  });
  assert.equal(failed.understanding.state, "failed");

  const stale = buildWorkspaceJourney({
    status: status(1),
    workbench: workbench({ hasData: true, runs: [run(false)] }),
    agent: agent(),
  });
  assert.equal(stale.understanding.state, "stale");
  assert.equal(stale.hasCurrentEvidence, false);
});

test("first trusted answer coordinator exposes exactly one prioritized recommendation", () => {
  const connect = buildTrustedAnswerCoordinator({ status: status(), workbench: workbench(), agent: agent() });
  assert.deepEqual(
    { action: connect.recommendation.actionKey, enabled: connect.recommendation.enabled },
    { action: "connect-data", enabled: true },
  );

  const running = buildTrustedAnswerCoordinator({
    status: status(1),
    workbench: workbench({ hasData: true }),
    agent: agent(),
    sourceIntelligenceJobs: [job("running", 22)],
  });
  assert.deepEqual(
    { action: running.recommendation.actionKey, enabled: running.recommendation.enabled },
    { action: "wait-for-understanding", enabled: false },
  );

  const recovery = buildTrustedAnswerCoordinator({
    status: status(1),
    workbench: workbench({ hasData: true }),
    agent: agent(),
    sourceIntelligenceJobs: [job("failed")],
  });
  assert.equal(recovery.recommendation.stage, "recover");

  const ask = buildTrustedAnswerCoordinator({
    status: status(1),
    workbench: workbench({ hasData: true, runs: [run()] }),
    agent: agent(),
  });
  assert.equal(ask.recommendation.actionKey, "ask-question");

  const clarificationAgent = agent({
    workspaceId: "journey-test",
    clarification: { required: true } as AgentAskResult["clarification"],
  });
  const clarify = buildTrustedAnswerCoordinator({
    status: status(1),
    workbench: workbench({ hasData: true, runs: [run()] }),
    agent: clarificationAgent,
  });
  assert.equal(clarify.recommendation.actionKey, "answer-clarification");

  const confirm = buildTrustedAnswerCoordinator({
    status: status(1, 1),
    workbench: workbench({ hasData: true, runs: [run()] }),
    agent: { ...clarificationAgent, requiresConfirmation: true },
    pendingDraftCount: 1,
  });
  assert.equal(confirm.recommendation.actionKey, "review-draft");
  assert.equal(Object.keys(confirm).filter((key) => key === "recommendation").length, 1);
});
