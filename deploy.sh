#!/bin/bash

# Cosmic Guru Backend Deployment Script
# Usage: ./deploy.sh [PROJECT_ID] [REGION]

set -e  # Exit on any error

# Default values
DEFAULT_PROJECT_ID="your-gcp-project-id"
DEFAULT_REGION="us-central1"
SERVICE_NAME="cosmic-guru-backend"

# Get parameters or use defaults
PROJECT_ID=${1:-$DEFAULT_PROJECT_ID}
REGION=${2:-$DEFAULT_REGION}

echo "🚀 Deploying Cosmic Guru Backend to Cloud Run..."
echo "📦 Project ID: $PROJECT_ID"
echo "🌍 Region: $REGION"
echo "🔧 Service: $SERVICE_NAME"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "   Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
echo "🔧 Setting GCP project..."
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "⚙️  Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com

# Build and deploy using Cloud Build
echo "🏗️  Starting Cloud Build deployment..."
gcloud builds submit \
    --config=cloudbuild.yaml \
    --substitutions=_REGION="$REGION" \
    .

echo "✅ Deployment complete!"

# Get the service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --format="value(status.url)")

echo ""
echo "🎉 Backend deployed successfully!"
echo "🔗 Service URL: $SERVICE_URL"
echo "🔍 Health check: $SERVICE_URL/health"
echo "📖 API docs: $SERVICE_URL/docs"

echo ""
echo "🔧 Useful commands:"
echo "   View logs: gcloud run logs tail --service=$SERVICE_NAME --region=$REGION"
echo "   Update service: gcloud run services update $SERVICE_NAME --region=$REGION"
echo "   Delete service: gcloud run services delete $SERVICE_NAME --region=$REGION"