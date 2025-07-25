import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SecureCredentialManager:
    """Secure credential management for API keys and sensitive data"""
    
    def __init__(self, credentials_file: str = ".secure_credentials"):
        self.credentials_file = credentials_file
        self.master_key = self._get_or_create_master_key()
        self.fernet = Fernet(self.master_key)
    
    def _get_or_create_master_key(self) -> bytes:
        """Get existing master key or create a new one"""
        if os.path.exists('.master_key'):
            try:
                with open('.master_key', 'rb') as key_file:
                    key = key_file.read()
                # Ensure proper permissions on existing file
                os.chmod('.master_key', 0o600)
                return key
            except Exception as e:
                print(f"Error reading master key: {e}")
                # If we can't read the existing key, create a new one
                return self._create_master_key()
        else:
            return self._create_master_key()
    
    def _create_master_key(self) -> bytes:
        """Create a new master key for encryption"""
        key = Fernet.generate_key()
        
        # Save the key to file with secure permissions
        with open('.master_key', 'wb') as key_file:
            key_file.write(key)
        
        # Set secure permissions (owner read/write only)
        os.chmod('.master_key', 0o600)
        
        return key
    
    def _derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def store_credential(self, key: str, value: str, encrypt: bool = True) -> bool:
        """Store a credential securely"""
        try:
            # Load existing credentials
            credentials = self._load_credentials()
            
            if encrypt:
                # Encrypt the value
                encrypted_value = self.fernet.encrypt(value.encode()).decode()
                credentials[key] = {"value": encrypted_value, "encrypted": True}
            else:
                credentials[key] = {"value": value, "encrypted": False}
            
            # Save credentials
            return self._save_credentials(credentials)
        except Exception as e:
            print(f"Error storing credential {key}: {e}")
            return False
    
    def get_credential(self, key: str) -> Optional[str]:
        """Get a credential"""
        try:
            credentials = self._load_credentials()
            if key not in credentials:
                return None
            
            cred = credentials[key]
            if cred.get("encrypted", False):
                # Decrypt the value
                decrypted_value = self.fernet.decrypt(cred["value"].encode()).decode()
                return decrypted_value
            else:
                return cred["value"]
        except Exception as e:
            print(f"Error retrieving credential {key}: {e}")
            return None
    
    def remove_credential(self, key: str) -> bool:
        """Remove a credential"""
        try:
            credentials = self._load_credentials()
            if key in credentials:
                del credentials[key]
                return self._save_credentials(credentials)
            return True
        except Exception as e:
            print(f"Error removing credential {key}: {e}")
            return False
    
    def list_credentials(self) -> list:
        """List all stored credential keys"""
        try:
            credentials = self._load_credentials()
            return list(credentials.keys())
        except Exception as e:
            print(f"Error listing credentials: {e}")
            return []
    
    def _load_credentials(self) -> Dict:
        """Load credentials from file"""
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}
    
    def _save_credentials(self, credentials: Dict) -> bool:
        """Save credentials to file"""
        try:
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            # Set secure permissions (owner read/write only)
            os.chmod(self.credentials_file, 0o600)
            return True
        except Exception as e:
            print(f"Error saving credentials: {e}")
            return False

class GoogleCredentialsManager:
    """Secure Google OAuth credentials management"""
    
    def __init__(self):
        self.secure_manager = SecureCredentialManager()
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/oauth2callback')
        
        # Store Google client credentials securely if they exist
        if self.client_id and self.client_secret:
            self.secure_manager.store_credential('google_client_id', self.client_id, encrypt=False)
            self.secure_manager.store_credential('google_client_secret', self.client_secret, encrypt=True)
    
    def get_client_config(self) -> Dict:
        """Get Google OAuth client configuration"""
        client_id = self.secure_manager.get_credential('google_client_id') or self.client_id
        client_secret = self.secure_manager.get_credential('google_client_secret') or self.client_secret
        
        if not client_id or not client_secret:
            raise ValueError("Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file")
        
        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [self.redirect_uri],
                "javascript_origins": [self.redirect_uri.replace('/oauth2callback', '')]
            }
        }
    
    def store_user_credentials(self, credentials_data: Dict) -> bool:
        """Store user OAuth credentials securely"""
        try:
            # Store each credential component separately and encrypted
            for key, value in credentials_data.items():
                self.secure_manager.store_credential(f'google_user_{key}', str(value), encrypt=True)
            return True
        except Exception as e:
            print(f"Error storing user credentials: {e}")
            return False
    
    def get_user_credentials(self) -> Optional[Dict]:
        """Get user OAuth credentials"""
        try:
            # Standard OAuth fields
            fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
            credentials = {}
            
            for field in fields:
                value = self.secure_manager.get_credential(f'google_user_{field}')
                if value:
                    credentials[field] = value
            
            # Add client info if not present
            if 'client_id' not in credentials:
                client_config = self.get_client_config()
                credentials['client_id'] = client_config['web']['client_id']
                credentials['client_secret'] = client_config['web']['client_secret']
                credentials['token_uri'] = client_config['web']['token_uri']
            
            return credentials if credentials else None
        except Exception as e:
            print(f"Error retrieving user credentials: {e}")
            return None
    
    def clear_user_credentials(self) -> bool:
        """Clear user OAuth credentials"""
        try:
            fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
            for field in fields:
                self.secure_manager.remove_credential(f'google_user_{field}')
            return True
        except Exception as e:
            print(f"Error clearing user credentials: {e}")
            return False
    
    def has_valid_credentials(self) -> bool:
        """Check if valid user credentials exist"""
        credentials = self.get_user_credentials()
        if not credentials:
            return False
        
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
        return all(field in credentials for field in required_fields)
    
    def _auto_migrate_from_json(self) -> bool:
        """Automatically migrate from old user_credentials.json file"""
        try:
            if os.path.exists('user_credentials.json'):
                print("🔄 Auto-migrating credentials from user_credentials.json...")
                
                with open('user_credentials.json', 'r') as f:
                    user_creds = json.load(f)
                
                # Store in secure storage
                success = self.store_user_credentials(user_creds)
                
                if success:
                    print("✅ Credentials migrated successfully!")
                    # Create backup and remove original
                    if not os.path.exists('.backup'):
                        os.makedirs('.backup')
                    
                    os.rename('user_credentials.json', '.backup/user_credentials.json.auto_migrated')
                    print("📦 Original file backed up to .backup/user_credentials.json.auto_migrated")
                    return True
                else:
                    print("❌ Failed to migrate credentials")
                    return False
            
            return False
        except Exception as e:
            print(f"❌ Auto-migration error: {e}")
            return False
