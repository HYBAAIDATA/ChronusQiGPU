import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import TuringApp from "./turing/TuringApp";
import EnterpriseApp from "./enterprise/EnterpriseApp";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/^\/enterprise(?:\/|$)/.test(window.location.pathname) ? (
      <EnterpriseApp />
    ) : /^\/turing(?:\/|$)/.test(window.location.pathname) ? (
      <TuringApp />
    ) : (
      <App />
    )}
  </StrictMode>,
);
