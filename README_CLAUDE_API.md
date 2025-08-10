# Claude API Integration

The Cosmic Guru backend integrates with Claude AI for personality analysis based on astrological charts.

## Setup

### 1. Get Claude API Key
1. Visit [https://console.anthropic.com/](https://console.anthropic.com/)
2. Create an account or sign in
3. Generate an API key

### 2. Configure Environment Variable
The backend automatically loads environment variables from a `.env` file in the backend directory.

Create or update the `.env` file:
```
ANTHROPIC_API_KEY=your-api-key-here
```

Alternatively, you can set it as a system environment variable:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### 3. Test the Integration
Run the server and test the personality analysis endpoint:

```bash
# Start the server
python main.py

# Test with curl (replace with actual chart data)
curl -X POST "http://localhost:8000/api/analyze-personality" \
  -H "Content-Type: application/json" \
  -d '{
    "chart": {...},
    "analysisType": "comprehensive"
  }'
```

## API Endpoints

### POST /api/analyze-personality
Analyzes personality based on astrological chart data.

**Request Body:**
```json
{
  "chart": {
    // AstrologicalChart object from /api/generate-chart
  },
  "analysisType": "comprehensive", // "comprehensive" | "quick" | "specific"
  "focusAreas": ["personality", "career", "relationships"] // optional
}
```

**Response:**
```json
{
  "overview": "Comprehensive personality overview...",
  "strengths": [
    {
      "name": "Leadership",
      "description": "Natural ability to guide others...",
      "strength": 8
    }
  ],
  "challenges": [
    {
      "name": "Impatience",
      "description": "Learning to slow down and consider...",
      "strength": 6
    }
  ],
  "relationships": "Relationship patterns and compatibility...",
  "career": "Career strengths and ideal environments...",
  "lifePath": "Life purpose and spiritual growth direction..."
}
```

## Security

- API keys are stored as environment variables (never in code)
- All Claude API calls are made from the backend only
- Frontend never has direct access to the Claude API
- Proper error handling prevents API key exposure

## Models Used

- **Primary**: `claude-3-haiku-20240307` (fast, cost-effective)
- **Max Tokens**: 2000 (sufficient for detailed analysis)
- **Temperature**: 0.7 (balanced creativity and consistency)

## Error Handling

- **503 Service Unavailable**: API key not configured
- **503 AI Service Error**: Claude API errors (rate limits, network issues)
- **500 Internal Server Error**: Parsing or processing errors

## Cost Considerations

Claude API pricing is based on tokens used. The personality analysis typically uses:
- Input: ~500-1000 tokens (chart summary + prompt)
- Output: ~1000-2000 tokens (detailed analysis)
- Total: ~1500-3000 tokens per analysis

Estimated cost: $0.003-$0.006 per analysis (as of 2024)