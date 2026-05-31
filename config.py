import os
from dotenv import load_dotenv

load_dotenv()

AZURE_API_KEY    = os.getenv("AZURE_API_KEY", "")
AZURE_ENDPOINT   = os.getenv("AZURE_ENDPOINT", "https://1555692-6904-resource.openai.azure.com/")
AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT", "gpt-4o-mini")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-10-21")
SECRET_KEY       = os.getenv("SECRET_KEY", "bordados-gc-secret-2026")
