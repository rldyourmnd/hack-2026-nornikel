import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/app";
import "@/shared/config/theme/theme.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
