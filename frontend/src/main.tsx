import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import TuringApp from "./turing/TuringApp";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/^\/turing(?:\/|$)/.test(window.location.pathname) ? (
      <TuringApp />
    ) : (
      <App />
    )}
  </StrictMode>,
);
