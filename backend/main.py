from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router

app = FastAPI(title="TrustGuard AI API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router. Prefix /api is used in frontend, but check if original had it.
# Original: @app.post("/api/verify"...)
# So we should prefix here or in router.
# Router has @router.post("/verify")
# So we need to include with prefix="/api".
app.include_router(router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "TrustGuard AI Backend is Running"}
