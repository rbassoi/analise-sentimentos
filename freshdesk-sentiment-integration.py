import requests
import json

class FreshdeskSentimentIntegrator:
    def __init__(self, domain, api_key):
        self.domain = domain
        self.api_key = api_key
        self.base_url = f'https://{domain}.freshdesk.com/api/v2'

    def sentiment_analysis(self, text):
        # Basic sentiment analysis function
        positive_words = ['bom', 'ótimo', 'excelente', 'maravilhoso']
        negative_words = ['ruim', 'péssimo', 'horrível', 'terrível']
        
        text_lower = text.lower()
        positive_count = sum(word in text_lower for word in positive_words)
        negative_count = sum(word in text_lower for word in negative_words)
        
        score = (positive_count - negative_count) / (positive_count + negative_count + 1)
        
        return {
            'score': score,
            'label': self._get_sentiment_label(score)
        }

    def _get_sentiment_label(self, score):
        if score > 0.5: return 'Altamente Positivo'
        if score > 0: return 'Positivo'
        if score == 0: return 'Neutro'
        if score > -0.5: return 'Negativo'
        return 'Altamente Negativo'

    def analyze_ticket_sentiment(self, ticket_id):
        # Fetch ticket details
        ticket_url = f'{self.base_url}/tickets/{ticket_id}'
        response = requests.get(ticket_url, auth=(self.api_key, 'X'))
        ticket = response.json()

        # Analyze ticket description
        sentiment = self.sentiment_analysis(ticket['description'])

        # Update ticket with sentiment
        update_payload = {
            'custom_fields': {
                'sentiment_score': sentiment['score'],
                'sentiment_label': sentiment['label']
            }
        }
        
        update_response = requests.put(
            ticket_url, 
            json=update_payload, 
            auth=(self.api_key, 'X')
        )
        
        return sentiment

# Usage Example
def main():
    integrator = FreshdeskSentimentIntegrator(
        domain='your_domain', 
        api_key='your_api_key'
    )
    
    # Analyze sentiment for a specific ticket
    ticket_sentiment = integrator.analyze_ticket_sentiment(ticket_id=123)
    print(json.dumps(ticket_sentiment, indent=2))

if __name__ == '__main__':
    main()
