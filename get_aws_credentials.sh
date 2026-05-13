#!/bin/bash
# get_aws_credentials.sh - Obtener credenciales temporales del IAM role
#
# Uso:
#   source get_aws_credentials.sh
#   python scripts/TEMP_score_phones.py 573228313778

echo "📍 Obteniendo credenciales temporales del IAM role..."

# Obtener credenciales temporales (1 hora)
CREDS=$(aws sts get-session-token --duration-seconds 3600 --output json)

if [ $? -ne 0 ]; then
    echo "❌ Error al obtener credenciales"
    echo "   Verificar: aws sts get-caller-identity"
    exit 1
fi

# Extraer valores
export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | jq -r '.Credentials.SessionToken')

echo "✅ Credenciales configuradas:"
echo "   Access Key ID: ${AWS_ACCESS_KEY_ID:0:10}..."
echo "   Session Token: ${AWS_SESSION_TOKEN:0:10}..."
echo ""
echo "Ahora puedes ejecutar:"
echo "   uv run python scripts/TEMP_score_phones.py 573228313778"
