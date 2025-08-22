import os
from supabase import create_client, Client

# LINE Bot Configuration
BOT_MENTION = os.environ.get('BOT_MENTION', '@billybot')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')

# Supabase Configuration  
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')

# Check if all required environment variables are set
if not all([LINE_CHANNEL_ACCESS_TOKEN, SUPABASE_URL, SUPABASE_ANON_KEY]):
    raise ValueError("Missing required environment variables")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)