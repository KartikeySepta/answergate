import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listJobs, addVideo, addBatch, cancelJob } from '@/api/jobs';

export function useJobs(status?: string) {
  return useQuery({
    queryKey: ['jobs', status],
    queryFn: () => listJobs(status),
    refetchInterval: 5000,
  });
}

export function useAddVideo() {
  return useMutation({
    mutationFn: ({
      url,
      workspaceId,
      engine,
    }: {
      url: string;
      workspaceId: string;
      engine?: string;
    }) => addVideo(url, workspaceId, engine),
  });
}

export function useAddBatch() {
  return useMutation({
    mutationFn: ({
      urls,
      workspaceId,
      engine,
    }: {
      urls: string[];
      workspaceId: string;
      engine?: string;
    }) => addBatch(urls, workspaceId, engine),
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => cancelJob(jobId),
    onSuccess: (_data, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
    },
  });
}
