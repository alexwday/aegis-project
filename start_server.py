#!/usr/bin/env python3
"""
Simple script to start the AEGIS FastAPI server for testing the chat interface.
"""

import uvicorn
import sys
import os

# Add the services package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Starting AEGIS FastAPI Server...")
    print("📱 Chat Interface: Open chat_interface.html in your browser")
    print("📋 API Docs: http://localhost:8000/docs")
    print("🔍 Health Check: http://localhost:8000/health")
    print("\n⚠️  Make sure your environment variables are set:")
    print("   - OPENAI_API_KEY (if using OpenAI)")
    print("   - Database connection strings (when implementing real databases)")
    print("\n🛑 Press Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "services.src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )