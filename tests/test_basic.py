"""
Basic tests for Sylvie bot functionality
"""

import unittest
import sys
import os

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from bot.memory import init_database, get_user_memory, update_user_memory
from bot.personality import build_prompt, get_random_emoticon

class TestSylvieBot(unittest.TestCase):
    
    def setUp(self):
        """Set up test database"""
        os.environ['DATABASE_PATH'] = ':memory:'  # Use in-memory database
        init_database()
    
    def test_memory_system(self):
        """Test user memory creation and updates"""
        user_id = "test123"
        memory = get_user_memory(user_id)
        
        self.assertEqual(memory['rapport'], 0)
        self.assertEqual(memory['annoyance'], 0)
        
        # Update memory
        updated = update_user_memory(user_id, "TestUser", "Hello", "Hi there!")
        self.assertEqual(updated['user_name'], "TestUser")
        self.assertEqual(updated['interaction_count'], 1)
    
    def test_personality_prompts(self):
        """Test prompt building"""
        prompt = build_prompt("TestUser", "Hello", rapport=5, annoyance=0)
        self.assertIn("TestUser", prompt)
        self.assertIn("Rapport Score: 5", prompt)
    
    def test_emoticons(self):
        """Test emoticon generation"""
        # Test with 100% chance
        emoticon = get_random_emoticon(1.0)
        self.assertTrue(len(emoticon) > 0)
        
        # Test with 0% chance
        emoticon = get_random_emoticon(0.0)
        self.assertEqual(emoticon, "")

if __name__ == '__main__':
    unittest.main()
