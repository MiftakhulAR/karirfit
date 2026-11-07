"use client";

import { AuthGate } from "@/components/AuthGate";
import { useApp } from "@/components/AppProvider";
import { ServerError } from "@/components/Header";
import { Results } from "@/components/Results";

export default function ResultsPage() {
  const { hydrated, model } = useApp();
  return (
    <AuthGate>
      {!hydrated ? null : !model ? <ServerError /> : <Results />}
    </AuthGate>
  );
}
