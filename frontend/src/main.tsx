import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { FilterProvider } from "./state/FilterContext";
import { AuthProvider } from "./state/AuthContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <FilterProvider>
          <App />
        </FilterProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
