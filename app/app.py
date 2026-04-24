"""
Main entry point of the solution.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.analysis import router as analysis_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(analysis_router)


### ROUTES ###


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
