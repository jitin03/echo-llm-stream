from app.app import app
import uvicorn
import os
# openai_api_key=os.environ.get("OPENAI_API_KEY")
api_key = os.environ.get("OPENAI_API_KEY")
port = int(os.getenv("PORT", "5566"))

uvicorn.run(app, host="0.0.0.0", port=port)
