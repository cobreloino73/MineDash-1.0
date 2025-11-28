# backend/config.py
"""
MineDash AI - Configuration
División Salvador, Codelco Chile
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Config:
    """Configuración central de MineDash AI"""
    
    # ============================================
    # PATHS
    # ============================================
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    LIGHTRAG_DIR = BASE_DIR / "lightrag_storage"
    
    # ============================================
    # API KEYS
    # ============================================
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # ============================================
    # MODELS
    # ============================================
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    # ============================================
    # SYSTEM
    # ============================================
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls):
        """Valida que las configuraciones críticas estén presentes"""
        errors = []
        
        if not cls.ANTHROPIC_API_KEY:
            errors.append("❌ ANTHROPIC_API_KEY no configurada")
        
        if not cls.GEMINI_API_KEY:
            errors.append("❌ GEMINI_API_KEY no configurada")
        
        if errors:
            print("\n".join(errors))
            raise ValueError("Configuración incompleta. Revisa tu archivo .env")
        
        print("✅ Configuración validada correctamente")
        return True

# Validar al importar
if __name__ == "__main__":
    Config.validate()
