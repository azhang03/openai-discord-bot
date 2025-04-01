import discord
import openai
import os
import time # Needed for polling delay

BOT_TOKEN = "" # Probably should create environment variables for this instead
OPENAI_API_KEY = ""

# --- Assistant Configuration ---
# IMPORTANT: You MUST set this environment variable with the ID
#            of the assistant you created in the OpenAI portal.
ASSISTANT_ID = ""

# --- End Configuration ---

# Check if keys and ID are loaded
if not BOT_TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN environment variable not set.")
    exit()
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY environment variable not set.")
    exit()
if not ASSISTANT_ID:
    print("ERROR: ASSISTANT_ID environment variable not set.")
    print("Please create an Assistant in the OpenAI portal (platform.openai.com/assistants)")
    print("and set its ID (asst_...) as the ASSISTANT_ID environment variable.")
    exit()

# Configure the OpenAI client (v1.x.x or higher syntax)
client_openai = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- Thread Management ---
# Dictionary to store mapping of Discord channel ID to OpenAI Thread ID
# Note: This is in-memory and will reset on bot restart.
# For persistence, you'd store this in a database or file.
channel_threads = {}

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
client_discord = discord.Client(intents=intents)

# --- Discord Event Handlers ---
@client_discord.event
async def on_ready():
    print(f'Logged in as {client_discord.user}')
    # Optional: Verify the Assistant ID is valid on startup
    try:
        assistant = client_openai.beta.assistants.retrieve(ASSISTANT_ID)
        print(f"Successfully connected to Assistant: {assistant.name} ({ASSISTANT_ID})")
    except openai.NotFoundError:
        print(f"ERROR: Assistant with ID '{ASSISTANT_ID}' not found. Check the ID.")
        # You might want to exit() here or handle it differently
    except openai.AuthenticationError:
         print("ERROR: OpenAI Authentication Failed. Check your API Key.")
         # exit()
    except Exception as e:
        print(f"ERROR: Could not retrieve Assistant {ASSISTANT_ID}: {e}")
        # exit()

    print(f'Bot is ready and listening for "Keith..." commands using Assistant ID: {ASSISTANT_ID}')
    print('------')

@client_discord.event
async def on_message(message):
    if message.author == client_discord.user:
        return

    if message.content.lower().startswith('keith'):
        # Assistant ID is checked on startup, so we assume it's valid here
        # if not ASSISTANT_ID: # This check is redundant now but harmless
        #      await message.channel.send("Sorry, the Assistant ID is not configured correctly.")
        #      return

        trigger_phrase = "Keith"
        try:
            start_index = message.content.lower().index(trigger_phrase.lower())
            user_prompt = message.content[start_index + len(trigger_phrase):].strip()
        except ValueError:
            return # Should not happen if startswith passed

        if not user_prompt:
            # await message.channel.send("Hi! You need to ask me something after 'Keith'.")
            return

        channel_id = message.channel.id
        print(f"\n[Channel {channel_id}] Received prompt from {message.author}: '{user_prompt}'")

        # --- Get or Create Thread ---
        thread_id = channel_threads.get(channel_id)
        if thread_id is None:
            print(f"[Channel {channel_id}] Creating new thread...")
            try:
                thread = client_openai.beta.threads.create()
                thread_id = thread.id
                channel_threads[channel_id] = thread_id
                print(f"[Channel {channel_id}] Created thread ID: {thread_id}")
            except Exception as e:
                print(f"Error creating thread: {e}")
                await message.channel.send("Sorry, I couldn't start a new conversation thread.")
                return
        else:
            print(f"[Channel {channel_id}] Using existing thread ID: {thread_id}")

        # --- Add Message to Thread ---
        try:
            print(f"[Channel {channel_id}] Adding message to thread {thread_id}...")
            client_openai.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_prompt,
            )
        except Exception as e:
            print(f"Error adding message to thread: {e}")
            await message.channel.send("Sorry, I couldn't process your message.")
            return

        # --- Run the Assistant ---
        try:
            print(f"[Channel {channel_id}] Creating run for thread {thread_id} with assistant {ASSISTANT_ID}...")
            async with message.channel.typing(): # Show "typing..." in Discord
                run = client_openai.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=ASSISTANT_ID,
                    # Instructions/model are defined in the portal assistant, no need to override here
                    # unless you specifically want to for a single run.
                )
                print(f"[Channel {channel_id}] Created run ID: {run.id}")

                # --- Poll for Run Completion ---
                max_poll_time = 300 # Maximum seconds to wait
                start_time = time.time()
                while run.status in ['queued', 'in_progress']:
                    if time.time() - start_time > max_poll_time:
                         print(f"[Channel {channel_id}] Run timed out.")
                         await message.channel.send("Sorry, the request took too long to process.")
                         return

                    time.sleep(1) # Wait 1 second before checking status again
                    run = client_openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
                    print(f"[Channel {channel_id}] Run status: {run.status}")

                if run.status == 'completed':
                    print(f"[Channel {channel_id}] Run completed. Retrieving messages...")
                    messages = client_openai.beta.threads.messages.list(
                        thread_id=thread_id,
                        order='desc' # Latest messages first
                    )
                    # Find the latest message from the assistant for this run
                    assistant_message = None
                    for msg in messages.data:
                        if msg.run_id == run.id and msg.role == 'assistant':
                            assistant_message = msg
                            break # Found the newest relevant message

                    if assistant_message and assistant_message.content:
                        response_text = ""
                        for content_block in assistant_message.content:
                            if content_block.type == 'text':
                                response_text += content_block.text.value
                                # If you expect multiple text blocks, remove the break
                                break

                        print(f"[Channel {channel_id}] Assistant response: '{response_text}'")
                        # Send response (handle Discord length limit)
                        if len(response_text) > 2000:
                            for i in range(0, len(response_text), 2000):
                                await message.channel.send(response_text[i:i+2000])
                        elif len(response_text) > 0:
                            await message.channel.send(response_text)
                        else:
                             await message.channel.send("I received an empty response.")
                    else:
                        print(f"[Channel {channel_id}] No assistant message found for run {run.id}")
                        await message.channel.send("Sorry, I couldn't retrieve a response for this interaction.")

                elif run.status in ['failed', 'cancelled', 'expired', 'requires_action']:
                    # requires_action is for function calling, which we aren't using here yet
                    print(f"[Channel {channel_id}] Run ended with status: {run.status}")
                    error_message = f"Sorry, the process ended with status: {run.status}."
                    if run.last_error:
                        error_message += f" Error: {run.last_error.message}"
                    # You might want specific handling for 'requires_action' if you add tools/functions later
                    await message.channel.send(error_message)
                else:
                     print(f"[Channel {channel_id}] Run ended with unexpected status: {run.status}")
                     await message.channel.send(f"Sorry, something went wrong ({run.status}).")

        except openai.RateLimitError:
             print("ERROR: OpenAI Rate Limit Exceeded.")
             await message.channel.send("Sorry, I'm getting too many requests right now (Rate Limit). Please try again in a moment.")
        except openai.AuthenticationError:
             print("ERROR: OpenAI Authentication Failed. Check your API Key.")
             await message.channel.send("Sorry, there's an issue with my connection to the AI (Authentication Error). Please tell the bot owner.")
        except Exception as e:
            print(f"An unexpected error occurred during run/retrieval: {e}")
            await message.channel.send("Sorry, an unexpected error occurred while getting the response.")


# --- Run the Bot ---
try:
    client_discord.run(BOT_TOKEN)
except discord.errors.LoginFailure:
    print("\nERROR: Improper Discord token passed. Make sure the DISCORD_BOT_TOKEN is correct.")
except discord.errors.PrivilegedIntentsRequired:
    print("\nERROR: Privileged Intents (like Message Content) are required but not enabled.")
    print("Go to your bot's settings in the Discord Developer Portal and enable 'MESSAGE CONTENT INTENT'.")
except Exception as e:
    print(f"Error running Discord client: {e}")
