# --- Start of Original Code ---
import discord
import openai
import os
import time # Needed for polling delay

# --- Added Imports for HalcM ---
import asyncio
try:
    import tkinter as tk
    from tkinter import simpledialog
    TKINTER_AVAILABLE = True
except ImportError:
    print("WARNING: tkinter library not found. The 'HalcM' command requires it.")
    print("         On Debian/Ubuntu: sudo apt-get install python3-tk")
    print("         On Fedora: sudo dnf install python3-tkinter")
    print("         On Windows/macOS: Should be included with Python install.")
    TKINTER_AVAILABLE = False
import threading
import queue

BOT_TOKEN = "" # dont hard code this, I'm just lazy
OPENAI_API_KEY = ""
ASSISTANT_ID = ""

# --- Added Configuration for HalcM ---
# IMPORTANT: Replace 0 with your actual Discord User ID.
ALLOWED_USER_ID =  0 # <<<!!! REPLACE 0 WITH YOUR ACTUAL USER ID !!!>>>


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
if ALLOWED_USER_ID == 0:
    print("ERROR: ALLOWED_USER_ID is not set in the script.")
    print("       Please edit the script and replace 0 with your Discord User ID.")
    exit()

client_openai = openai.OpenAI(api_key=OPENAI_API_KEY)
channel_threads = {}

manual_mode_active = False
manual_mode_channel_id = None
manual_mode_lock = threading.Lock()
message_queue = queue.Queue()

intents = discord.Intents.default()
intents.message_content = True
client_discord = discord.Client(intents=intents)

# --- Added Helper Functions for HalcM ---
def _show_dialog():
    """Shows a Tkinter simpledialog and returns the input."""
    if not TKINTER_AVAILABLE: return None
    user_input = None
    try:
        root = tk.Tk()
        root.withdraw() # Hide root window
        root.attributes("-topmost", True) # Keep dialog on top
        user_input = simpledialog.askstring("Manual Bot Input", "Enter message (or 'stop' to exit):", parent=root)
        root.destroy()
    except Exception as e:
        print(f"[GUI Thread] Error creating Tkinter dialog: {e}")
        try: root.destroy()
        except: pass
    return user_input

def run_manual_input_loop(target_channel_id):
    """
    Continuously prompts the user for input via Tkinter dialog
    until 'stop' is entered or the dialog is cancelled.
    Runs in a separate thread.
    """
    global manual_mode_active, manual_mode_channel_id

    print(f"[Manual Mode Thread] Started for channel {target_channel_id}.")
    while True:
        with manual_mode_lock:
            if not manual_mode_active:
                print("[Manual Mode Thread] Mode deactivated externally. Exiting loop.")
                break

        manual_input = _show_dialog()

        if manual_input is None:
            print("[Manual Mode Thread] Dialog cancelled by user. Exiting loop.")
            break

        if manual_input.strip().lower() == 'stop':
            print("[Manual Mode Thread] 'stop' command received. Exiting loop.")
            break

        if manual_input:
            print(f"[Manual Mode Thread] Queuing message for channel {target_channel_id}: '{manual_input}'")
            message_queue.put((target_channel_id, manual_input))

    print(f"[Manual Mode Thread] Loop finished for channel {target_channel_id}.")
    with manual_mode_lock:
        if manual_mode_channel_id == target_channel_id:
            manual_mode_active = False
            manual_mode_channel_id = None
            print("[Manual Mode Thread] Manual mode deactivated.")
        else:
             print(f"[Manual Mode Thread] Warning: Manual mode state mismatch on exit? (current target: {manual_mode_channel_id})")

async def check_message_queue():
    """Periodically checks the message queue and sends messages to Discord."""
    print("[Queue Task] Starting message queue processor.")
    while True:
        try:
            channel_id, text_to_send = message_queue.get_nowait()
            target_channel = client_discord.get_channel(channel_id)
            if target_channel:
                try:
                    await target_channel.send(text_to_send)
                    print(f"[Queue Task] Sent message to channel {channel_id}.")
                    message_queue.task_done()
                except discord.Forbidden:
                    print(f"[Queue Task] Error: Missing permissions to send to channel {channel_id}.")
                except discord.HTTPException as e:
                    print(f"[Queue Task] Error: Failed to send message to channel {channel_id}: {e}")
                except Exception as e:
                     print(f"[Queue Task] Error: Unexpected error sending message to {channel_id}: {e}")
            else:
                print(f"[Queue Task] Error: Could not find channel {channel_id}. Discarding message.")
                message_queue.task_done()

        except queue.Empty:
            await asyncio.sleep(0.2)
        except Exception as e:
            print(f"[Queue Task] Error processing message queue: {e}")
            await asyncio.sleep(1)

@client_discord.event
async def on_ready():
    print(f'Logged in as {client_discord.user}')
    # Optional: Verify the Assistant ID is valid on startup
    try:
        assistant = client_openai.beta.assistants.retrieve(ASSISTANT_ID)
        print(f"Successfully connected to Assistant: {assistant.name} ({ASSISTANT_ID})")
    except openai.NotFoundError:
        print(f"ERROR: Assistant with ID '{ASSISTANT_ID}' not found. Check the ID.")
        # You might want to exit() here or handle it differently idk
    except openai.AuthenticationError:
         print("ERROR: OpenAI Authentication Failed. Check your API Key.")
         # exit()
    except Exception as e:
        print(f"ERROR: Could not retrieve Assistant {ASSISTANT_ID}: {e}")
        # exit()

    print(f'Bot is ready and listening for "Keith..." commands using Assistant ID: {ASSISTANT_ID}')

    if TKINTER_AVAILABLE:
        print(f'Listening for "HalcM" command from User ID {ALLOWED_USER_ID} to trigger local input loop.')
        # Start the background task that processes the message queue
        asyncio.create_task(check_message_queue())
    else:
        print('HalcM command disabled (tkinter not found).')

    print('------')


@client_discord.event
async def on_message(message):
    # --- Added Global State Access ---
    # Need access to modify these from within the function if HalcM is triggered
    global manual_mode_active, manual_mode_channel_id

    if message.author == client_discord.user:
        return


    # --- Added HalcM Trigger Check ---
    # Check for HalcM command *before* the Keith command check
    if message.content.lower() == 'halcm' and message.author.id == ALLOWED_USER_ID:
        if not TKINTER_AVAILABLE:
            try:
                await message.channel.send("Sorry, the local input feature requires `tkinter` which was not found.", delete_after=10)
                await message.delete()
            except Exception: pass
            return

        with manual_mode_lock: # Safely check and set state
            if manual_mode_active:
                print(f"User {message.author.id} tried HalcM, but already active for channel {manual_mode_channel_id}.")
                try:
                    await message.channel.send(f"Manual mode is already active (controlling channel <#{manual_mode_channel_id}>). Type `stop` in the local popup to exit.", delete_after=15)
                    await message.delete()
                except Exception: pass
                return

            print(f"Activating manual control mode for channel {message.channel.id} by user {message.author.id}")
            manual_mode_active = True
            manual_mode_channel_id = message.channel.id

        try: # Delete trigger message outside lock
            await message.delete()
            print(f"Deleted trigger message for HalcM.")
        except Exception as e:
            print(f"Could not delete trigger message for HalcM: {e}")

        # Start the GUI input loop in a separate thread
        gui_thread = threading.Thread(target=run_manual_input_loop,
                                      args=(message.channel.id,),
                                      daemon=True)
        gui_thread.start()

        return # Stop processing this message further

    # If manual mode is active for this channel, ignore other potential commands like Keith
    with manual_mode_lock:
        if manual_mode_active and message.channel.id == manual_mode_channel_id:
            # Don't process 'Keith' or other commands if manual mode is active in this channel
            # We already checked for the HalcM trigger itself above.
            print(f"Ignoring message from {message.author} in channel {message.channel.id} (manual mode active).")
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
        try:
            print(f"[Channel {channel_id}] Adding message to thread {thread_id}...")
            client_openai.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_prompt,
            )
        except Exception as e:
            if "No thread found" in str(e) or ("not_found" in str(e).lower() and "thread" in str(e).lower()):
                 print(f"[Channel {channel_id}] Thread {thread_id} seems to be deleted. Removing from cache and asking user to retry.")
                 if channel_id in channel_threads:
                     del channel_threads[channel_id]
                 await message.channel.send("It seems our previous conversation history was lost. Please try sending your message again to start a new one.")
            else: # Original error handling for other add message errors
                print(f"Error adding message to thread: {e}")
                await message.channel.send("Sorry, I couldn't process your message.")
            return # Return on any add message error
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

                max_poll_time = 300 # Maximum seconds to wait
                start_time = time.time()
                # --- Modified polling loop to use asyncio.sleep ---
                # Original used time.sleep(1) which blocks the event loop
                while run.status in ['queued', 'in_progress']:
                    if time.time() - start_time > max_poll_time:
                         print(f"[Channel {channel_id}] Run timed out.")
                         try:
                             print(f"[Channel {channel_id}] Attempting to cancel timed out run {run.id}...")
                             client_openai.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
                             print(f"[Channel {channel_id}] Cancel request sent for run {run.id}.")
                         except Exception as cancel_err:
                             print(f"[Channel {channel_id}] Error attempting to cancel run {run.id}: {cancel_err}")
                         await message.channel.send("Sorry, the request took too long to process.")
                         return

                    await asyncio.sleep(1.5) 
                    try: 
                        run = client_openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
                        print(f"[Channel {channel_id}] Run status: {run.status}")
                    except openai.NotFoundError:
                        print(f"[Channel {channel_id}] Error polling run {run.id}: Run or Thread not found.")
                        await message.channel.send("There was an issue tracking the AI's progress (run/thread not found).")
                        if channel_id in channel_threads: del channel_threads[channel_id]
                        return
                    except Exception as poll_err:
                        print(f"[Channel {channel_id}] Error polling run {run.id}: {poll_err}")
                        await asyncio.sleep(3)


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

                        print(f"[Channel {channel_id}] Assistant response: '{response_text}'")

                        # Send response (handle Discord length limit)
                        if len(response_text) > 2000:
                            print(f"[Channel {channel_id}] Response is long ({len(response_text)} chars), splitting.")
                            parts = []
                            current_part = ""
                            for paragraph in response_text.split('\n'):
                                if len(current_part) + len(paragraph) + 1 <= 2000:
                                    current_part += paragraph + "\n"
                                else:
                                    if current_part: parts.append(current_part.strip())
                                    if len(paragraph) > 2000:
                                         for i in range(0, len(paragraph), 1990): parts.append(paragraph[i:i+1990])
                                         current_part = ""
                                    else: current_part = paragraph + "\n"
                            if current_part: parts.append(current_part.strip())
                            for part in parts:
                                if part: await message.channel.send(part)
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
                        error_message += f" Error Code: {run.last_error.code}. Message: {run.last_error.message}"
                    # You might want specific handling for 'requires_action' if you add tools/functions later
                    await message.channel.send(error_message[:1950]) # Limit length, original just sent potentially long message
                else:
                     print(f"[Channel {channel_id}] Run ended with unexpected status: {run.status}") 
                     await message.channel.send(f"Sorry, something went wrong ({run.status}).") 

        except openai.RateLimitError:
             print("ERROR: OpenAI Rate Limit Exceeded.")
             await message.channel.send("Sorry, I'm getting too many requests right now (Rate Limit). Please try again in a moment.") 
        except openai.AuthenticationError:
             print("ERROR: OpenAI Authentication Failed. Check your API Key.")
             await message.channel.send("Sorry, there's an issue with my connection to the AI (Authentication Error). Please tell the bot owner.") 
        except openai.NotFoundError as e:
             print(f"[Channel {channel_id}] ERROR: OpenAI resource not found during run/retrieval: {e}")
             await message.channel.send("Sorry, it seems the conversation context was lost or expired before the AI could finish. Please try again.")
             if channel_id in channel_threads: del channel_threads[channel_id]
        except Exception as e:
            print(f"An unexpected error occurred during run/retrieval: {e}") 
            # Optional: Log full traceback
            # import traceback; traceback.print_exc()
            await message.channel.send("Sorry, an unexpected error occurred while getting the response.") 


try:
    client_discord.run(BOT_TOKEN)
except discord.errors.LoginFailure:
    print("\nERROR: Improper Discord token passed. Make sure the DISCORD_BOT_TOKEN is correct.")
except discord.errors.PrivilegedIntentsRequired:
    print("\nERROR: Privileged Intents (like Message Content) are required but not enabled.")
    print("Go to your bot's settings in the Discord Developer Portal and enable 'MESSAGE CONTENT INTENT'.")
except Exception as e:
    print(f"Error running Discord client: {e}")
finally:
    print("Discord client stopped.")
    with manual_mode_lock:
        if manual_mode_active:
             print("Signalling active manual mode thread to stop due to bot shutdown...")
             manual_mode_active = False
