import { useParams } from "react-router-dom";

import { useProject } from "../api/hooks";

/**
 * Read the active project off the URL. ``ProjectShell`` is mounted on
 * ``/projects/:projectName/*``, so child routes can pull a fully loaded
 * ``ProjectDetail`` via this hook without prop-drilling.
 */
export function useActiveProject() {
  const { projectName } = useParams<{ projectName: string }>();
  const query = useProject(projectName);
  return { projectName, ...query };
}
