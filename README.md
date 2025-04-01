# Keith - Discord AI Chat Bot

A Python-based Discord bot named "Keith" that uses the OpenAI Assistants API to provide intelligent and context-aware responses when mentioned.

This is a revamped version of a Discord bot I made all the way back in my Sophomore year before ChatGPT was even really a thing. I had a bunch of if-statements tied to various use cases back then that have now been lost. I decided to revive the bot seeing how I still have the application registered on the Discord Dev Portal.
## Features

*   Listens for messages starting with "Keith" (case-insensitive).
*   Connects to a pre-configured OpenAI Assistant using its ID.
*   Leverages the OpenAI Assistants API for generating responses.
*   Maintains conversation history per Discord channel using OpenAI Threads.
*   Configurable via environment variables for security.
*   Shows a "typing..." indicator while processing requests.

## Prerequisites

Before you begin, ensure you have the following:

1.  **Python:** Version 3.8 or higher recommended.
2.  **pip:** Python package installer (usually comes with Python).
3.  **Discord Bot Application:**
    *   An existing Discord application with a Bot user created via the [Discord Developer Portal](https://discord.com/developers/applications).
    *   The bot must be invited to your Discord server(s).
    *   The **`MESSAGE CONTENT INTENT`** must be enabled for the bot in the Developer Portal under the "Bot" tab.
4.  **OpenAI Account & API Key:**
    *   An account on the [OpenAI Platform](https://platform.openai.com/).
    *   An active API Key ([https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)).
    *   Billing enabled on your OpenAI account (it straight up will not let you call the API unless you have a payment method attached).
5.  **OpenAI Assistant ID:**
    *   An Assistant created via the OpenAI Platform ([https://platform.openai.com/assistants](https://platform.openai.com/assistants)). You will need its ID (starting with `asst_...`). Configure its instructions, model (e.g., `gpt-4o-mini`, `gpt-4-turbo`), and any tools directly in the OpenAI portal.
