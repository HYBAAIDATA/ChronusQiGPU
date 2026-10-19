import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import TuringWorkspace from "./turing/Workspace";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {window.location.pathname.replace(/\/$/, "") === "/turing" ? (
      <TuringWorkspace />
    ) : (
      <App />
    )}
  </StrictMode>,
);
