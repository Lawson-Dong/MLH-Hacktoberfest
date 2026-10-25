export async function loadWorkspace() {
  const projects = await fetch('/api/projects');
  const members = await fetch('/api/members');
  const health = await fetch('/api/health');
  return { projects: await projects.json(), members: await members.json(), health: await health.json() };
}
