"""
Main entry point of the solution.
"""
import uvicorn
from ecodev_core import attempt_to_log
from ecodev_core import AUTH
from ecodev_core import engine
from ecodev_core import get_session
from ecodev_core import JwtAuth
from ecodev_core import Token
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqladmin import Admin
from sqlmodel import Session

# from app.rag import DraftLawChatService


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# draft_law_chat_service = DraftLawChatService()


# class DraftLawChatRequest(BaseModel):
#     question: str
#     top_k: int | None = None


# class DraftLawChatSource(BaseModel):
#     source_id: str
#     law_id: int | None = None
#     law_number: str
#     law_title: str
#     law_status: str
#     text: str
#     score: float


# class DraftLawChatApiResponse(BaseModel):
#     answer: str
#     indexed_law_count: int
#     indexed_chunk_count: int
#     sources: list[DraftLawChatSource]

# ROUTE GUIDANCE #

# Add API App routes below via:
# "@app.get/post()"

# If many routes, consider:
#   1. Adding a subdirectory "app/routers" with routers,
#   2. Registering the routers in their files via
#      "<your_router_name> = APIRouter()"
#   3. Importing and adding the routers in this file via:
#      "app.include_router(<your_router_name>)


# ROUTES #
@app.post('/login', response_model=Token)
def login_route(
    user: OAuth2PasswordRequestForm = Depends(), session=Depends(get_session)
):
    """
    Route allowing users to log in.
    """
    return attempt_to_log(user.username, user.password, session)


# @app.post("/draft-law-chat", response_model=DraftLawChatApiResponse)
# def draft_law_chat_route(payload: DraftLawChatRequest):
#     try:
#         with Session(engine) as session:
#             response = draft_law_chat_service.answer_question(
#                 session=session,
#                 question=payload.question,
#                 top_k=payload.top_k,
#             )
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc)) from exc
#     except RuntimeError as exc:
#         raise HTTPException(status_code=503, detail=str(exc)) from exc

#     return DraftLawChatApiResponse(
#         answer=response.answer,
#         indexed_law_count=response.indexed_law_count,
#         indexed_chunk_count=response.indexed_chunk_count,
#         sources=[
#             DraftLawChatSource(
#                 source_id=source.source_id,
#                 law_id=source.law_id,
#                 law_number=source.law_number,
#                 law_title=source.law_title,
#                 law_status=source.law_status,
#                 text=source.text,
#                 score=source.score,
#             )
#             for source in response.sources
#         ],
#     )


# @app.post("/draft-law-chat/index")
# def draft_law_chat_index_route():
#     with Session(engine) as session:
#         return draft_law_chat_service.index_stats(session)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
