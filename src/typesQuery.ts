export interface QueryResult {
  ok: boolean;
  query: {
    table: string;
    mode: string;
    group?: string;
    measure: string;
    aggregation: string;
    sqlIntent: string;
    runtime?: {
      engine: string;
      database: string;
      compiledSql: string;
      syncedRows?: number | null;
    };
    fallbackReason?: string | null;
  };
  rows: Array<{
    label?: string;
    value: number | string | null;
  }>;
}
