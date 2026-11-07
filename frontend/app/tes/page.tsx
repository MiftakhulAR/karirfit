"use client";

import { AuthGate } from "@/components/AuthGate";
import { useApp } from "@/components/AppProvider";
import { Wizard } from "@/components/Wizard";

export default function TestPage() {
  const { hydrated } = useApp();
  // login is required before the test (FR1); wait for saved answers so the wizard does not flash empty
  return <AuthGate>{hydrated ? <Wizard /> : null}</AuthGate>;
}
