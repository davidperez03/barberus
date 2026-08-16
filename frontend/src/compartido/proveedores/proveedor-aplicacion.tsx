"use client";

/**
 * Cascarón de providers transversales (hoy: react-query). Vive en `compartido/` porque
 * no pertenece a ningún contexto -- lo consume `app/layout.tsx`.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function ProveedorAplicacion({ children }: { children: React.ReactNode }) {
  const [clienteConsultas] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );

  return <QueryClientProvider client={clienteConsultas}>{children}</QueryClientProvider>;
}
