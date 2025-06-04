import requests
import json
import time
from pprint import pprint

# Test credentials - these don't need to be real for our test
# We just want to verify the structure of the response
test_creds = {
    "access_key": "AKIAIOSFODNN7EXAMPLE",
    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "session_token": None,  # Can be None for long-term credentials
    "environment": "com"
}

base_url = "http://localhost:8000/api/auth"

def test_credential_validation():
    """Test that credential validation returns expiration info"""
    print("\n=== Testing credential validation with expiration info ===\n")
    
    try:
        # Send validation request
        print("Sending credential validation request...")
        response = requests.post(f"{base_url}/aws-credentials", json=test_creds)
        
        # Parse response
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Response status code: {response.status_code}")
            print("\nResponse content:")
            pprint(result)
            
            # Check if response includes expiration info
            if "expiration" in result:
                print("\n✅ Validation successful! Response includes expiration information.")
                
                # Calculate and display time until expiration
                if result.get("expires_in_seconds"):
                    print(f"Credentials will expire in {result['expires_in_minutes']} minutes "
                          f"({result['expires_in_seconds']} seconds)")
            else:
                print("\n❌ Response doesn't include expiration information.")
        else:
            print(f"Error: Received status code {response.status_code}")
            print("Response content:")
            print(response.text)
            
    except Exception as e:
        print(f"Error during test: {str(e)}")

if __name__ == "__main__":
    test_credential_validation()
