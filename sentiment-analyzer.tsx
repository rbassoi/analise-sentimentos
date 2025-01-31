import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

const SentimentAnalyzer = () => {
  const [text, setText] = useState('');
  const [sentiment, setSentiment] = useState(null);
  const [language, setLanguage] = useState('portuguese');

  // Comprehensive lists of sentiment-indicating words
  const sentimentLists = {
    portuguese: {
      positive: [
        'bom', 'ótimo', 'excelente', 'maravilhoso', 'incrível', 
        'feliz', 'amor', 'adorável', 'fantástico', 'delicioso',
        'impressionante', 'perfeito', 'alegre', 'esperançoso', 'positivo'
      ],
      negative: [
        'ruim', 'terrível', 'horrível', 'péssimo', 'detestável', 
        'triste', 'ódio', 'frustrado', 'raiva', 'péssimo',
        'desapontado', 'chateado', 'miserável', 'depressivo', 'negativo'
      ],
      intensifiers: {
        positive: ['muito', 'extremamente', 'absolutamente', 'totalmente', 'realmente'],
        negative: ['extremamente', 'absolutamente', 'completamente', 'totalmente']
      }
    }
  };

  const analyzeSentiment = () => {
    if (!text.trim()) {
      setSentiment(null);
      return;
    }

    const lowerText = text.toLowerCase();
    const currentLangSentiments = sentimentLists[language];
    
    // Count positive and negative words
    const positiveMatches = currentLangSentiments.positive.filter(word => 
      lowerText.includes(word)
    );
    const negativeMatches = currentLangSentiments.negative.filter(word => 
      lowerText.includes(word)
    );

    // Check for intensifiers
    const positiveIntensifiers = currentLangSentiments.intensifiers.positive.filter(word => 
      lowerText.includes(word)
    );
    const negativeIntensifiers = currentLangSentiments.intensifiers.negative.filter(word => 
      lowerText.includes(word)
    );

    // Calculate sentiment score
    const positiveScore = positiveMatches.length + (positiveIntensifiers.length * 0.5);
    const negativeScore = negativeMatches.length + (negativeIntensifiers.length * 0.5);

    const sentimentScore = (positiveScore - negativeScore) / (positiveScore + negativeScore + 1);

    setSentiment({
      score: sentimentScore,
      positiveWords: positiveMatches,
      negativeWords: negativeMatches
    });
  };

  const getSentimentLabel = (score) => {
    const labels = {
      'positive': {
        highlyPositive: 'Altamente Positivo',
        positive: 'Positivo'
      },
      'negative': {
        neutral: 'Neutro',
        negative: 'Negativo',
        highlyNegative: 'Altamente Negativo'
      }
    };

    if (score > 0.5) return labels.positive.highlyPositive;
    if (score > 0) return labels.positive.positive;
    if (score === 0) return labels.negative.neutral;
    if (score > -0.5) return labels.negative.negative;
    return labels.negative.highlyNegative;
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
              Sentimento: {getSentimentLabel(sentiment.score)}
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
      </Card>
    </CardContent>
  );
};

export default SentimentAnalyzer;
