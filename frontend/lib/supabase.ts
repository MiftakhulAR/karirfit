import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { Answers, Assessment, RecommendResponse } from "./types";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

/** null when the Supabase env variables are missing (the UI then explains how to set them). */
export const supabase: SupabaseClient | null = URL && ANON ? createClient(URL, ANON) : null;
export const supabaseConfigured = Boolean(supabase);

/** Saves one finished test for the signed-in user (row-level security: only the owner can read it). */
export async function saveAssessment(answers: Answers, res: RecommendResponse) {
  if (!supabase) return;
  const top = res.top.map(r => ({ career: r.career, name_id: r.name_id, name_en: r.name_en, fit: Math.round(r.fit * 10) / 10 }));
  const { error } = await supabase.from("assessments").insert({ answers, top });
  if (error) throw new Error(error.message);
}

export async function listAssessments(): Promise<Assessment[]> {
  if (!supabase) return [];
  const { data, error } = await supabase.from("assessments").select("id, created_at, answers, top")
    .order("created_at", { ascending: false }).limit(50);
  if (error) throw new Error(error.message);
  return (data ?? []) as Assessment[];
}

export async function deleteAssessment(id: string) {
  if (!supabase) return;
  const { error } = await supabase.from("assessments").delete().eq("id", id);
  if (error) throw new Error(error.message);
}
