#!/usr/bin/env python3
"""
Utility script for generating WebSocket authentication tokens
"""

import sys
import time
import jwt

# These should match the values in ws_server.py
JWT_SECRET = "your-secret-key"  # Should be loaded from config in production
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

def generate_token(user_id: str) -> str:
    """Generate a JWT authentication token for a user"""
    try:
        payload = {
            'user_id': user_id,
            'exp': time.time() + (TOKEN_EXPIRY_HOURS * 3600),  # Expire in 24 hours
            'iat': time.time()
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token
        
    except Exception as e:
        print(f"Error generating auth token: {e}")
        raise

def validate_token(token: str) -> dict:
    """Validate a JWT token and return the payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

def main():
    if len(sys.argv) != 2:
        print("Usage: python ws_auth.py <user_id>")
        print("Example: python ws_auth.py 123456789012345678")
        sys.exit(1)
    
    user_id = sys.argv[1]
    
    try:
        token = generate_token(user_id)
        print(f"Generated token for user {user_id}:")
        print(token)
        print(f"\nToken expires in {TOKEN_EXPIRY_HOURS} hours")
        
        # Validate the token we just created
        payload = validate_token(token)
        print(f"\nToken validation successful:")
        print(f"User ID: {payload['user_id']}")
        print(f"Issued at: {time.ctime(payload['iat'])}")
        print(f"Expires at: {time.ctime(payload['exp'])}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 