from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import auth, runs, files
from app.api import web_orders, jetro, vendor_bills, combined_price, exports, audit


app = FastAPI(
    title="B&R Food Services Workflow Automation",
    description="File-based workflow automation — JSON + XLSX storage, no database required.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(web_orders.router, prefix="/api/v1")
app.include_router(jetro.router, prefix="/api/v1")
app.include_router(vendor_bills.router, prefix="/api/v1")
app.include_router(combined_price.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "service": "B&R Food Services API"}
