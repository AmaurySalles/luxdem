"""
Main entry point of the solution.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ROUTE GUIDANCE #

# Add API App routes below via:
# "@app.get/post()"

# If many routes, consider:
#   1. Adding a subdirectory "app/routers" with routers,
#   2. Registering the routers in their files via
#      "<your_router_name> = APIRouter()"
#   3. Importing and adding the routers in this file via:
#      "app.include_router(<your_router_name>)


### ROUTES ###


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
