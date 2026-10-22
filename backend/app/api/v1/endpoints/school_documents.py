"""Source-document endpoints for school courses (README §3.6, §3.15).

Teachers upload PDFs/Word docs that the AI course builder turns into courses.
The browser uploads the file straight to the private bucket with a signed URL
from `upload-url`, then calls `complete` to verify it and kick off extraction.
All routes are staff-only (school students are blocked by the route allowlist).
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.school_auth import SchoolCtx, school_member
from app.services import school_document_service as docs

router = APIRouter()


class UploadUrlRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    # ge=0 (not 1) so an empty file reaches the handler's friendly
    # document_rejected/empty_file message instead of a raw 422 validation error.
    size_bytes: int = Field(..., ge=0)
    mime: Optional[str] = None


@router.post("/{school_id}/documents/upload-url", summary="Start an upload: validate and sign a direct-to-storage URL")
def create_upload_url(body: UploadUrlRequest, ctx: SchoolCtx = Depends(school_member())):
    return docs.create_upload(ctx, body.filename, body.size_bytes, body.mime or "")


@router.post("/{school_id}/documents/{document_id}/complete", summary="Finish an upload: verify the file and queue extraction")
def complete_upload(document_id: str, ctx: SchoolCtx = Depends(school_member())):
    return docs.complete(ctx, document_id)


@router.get("/{school_id}/documents", summary="List the school's uploaded documents")
def list_documents(ctx: SchoolCtx = Depends(school_member())):
    return {"documents": docs.list_documents(ctx)}


@router.get("/{school_id}/documents/{document_id}", summary="One document's status and metadata")
def get_document(document_id: str, ctx: SchoolCtx = Depends(school_member())):
    return docs.get_document(ctx, document_id)


@router.delete("/{school_id}/documents/{document_id}", status_code=204, summary="Delete a document (keeps published courses)")
def delete_document(document_id: str, ctx: SchoolCtx = Depends(school_member())):
    docs.delete_document(ctx, document_id)
