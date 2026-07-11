export function appendCliFilters(args: string[], filters: unknown, options: { includeSide?: boolean } = {}) {
  if (!Array.isArray(filters)) return;
  for (const filter of filters) {
    if (filter && typeof filter === "object") {
      const item = filter as Record<string, unknown>;
      const side = options.includeSide && item.side ? `${String(item.side)}:` : "";
      args.push("--filter", `${side}${String(item.field ?? "")}:${String(item.operator ?? "contains")}:${String(item.value ?? "")}`);
    }
  }
}

export function appendCliSorts(args: string[], sortItems: unknown) {
  if (!Array.isArray(sortItems)) return;
  for (const sort of sortItems) {
    if (sort && typeof sort === "object") {
      const item = sort as Record<string, unknown>;
      args.push("--sort", `${String(item.field ?? "")}:${String(item.direction ?? "asc")}`);
    }
  }
}
