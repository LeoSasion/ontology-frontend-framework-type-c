export const siblingRepositoryNames = Object.freeze([
  "AIBI-A",
  "AIBI-B",
  "AIBI-D",
  "AIBI-E",
]);

export const absoluteSiblingProjectPathPattern = /(?:[A-Za-z]:[\\/]|(?<!:)(?:\\\\|\/\/)[^\\/\r\n"']+[\\/][^\\/\r\n"']+[\\/]|(?<![\w:/])\/(?!\/))(?:[^\\/\r\n"']+[\\/])*(?:AIBI-[ABDE]|AIBI项目杂交|AIBI|财务报表(?:_bak)?)(?=[\\/])/giu;
export const relativeSiblingProjectPathPattern = /(?:^|[\s"'`(=:,])(?:\.\.[\\/]+)*(?:AIBI-[ABDE])(?=[\\/])(?![\\/][ABDE](?:\s|$))/gimu;
export const legacyCrossProjectEnvironmentVariablePattern = /AIBI_PROJECT_[ABDE]_PATH/gu;
export const forbiddenProjectPathPattern = /[\\/](?:AIBI-[ABDE]|AIBI项目杂交|AIBI|财务报表(?:_bak)?)(?:[\\/]|$)/iu;

export function patternMatches(pattern, value) {
  pattern.lastIndex = 0;
  return pattern.test(String(value ?? ""));
}
