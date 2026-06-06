import React, { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

type SentimentResult = {
  score: number;
  label: string;
  positiveWords: string[];
  negativeWords: string[];
};

const SentimentAnalyzer = () => {
  const [text, setText] = useState('');
  const [sentiment, setSentiment] = useState<SentimentResult | null>(null);

  const sentimentLists = useMemo(
    () => ({
      positive: [
        'bom',
        'otimo',
        'excelente',
        'maravilhoso',
        'incrivel',
        'feliz',
        'fantastico',
        'perfeito',
        'resolvido',
        'satisfeito',
      ],
      negative: [
        'ruim',
        'pessimo',
        'horrivel',
        'terrivel',
        'frustrado',
        'raiva',
        'problema',
        'erro',
        'falha',
        'insatisfeito',
      ],
    }),
    []
  );

  const normalizeText = (value: string) =>
    value
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();

  const findMatches = (lowerText: string, words: string[]) =>
    words.filter((word) => new RegExp(`\\b${word}\\b`, 'i').test(lowerText));

  const getSentimentLabel = (score: number) => {
    if (score > 0.5) return 'Altamente Positivo';
    if (score > 0) return 'Positivo';
    if (score === 0) return 'Neutro';
    if (score > -0.5) return 'Negativo';
    return 'Altamente Negativo';
  };

  const analyzeSentiment = () => {
    if (!text.trim()) {
      setSentiment(null);
      return;
    }

    const lowerText = normalizeText(text);
    const positiveMatches = findMatches(lowerText, sentimentLists.positive);
    const negativeMatches = findMatches(lowerText, sentimentLists.negative);
    const positiveScore = positiveMatches.length;
    const negativeScore = negativeMatches.length;
    const sentimentScore = (positiveScore - negativeScore) / (positiveScore + negativeScore + 1);

    setSentiment({
      score: sentimentScore,
      label: getSentimentLabel(sentimentScore),
      positiveWords: positiveMatches,
      negativeWords: negativeMatches,
    });
  };

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle>Analisador de Sentimento</CardTitle>
      </CardHeader>
      <CardContent>
        <Textarea
          placeholder="Digite o texto para análise de sentimento..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="mb-4 h-32"
        />
        <Button 
          onClick={analyzeSentiment} 
          disabled={!text.trim()}
          className="w-full"
        >
          Analisar Sentimento
        </Button>
        {sentiment && (
          <div className="mt-4 p-3 bg-gray-100 rounded">
            <p className="font-semibold">
              Sentimento: {sentiment.label}
            </p>
            <p>Pontuação de Sentimento: {sentiment.score.toFixed(2)}</p>
            {sentiment.positiveWords.length > 0 && (
              <p className="text-green-600">
                Palavras Positivas: {sentiment.positiveWords.join(', ')}
              </p>
            )}
            {sentiment.negativeWords.length > 0 && (
              <p className="text-red-600">
                Palavras Negativas: {sentiment.negativeWords.join(', ')}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default SentimentAnalyzer;
