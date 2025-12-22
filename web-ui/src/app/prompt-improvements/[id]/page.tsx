'use client';

import { use } from 'react';
import PromptAnalysisDetail from '@/components/PromptAnalysisDetail';

interface Props {
  params: Promise<{ id: string }>;
}

export default function AnalysisDetailPage({ params }: Props) {
  const { id } = use(params);
  return <PromptAnalysisDetail analysisId={id} />;
}
