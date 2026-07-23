"""
Autenticação OAuth 2.0 para API Idealista.
"""

import httpx
import base64
from datetime import datetime, timedelta
from typing import Optional


class IdealistaAuth:
    """Gerencia autenticação OAuth 2.0 com API Idealista."""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
    
    def _encode_credentials(self) -> str:
        """Codifica API key e secret em Base64."""
        credentials = f"{self.api_key}:{self.api_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return encoded
    
    async def get_token(self) -> str:
        """
        Obtém Bearer token (reutiliza se ainda válido).
        
        Returns:
            Access token
        """
        # Se token ainda válido, reutilizar
        if self.token and self.token_expiry:
            if datetime.now() < self.token_expiry:
                return self.token
        
        # Requisitar novo token
        url = "https://api.idealista.com/oauth/token"
        
        encoded_credentials = self._encode_credentials()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "read"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            result = response.json()
            
            self.token = result["access_token"]
            expires_in = result["expires_in"]  # segundos
            
            # Guardar expiry (com margem de 5 min)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
            
            return self.token


# Singleton
_auth_instance = None

def get_idealista_auth() -> IdealistaAuth:
    """Obtém instância singleton de autenticação."""
    global _auth_instance
    
    if _auth_instance is None:
        from utils.config import IDEALISTA_API_KEY, IDEALISTA_API_SECRET
        _auth_instance = IdealistaAuth(IDEALISTA_API_KEY, IDEALISTA_API_SECRET)
    
    return _auth_instance