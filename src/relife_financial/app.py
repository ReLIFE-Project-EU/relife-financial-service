from importlib.metadata import version

from fastapi import FastAPI

from relife_financial.config.logging import configure_logging
from relife_financial.routes import auth, examples, health

from relife_financial.routes.npv import router as npv_router
from relife_financial.routes.ii import router as ii_router
from relife_financial.routes.opex import router as opex_router
from relife_financial.routes.roi import router as roi_router
from relife_financial.routes.irr import router as irr_router

# Dynamically determine the package name
package_name = __name__.split(".")[0]

# Get version dynamically
package_dist_name = package_name.replace("_", "-")

try:
    __version__ = version(package_dist_name)
except ImportError:
    __version__ = "development"

configure_logging()

app = FastAPI(
    title="Financial Service APIs",
    description="FastAPI application for all financial indicators",
    version=__version__,
)

#app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Financial API. Try /docs for Swagger UI."}



app.include_router(health.router)
app.include_router(auth.router)
app.include_router(examples.router)

#Financial service endpoints
app.include_router(npv_router)
app.include_router(ii_router)
app.include_router(opex_router)
app.include_router(roi_router)
app.include_router(irr_router)
