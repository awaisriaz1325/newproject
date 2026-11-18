import type { ReactNode } from "react";
import { SessionProvider } from "@/components/session";

export default function AppLayout({ children }: { children: ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}
