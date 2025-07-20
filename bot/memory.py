"""
Memory management system for user interactions and relationship building
"""

import sqlite3
import json
import os
from datetime import datetime

DATABASE_PATH = os.getenv('DATABASE_PATH', './sylvie_memory.db')

def init_database():
    """Initialize the SQLite database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_memory (
            user_id TEXT PRIMARY KEY,
            user_name TEXT,
            rapport_score INTEGER DEFAULT 0,
            annoyance_score INTEGER DEFAULT 0,
            last_interaction TEXT,
            memory_notes TEXT,
            interaction_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user_memory(user_id):
    """Fetch user memory data"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM user_memory WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'user_id': result[0],
            'user_name': result[1], 
            'rapport': result[2],
            'annoyance': result[3],
            'last_interaction': result[4],
            'memory_notes': result[5],
            'interaction_count': result[6],
            'created_at': result[7],
            'updated_at': result[8]
        }
    
    return {
        'user_id': user_id,
        'user_name': '',
        'rapport': 0,
        'annoyance': 0, 
        'last_interaction': '',
        'memory_notes': '',
        'interaction_count': 0,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

def update_user_memory(user_id, user_name, message, response, sentiment_change=None):
    """Update user memory with new interaction"""
    memory = get_user_memory(user_id)
    
    # Update basic info
    memory['user_name'] = user_name
    memory['last_interaction'] = f"User: {message[:50]}... | Bot: {response[:50]}..."
    memory['interaction_count'] += 1
    memory['updated_at'] = datetime.now().isoformat()
    
    # Update sentiment scores
    if sentiment_change:
        if 'rapport' in sentiment_change:
            memory['rapport'] = max(0, memory['rapport'] + sentiment_change['rapport'])
        if 'annoyance' in sentiment_change:
            memory['annoyance'] = max(0, memory['annoyance'] + sentiment_change['annoyance'])
    
    # Simple sentiment analysis
    message_lower = message.lower()
    positive_words = ['thanks', 'thank you', 'awesome', 'cool', 'love', 'great', 'amazing', 'cute']
    negative_words = ['stupid', 'dumb', 'annoying', 'hate', 'shut up', 'boring']
    
    if any(word in message_lower for word in positive_words):
        memory['rapport'] += 1
    elif any(word in message_lower for word in negative_words):
        memory['annoyance'] += 1
        
    # Decay annoyance over time (slowly)
    if memory['interaction_count'] % 10 == 0 and memory['annoyance'] > 0:
        memory['annoyance'] = max(0, memory['annoyance'] - 1)
    
    # Save to database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO user_memory 
        (user_id, user_name, rapport_score, annoyance_score, last_interaction, 
        memory_notes, interaction_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        memory['user_id'], memory['user_name'], memory['rapport'], 
        memory['annoyance'], memory['last_interaction'], memory['memory_notes'],
        memory['interaction_count'], memory['created_at'], memory['updated_at']
    ))
    
    conn.commit() 
    conn.close()
    
    return memory

def get_memory_summary(user_id):
    """Get a formatted memory summary for display"""
    memory = get_user_memory(user_id)
    return f"""
**Memory for {memory['user_name'] or 'Unknown User'}:**
- Rapport: {memory['rapport']} (friendliness level)
- Annoyance: {memory['annoyance']} (sass level)
- Interactions: {memory['interaction_count']}
- Last chat: {memory['last_interaction'] or 'None yet'}
- First met: {memory['created_at'][:10] if memory['created_at'] else 'Unknown'}
"""
