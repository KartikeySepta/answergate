import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listWorkspaces, getWorkspace, deleteWorkspace } from '@/api/workspaces';

export function useWorkspaces() {
  return useQuery({
    queryKey: ['workspaces'],
    queryFn: listWorkspaces,
  });
}

export function useWorkspace(id: string) {
  return useQuery({
    queryKey: ['workspace', id],
    queryFn: () => getWorkspace(id),
    enabled: !!id,
  });
}

export function useDeleteWorkspace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteWorkspace(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
    },
  });
}
