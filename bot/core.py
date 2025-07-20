"""
Main Discord bot with Mistral-7B integration for Sylvie
"""

import os
import re
import asyncio
import discord
from discord.ext import commands
from transformers import pipeline
import torch
from dotenv import load_dotenv
import wikipedia
import sqlite3

from .memory import init_database, get_user_memory, update_user_memory, get_memory_summary
from .personality import build_prompt, get_random_emoticon

# Load environment variables
load_dotenv()

# Initialize database
init_database()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Mistral model
print("Loading Mistral-7B-Instruct-v0.3...")
generator = None

def load_model():
    """Load the Mistral model"""
    global generator
    try:
        generator = pipeline(
            "text-generation",
            model="mistralai/Mistral-7B-Instruct-v0.3",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
            # Use 8-bit quantization if available for memory efficiency
            model_kwargs={"load_in_8bit": True} if torch.cuda.is_available() else {}
        )
        print("[OK] Mistral model loaded successfully!")
    except Exception as e:
        print(f"[Error] Error loading Mistral model: {e}")
        print("[Fallback] Falling back to a smaller model...")
        # Fallback to a smaller model if Mistral fails
        generator = pipeline("text-generation", model="microsoft/DialoGPT-medium")

@bot.event
async def on_ready():
    print(f'[OK] {bot.user} (Sylvie) is online!')
    print(f'[Info] Connected to {len(bot.guilds)} servers')
    
    # Load model after bot is ready
    if generator is None:
        load_model()

@bot.event 
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
        
    # Process commands first
    await bot.process_commands(message)
    
    # Don't respond to commands
    if message.content.startswith('!'):
        return
    
    try:
        # Get user info and memory
        user_id = str(message.author.id)
        user_name = message.author.display_name
        memory = get_user_memory(user_id)
        
        # Check if this is Nex (special treatment)
        is_nex = user_name.lower() == "nex" or "nex" in user_name.lower()
        
        # Build context for the model
        memory_context = f"Interactions: {memory['interaction_count']}, Last: {memory['last_interaction'][:100] if memory['last_interaction'] else 'First time meeting'}"
        
        # Handle knowledge queries with Wikipedia
        knowledge_answer = ""
        if any(trigger in message.content.lower() for trigger in ["what is", "tell me about", "who is", "explain"]):
            try:
                # Extract the topic (simple approach)
                content = message.content.lower()
                topic = content.split("what is")[-1] if "what is" in content else \
                        content.split("tell me about")[-1] if "tell me about" in content else \
                        content.split("who is")[-1] if "who is" in content else \
                        content.split("explain")[-1] if "explain" in content else ""
                
                if topic.strip():
                    wiki = wikipedia.summary(topic.strip(), sentences=2)
                    knowledge_answer = f"\nKnowledge: {wiki}"
            except wikipedia.exceptions.PageError:
                knowledge_answer = "\nKnowledge: I couldn't find a Wikipedia page for that topic."
            except wikipedia.exceptions.DisambiguationError as e:
                knowledge_answer = f"\nKnowledge: '{topic}' could mean multiple things. Try being more specific? (Options: {e.options[:3]})"
            except Exception as e:
                knowledge_answer = f"\nKnowledge: Something went wrong looking that up: {str(e)}"
        
        # Build the prompt
        full_prompt = build_prompt(
            user_name=user_name,
            user_message=message.content + knowledge_answer,
            rapport=memory['rapport'],
            annoyance=memory['annoyance'], 
            memory_context=memory_context
        )
        
        # Add special context for Nex
        if is_nex:
            full_prompt += "\n\nIMPORTANT: This is Nex, your beloved papa figure. Be extra sweet and loving!"
        
        # Generate response with typing indicator
        async with message.channel.typing():
            if generator is None:
                await message.reply("*flops sadly* My AI brain isn't loaded yet, give me a moment! (˶ᵔ ᵕ ˂˶)")
                return
                
            # Generate response
            result = generator(
                full_prompt,
                max_new_tokens=int(os.getenv('MAX_TOKENS', 120)),
                do_sample=True,
                temperature=float(os.getenv('TEMPERATURE', 0.9)),
                top_p=0.9,
                pad_token_id=generator.tokenizer.eos_token_id if hasattr(generator.tokenizer, 'eos_token_id') else None
            )
            
            # Extract the response text
            generated_text = result[0]['generated_text']
            
            # Clean up the response (remove the prompt part)
            response = generated_text.split('[/INST]')[-1].strip()
            
            # Remove any unwanted tokens
            response = re.sub(r'<s>|</s>', '', response).strip()
            
            # Add random emoticon
            emoticon = get_random_emoticon(0.3)
            if emoticon and not any(emote in response for emote in ['(', ')', 'ᵕ', '˶']):
                response += f" {emoticon}"
            
            # Ensure response isn't too long
            if len(response) > 400:
                response = response[:350] + "... *gets distracted* ∧,,,∧"
            
            # Send response
            await message.reply(response, mention_author=False)
            
            # Update memory
            update_user_memory(user_id, user_name, message.content, response)
            
    except Exception as e:
        print(f"[Error] Error processing message: {e}")
        await message.reply("*tilts head confused* Something went wrong with my dragon brain! Try again? (˶ᵔ ᵕ ˂˶)")

# Commands
@bot.command(name='memory')
async def check_memory(ctx):
    """Check what Sylvie remembers about you"""
    user_id = str(ctx.author.id)
    summary = get_memory_summary(user_id)
    await ctx.send(summary)

@bot.command(name='forget')
async def forget_user(ctx, user_mention=None):
    """Reset memory for a user (mention them or use on yourself)"""
    if user_mention:
        # Extract user ID from mention
        user_id = re.findall(r'\d+', user_mention)
        if user_id:
            user_id = user_id[0]
        else:
            await ctx.send("Invalid user mention!")
            return
    else:
        user_id = str(ctx.author.id)
    
    # Reset memory by deleting from database
    conn = sqlite3.connect(os.getenv('DATABASE_PATH', './sylvie_memory.db'))
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_memory WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await ctx.send("*poof* Memory wiped clean! Like meeting for the first time~ (˶ᵔ ᵕ ˂˶)")

@bot.command(name='stats')
async def bot_stats(ctx):
    """Show bot statistics"""
    conn = sqlite3.connect(os.getenv('DATABASE_PATH', './sylvie_memory.db'))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*), SUM(interaction_count), AVG(rapport_score) FROM user_memory')
    stats = cursor.fetchone()
    conn.close()
    
    users, total_interactions, avg_rapport = stats
    await ctx.send(f"""
**Sylvie's Stats** (∧,,,∧)
- Users I remember: {users or 0}
- Total conversations: {total_interactions or 0} 
- Average rapport: {avg_rapport:.1f if avg_rapport else 0}/10
- Servers: {len(bot.guilds)}
""")

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("[Error] No Discord token found! Add it to your .env file.")
    else:
        bot.run(token)
