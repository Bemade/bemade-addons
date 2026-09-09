# Lost Messages Routing - AI Improvements

AI-powered automatic classification of lost/unattached email messages using OpenWebUI.

## Features

### 1. Automatic AI Classification
- Uses OpenWebUI (or any OpenAI-compatible API) to automatically classify lost messages
- Analyzes email subject, body, and sender to determine the appropriate subcategory
- Supports all subcategories from `mail_manual_routing_ux`: spam, bounce, auto-reply, legitimate, new inquiry, finance, vendor

### 2. Confidence Scoring
- Each AI classification includes a confidence score (0-100%)
- Visual indicators in list view:
  - Green: ≥80% confidence (high confidence)
  - Orange: 50-79% confidence (medium confidence)
  - Red: <50% confidence (low confidence)

### 3. Configurable Settings
Configure the AI integration in **Settings > General Settings > Lost Messages AI**:
- **OpenWebUI URL**: Base URL of your OpenWebUI server (e.g., `http://localhost:3000`)
- **API Key**: Optional API key for authentication
- **Model Name**: LLM model to use (e.g., `glm-5:cloud`, `llama3`, `mistral`, `gpt-4`)
- **Auto-Classify**: Enable automatic classification of new unattached messages
- **Confidence Threshold**: Minimum confidence level to auto-apply classification

### 4. Manual Classification
- Click **AI Classify** button on any unattached message to manually trigger classification
- Select multiple messages in list view and use **Action > AI Classify Messages**

### 5. Classification History
- `ai_classification_date`: Timestamp of when AI classified the message
- AI reasoning is appended to the message's "Extra Lost Details" field

## Configuration

### OpenWebUI Setup

1. The module comes pre-configured with:
   ```
   OpenWebUI URL: https://ai.3387.vezina.biz
   Model Name: glm-5:cloud
   Auto-Classify: Disabled (enable manually)
   Confidence Threshold: 80%
   ```

2. To customize, go to **Settings > General Settings > Lost Messages AI**
3. Optionally add an API Key if your server requires authentication

### Supported APIs

This module works with any OpenAI-compatible API:
- OpenWebUI (recommended)
- OpenAI API
- Azure OpenAI
- Local LLM servers (ollama, text-generation-webui, etc.)

## Usage

### Automatic Mode
1. Enable "Auto-Classify New Messages" in settings
2. Set confidence threshold (recommended: 80%)
3. New unattached messages will be automatically classified

### Manual Mode
1. Navigate to **Discuss > Lost Messages**
2. Select one or more messages
3. Click **AI Classify** button or **Action > AI Classify Messages**

## Technical Details

### API Integration
- Uses OpenAI-compatible `/api/chat/completions` endpoint
- Low temperature (0.1) for consistent classification
- Timeout: 30 seconds per request

### Classification Prompt
The AI receives:
- Available subcategories with descriptions
- Email metadata (from, subject, body preview)
- Structured JSON response format requirement

### Response Format
```json
{
  "category": "spam",
  "confidence": 95.5,
  "reasoning": "Unsolicited marketing email with promotional content"
}
```

## Dependencies

- `mail_manual_routing`: Base lost messages routing functionality
- `mail_manual_routing_ux`: Subcategories and UX improvements
- Python `requests` library

## Author

Bemade Inc. - https://bemade.org

## License

LGPL-3
