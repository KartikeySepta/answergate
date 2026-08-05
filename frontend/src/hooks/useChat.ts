import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMessages, sendMessage } from '@/api/chat';
import type { ChatResponse, Message } from '@/api/types';

export function useMessages(workspaceId: string) {
  return useQuery({
    queryKey: ['messages', workspaceId],
    queryFn: () => getMessages(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation<
    ChatResponse,
    Error,
    {
      workspaceId: string;
      question: string;
      history: Pick<Message, 'role' | 'content'>[];
      mode?: string;
    }
  >({
    mutationFn: ({ workspaceId, question, history, mode }) =>
      sendMessage(workspaceId, question, history, mode),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['messages', variables.workspaceId],
      });
    },
  });
}
