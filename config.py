"""
Configuration du projet
"""
import os

class Config:
    # Dossiers
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
    OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
    
    # Configuration Ollama (LLM local gratuit)
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "llama3.2:3b"
    
    # Configuration Flask
    FLASK_DEBUG = True
    FLASK_HOST = "127.0.0.1"
    FLASK_PORT = 5000
    
    @staticmethod
    def ensure_directories():
        """Crée les dossiers s'ils n'existent pas"""
        os.makedirs(Config.INPUT_DIR, exist_ok=True)
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)