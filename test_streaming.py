#!/usr/bin/env python3
"""Test script to verify SUBAGENT_COMPLETE markers in streaming response"""

import requests
import json

def test_streaming():
    """Test the streaming endpoint to see if SUBAGENT_COMPLETE markers are present"""
    
    url = "http://localhost:8000/chat"
    
    # Test message
    payload = {
        "messages": [
            {"role": "user", "content": "What are the latest earnings results for RBC?"}
        ],
        "stream": True,
        "db_names": ["earnings_transcripts", "quarterly_reports"]
    }
    
    try:
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
        
        print("=== Streaming Response ===")
        full_response = ""
        subagent_markers_found = []
        
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            if chunk:
                full_response += chunk
                print(chunk, end='', flush=True)
                
                # Check for SUBAGENT_COMPLETE markers
                if 'SUBAGENT_COMPLETE:' in chunk:
                    import re
                    matches = re.findall(r'SUBAGENT_COMPLETE:(.+?)(?=\n|$)', chunk)
                    for match in matches:
                        try:
                            data = json.loads(match)
                            subagent_markers_found.append(data)
                            print(f"\n\n[FOUND SUBAGENT DATA]: {data['name']}")
                        except:
                            print(f"\n\n[ERROR PARSING SUBAGENT DATA]: {match}")
        
        print("\n\n=== Summary ===")
        print(f"Total subagent markers found: {len(subagent_markers_found)}")
        for marker in subagent_markers_found:
            print(f"- {marker.get('name', 'Unknown')}: {marker.get('status', 'Unknown')}")
        
        # Check for --- separators
        separator_count = full_response.count('---')
        print(f"\nFound {separator_count} '---' separators in response")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_streaming()