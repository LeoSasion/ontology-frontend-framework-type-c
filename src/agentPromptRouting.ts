import type { AppSection } from "./appSections";
import type { WorkspaceStatus } from "./types";

export type AgentPromptRoute = {
  section: AppSection;
  reasonZh: string;
  reasonEn: string;
  matchedKeywords: string[];
};

type RouteRule = {
  section: AppSection;
  reasonZh: string;
  reasonEn: string;
  keywords: RegExp[];
};

const routeRules: RouteRule[] = [
  {
    section: "agent",
    reasonZh: "需要确认或处理待写入修改",
    reasonEn: "Review or approve pending changes",
    keywords: [/确认/, /待确认/, /草案/, /修改/, /写入/, /执行/, /删除/, /覆盖/, /应用/, /approve/, /confirm/, /draft/, /write/, /delete/, /overwrite/, /apply/],
  },
  {
    section: "sources",
    reasonZh: "进入数据源工作台",
    reasonEn: "Open the source workbench",
    keywords: [/导入/, /上传/, /数据源/, /表格/, /文件/, /字段/, /公式/, /关系/, /预检/, /合并/, /连接器/, /source/, /import/, /upload/, /file/, /field/, /formula/, /relationship/, /connector/],
  },
  {
    section: "views",
    reasonZh: "打开明细和分页查询",
    reasonEn: "Open detail views and paged query",
    keywords: [/明细/, /视图/, /分页/, /筛选/, /过滤/, /排序/, /下钻/, /行数据/, /保存视图/, /detail/, /view/, /rows?/, /filter/, /sort/, /drill/, /paged/],
  },
  {
    section: "dashboards",
    reasonZh: "打开看板和图表编辑",
    reasonEn: "Open dashboards and chart editing",
    keywords: [/看板/, /仪表盘/, /图表/, /组件/, /柱状图/, /折线图/, /饼图/, /dashboard/, /board/, /chart/, /widget/],
  },
  {
    section: "evidence",
    reasonZh: "查看证据链和口径说明",
    reasonEn: "Open evidence and metric explanation",
    keywords: [/证据/, /溯源/, /来源/, /引用/, /口径/, /解释/, /为什么/, /计算/, /可信/, /evidence/, /proof/, /source trace/, /explain/, /why/, /calculation/, /trust/],
  },
  {
    section: "settings",
    reasonZh: "进入工作区设置",
    reasonEn: "Open workspace settings",
    keywords: [/设置/, /偏好/, /主题/, /语言/, /白名单/, /权限/, /沙盒/, /配置/, /settings/, /preference/, /theme/, /language/, /permission/, /config/, /sandbox/],
  },
];

export function resolveAgentPromptRoute(prompt: string, status?: WorkspaceStatus): AgentPromptRoute {
  const normalized = prompt.trim().toLocaleLowerCase();
  const fallback: AgentPromptRoute = {
    section: "agent",
    reasonZh: "交给 Agent 回答和整理证据",
    reasonEn: "Let Agent answer and gather evidence",
    matchedKeywords: [],
  };
  if (!normalized) return fallback;

  const ranked = routeRules
    .map((rule) => {
      const matchedKeywords = rule.keywords
        .filter((keyword) => keyword.test(normalized))
        .map((keyword) => keyword.source);
      return { rule, matchedKeywords };
    })
    .filter((item) => item.matchedKeywords.length > 0)
    .sort((left, right) => right.matchedKeywords.length - left.matchedKeywords.length);

  const best = ranked[0];
  if (best) {
    return {
      section: best.rule.section,
      reasonZh: best.rule.reasonZh,
      reasonEn: best.rule.reasonEn,
      matchedKeywords: best.matchedKeywords,
    };
  }

  if (status && status.counts.tables <= 0) {
    return {
      section: "sources",
      reasonZh: "还没有可分析数据，先接入数据源",
      reasonEn: "No analysis table yet, start with sources",
      matchedKeywords: [],
    };
  }

  return fallback;
}
