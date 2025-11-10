#!/bin/bash
# Script de configuration de MongoDB

echo "Setting up MongoDB for Service Annotation System..."

# Créer la base de données et les collections
mongosh <<EOF
use service_registry

// Créer les collections
db.createCollection("services")
db.createCollection("execution_history")

// Créer les index pour services
db.services.createIndex({"service_id": 1}, {unique: true})
db.services.createIndex({"service_name": 1})
db.services.createIndex({"functional_annotations.operations.name": 1})
db.services.createIndex({"policy_annotations.privacy.data_sensitivity": 1})

// Créer les index pour execution_history
db.execution_history.createIndex({"service_id": 1, "timestamp": -1})
db.execution_history.createIndex({"timestamp": -1})
db.execution_history.createIndex({"status": 1})
db.execution_history.createIndex({"context.user.id": 1})

// Créer un index TTL pour nettoyer l'historique ancien (optionnel)
// Supprime les enregistrements de plus de 90 jours
db.execution_history.createIndex(
  {"timestamp": 1}, 
  {expireAfterSeconds: 7776000}  // 90 jours
)

print("MongoDB setup completed successfully!")
EOF

echo "Done!"