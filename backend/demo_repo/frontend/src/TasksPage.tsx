// Demo fixture: these calls deliberately include missing routes and a method mismatch.
interface Task {
  id: string;
  title: string;
  completed: boolean;
  project_id: string;
}

export async function loadTasks(projectId: string): Promise<Task[]> {
  const response = await fetch(`/api/projects/${projectId}/tasks`);
  return response.json();
}

export async function createTask(title: string, projectId: string) {
  return fetch('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({ title, project_id: projectId, completed: false }),
  });
}

export async function updateTask(taskId: string) {
  return fetch(`/api/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify({ completed: true }),
  });
}
