import { Navigate, Route, Routes } from "react-router-dom";

import { RootShell } from "./components/RootShell";
import { ProjectShell } from "./components/ProjectShell";
import { ProjectsPage } from "./routes/ProjectsPage";
import { DashboardPage } from "./routes/DashboardPage";
import { SchemaPage } from "./routes/SchemaPage";
import { QueryPage } from "./routes/QueryPage";
import { ProposalsPage } from "./routes/ProposalsPage";
import { SettingsPage } from "./routes/SettingsPage";
import { VaultPage } from "./routes/VaultPage";
import { GraphPage } from "./routes/GraphPage";
import { HelpPage } from "./routes/HelpPage";

export default function App() {
  return (
    <Routes>
      <Route element={<RootShell />}>
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route path="projects/:projectName" element={<ProjectShell />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="schema" element={<SchemaPage />} />
          <Route path="query" element={<QueryPage />} />
          <Route path="vault" element={<VaultPage />} />
          <Route path="graph" element={<GraphPage />} />
          <Route path="proposals" element={<ProposalsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
