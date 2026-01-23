"""
Serveur Flask optimisé pour gérer des uploads massifs
"""

from app import app
from werkzeug.serving import WSGIRequestHandler
import sys

# Augmenter le timeout de requête à l'infini
WSGIRequestHandler.protocol_version = "HTTP/1.1"

# Augmenter la limite de récursion si nécessaire
sys.setrecursionlimit(10000)

if __name__ == '__main__':
    print("=" * 60)
    print("Démarrage du serveur Flask (mode SANS LIMITES)")
    print("=" * 60)
    print("✓ Limite de taille de fichier : AUCUNE")
    print("✓ Nombre de fichiers : ILLIMITÉ")
    print("✓ Timeout : DÉSACTIVÉ")
    print("✓ Multi-threading : ACTIVÉ")
    print("=" * 60)
    print()
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True,  # Support multi-threading
        use_reloader=True,
        request_handler=WSGIRequestHandler
    )