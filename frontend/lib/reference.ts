import type { Lang, Requirement, RefInfo } from "./types";

/** O*NET reference careers (group non_it): labels shown instead of job-ad demand. */
/** Education level (thesis Table 3.9): reference careers whose O*NET Job Zone is above the level are hidden.
 *  zone = highest Job Zone shown (0 = all levels). The student chooses it on the results page; D4/S1 by default. */
export const MIN_JOB_ZONE_D4 = 4;
export const EDU_ZONES: { zone: number; id: string; en: string }[] = [
  { zone: 0, id: "Semua jenjang", en: "All levels" },
  { zone: 2, id: "SMA/SMK (Job Zone ≤ 2)", en: "Secondary (Job Zone ≤ 2)" },
  { zone: 3, id: "D3 (Job Zone ≤ 3)", en: "Diploma (Job Zone ≤ 3)" },
  { zone: 4, id: "D4/S1 (Job Zone ≤ 4)", en: "Bachelor (Job Zone ≤ 4)" },
  { zone: 5, id: "S2 (Job Zone ≤ 5)", en: "Master's (Job Zone ≤ 5)" },
];
/** IT careers are always shown; a reference career is hidden when its Job Zone is above the chosen level. */
export const zoneAllows = (r: { group?: string; job_zone?: number | null }, zone: number) =>
  r.group !== "non_it" || zone === 0 || r.job_zone == null || r.job_zone <= zone;

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
