import { useQuery } from '@tanstack/react-query';
import { getClaims, getThemes, getReport } from '@/api/claims';

export function useClaims(workspaceId: string, limit?: number, offset?: number) {
  return useQuery({
    queryKey: ['claims', workspaceId, limit, offset],
    queryFn: () => getClaims(workspaceId, limit, offset),
    enabled: !!workspaceId,
  });
}

export function useThemes(workspaceId: string) {
  return useQuery({
    queryKey: ['themes', workspaceId],
    queryFn: () => getThemes(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useReport(workspaceId: string) {
  return useQuery({
    queryKey: ['report', workspaceId],
    queryFn: () => getReport(workspaceId),
    enabled: !!workspaceId,
  });
}
