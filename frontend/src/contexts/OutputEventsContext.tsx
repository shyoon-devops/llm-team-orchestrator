import { createContext, useContext } from "react";
import type { WSEvent } from "../types";

const OutputEventsContext = createContext<WSEvent[]>([]);

export const OutputEventsProvider = OutputEventsContext.Provider;

export function useOutputEvents(): WSEvent[] {
  return useContext(OutputEventsContext);
}
