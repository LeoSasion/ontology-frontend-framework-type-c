import { useCallback, useEffect, useState } from "react";
import type { AppSection } from "./components/Sidebar";

const inspectorPreferenceStorageKey = "aibiHybrid.contextDrawerPreference";

function initialInspectorPreference() {
  if (typeof window === "undefined") {
    return { expanded: false, pinned: false };
  }
  try {
    const stored = window.localStorage.getItem(inspectorPreferenceStorageKey);
    if (!stored) return { expanded: false, pinned: false };
    const parsed = JSON.parse(stored) as { expanded?: unknown; pinned?: unknown };
    return {
      expanded: parsed.expanded === true || parsed.pinned === true,
      pinned: parsed.pinned === true,
    };
  } catch {
    return { expanded: false, pinned: false };
  }
}

export function useInspectorController(openSection: (section: AppSection) => void) {
  const [preference, setPreference] = useState(initialInspectorPreference);
  const expanded = preference.expanded || preference.pinned;

  useEffect(() => {
    try {
      window.localStorage.setItem(inspectorPreferenceStorageKey, JSON.stringify(preference));
    } catch {
      // The inspector still works when storage is unavailable.
    }
  }, [preference]);

  const expand = useCallback(() => {
    setPreference((current) => ({ ...current, expanded: true }));
  }, []);

  const collapse = useCallback(() => {
    setPreference((current) => ({ ...current, expanded: false, pinned: false }));
  }, []);

  const togglePinned = useCallback(() => {
    setPreference((current) => {
      const pinned = !current.pinned;
      return { expanded: pinned ? true : current.expanded, pinned };
    });
  }, []);

  const openAgent = useCallback(() => {
    expand();
    openSection("agent");
  }, [expand, openSection]);

  const openEvidence = useCallback(() => {
    expand();
    openSection("evidence");
  }, [expand, openSection]);

  const openAndExpand = useCallback((section: AppSection) => {
    expand();
    openSection(section);
  }, [expand, openSection]);

  return {
    collapse,
    expand,
    expanded,
    openAgent,
    openAndExpand,
    openEvidence,
    pinned: preference.pinned,
    togglePinned,
  };
}
