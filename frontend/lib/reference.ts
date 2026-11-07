import type { Lang, Requirement, RefInfo } from "./types";

/** O*NET reference careers (group non_it): labels shown instead of job-ad demand. */
export const MIN_JOB_ZONE_D4 = 4;   // D4/S1 -> O*NET Job Zone >= 4 (same rule as the thesis web, careerai)

export function reqLabel(r: Requirement, lang: Lang): string {
  if (r.demand == null) return `${lang === "id" ? "kepentingan" : "importance"} ${(r.importance ?? 0).toFixed(1)}/${r.scale ?? 5}`;
  return `${Math.round(r.demand * 100)}%`;
}
export function reqBar(r: Requirement): number {
  return r.demand == null ? ((r.importance ?? 0) / (r.scale ?? 5)) * 100 : r.demand * 100;
}
export function refNote(c: RefInfo, lang: Lang): string {
  const zone = c.job_zone ? ` · Job Zone ${c.job_zone}` : "";
  const field = lang === "id" ? c.field_id : c.field_en;
  return lang === "id"
    ? `Profil acuan O*NET 31.0 (AS), belum divalidasi untuk Indonesia${field ? ` · ${field}` : ""}${zone}`
    : `O*NET 31.0 reference profile (US), not validated for Indonesia${field ? ` · ${field}` : ""}${zone}`;
}
