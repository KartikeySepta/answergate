import { useQuery } from '@tanstack/react-query';
import { useRef } from 'react';
import { getJob } from '@/api/jobs';
import type { JobDetail } from '@/api/types';

const FAST_INTERVAL = 2000;
const BACKOFF_INTERVAL = 10_000;
const MAX_FAILURES = 5;

export function useJobPolling(jobId: string | null) {
  const failureCount = useRef(0);
  const isStaleRef = useRef(false);

  const query = useQuery<JobDetail>({
    queryKey: ['job', jobId],
    queryFn: () => {
      failureCount.current = 0;
      isStaleRef.current = false;
      return getJob(jobId!);
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      if (isStaleRef.current) return false;

      if (query.state.fetchStatus === 'idle' && query.state.status === 'error') {
        failureCount.current += 1;
        if (failureCount.current >= MAX_FAILURES) {
          isStaleRef.current = true;
          return false;
        }
        return BACKOFF_INTERVAL;
      }

      const status = query.state.data?.status;
      if (status === 'queued' || status === 'running') {
        return FAST_INTERVAL;
      }

      return false;
    },
    retry: false,
  });

  const isStale = isStaleRef.current;

  return {
    job: query.data ?? null,
    isLoading: query.isLoading,
    isStale,
    error: query.error,
    refetch: query.refetch,
  };
}
