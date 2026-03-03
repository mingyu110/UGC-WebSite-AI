#!/bin/bash
# =============================================================================
# Create Node.js Dependencies Lambda Layer
# =============================================================================
# This creates a Lambda Layer with common Node.js dependencies:
# - express
# - cors
# - body-parser
# - uuid
# - @aws-sdk/client-dynamodb
# - @aws-sdk/lib-dynamodb
# =============================================================================

set -e

LAYER_NAME="ugc-nodejs-dependencies"
REGION="${AWS_REGION:-us-east-1}"

echo "=============================================="
echo "Creating Node.js Dependencies Lambda Layer"
echo "=============================================="
echo "Layer Name: $LAYER_NAME"
echo "Region: $REGION"
echo ""

# Create temp directory
TEMP_DIR=$(mktemp -d)
LAYER_DIR="$TEMP_DIR/nodejs"
mkdir -p "$LAYER_DIR"

echo "=== Installing dependencies ==="
cd "$LAYER_DIR"

# Create package.json
cat > package.json << 'EOF'
{
  "name": "nodejs-layer",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "body-parser": "^1.20.2",
    "uuid": "^9.0.0",
    "@aws-sdk/client-dynamodb": "^3.450.0",
    "@aws-sdk/lib-dynamodb": "^3.450.0"
  }
}
EOF

# Install dependencies
npm install --production --no-optional
rm package.json package-lock.json 2>/dev/null || true

echo ""
echo "=== Creating layer zip ==="
cd "$TEMP_DIR"
zip -r layer.zip nodejs -q

LAYER_SIZE=$(du -h layer.zip | cut -f1)
echo "Layer size: $LAYER_SIZE"

echo ""
echo "=== Publishing Lambda Layer ==="
LAYER_ARN=$(aws lambda publish-layer-version \
    --layer-name "$LAYER_NAME" \
    --description "Common Node.js dependencies for UGC websites (express, cors, aws-sdk)" \
    --compatible-runtimes nodejs18.x nodejs20.x \
    --zip-file fileb://layer.zip \
    --region "$REGION" \
    --query 'LayerVersionArn' \
    --output text)

echo ""
echo "=============================================="
echo "✅ Lambda Layer created successfully!"
echo "=============================================="
echo ""
echo "Layer ARN: $LAYER_ARN"
echo ""
echo "Add this to lambda_adapter.py NODEJS_DEPS_LAYERS:"
echo "  \"$REGION\": \"$LAYER_ARN\""
echo ""

# Cleanup
rm -rf "$TEMP_DIR"

echo "Done!"
